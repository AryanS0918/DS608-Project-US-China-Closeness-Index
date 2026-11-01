"""Build the production FDI structural-ties panel for the US-China Closeness Index."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

ANCHOR_ISO3 = {"China": "CHN", "United States": "USA"}
ANCHORS = tuple(ANCHOR_ISO3)
START_YEAR = 2018
END_YEAR = 2024
KEYS = ["country_iso3", "anchor", "year"]
HISTORICAL_ENTITY_CODES = {
    "BYS", "CSK", "DDR", "DHY", "HVO", "RHO", "SCG", "SVU", "VDR", "YUG"
}
METHOD = "official_outward_positive_log1p_scaled_to_anchor_year_p95"
SOURCE = "IMF Direct Investment Positions"


def require_columns(frame: pd.DataFrame, columns: set[str], label: str) -> None:
    missing = sorted(columns - set(frame.columns))
    if missing:
        raise ValueError(f"{label} is missing required columns: {missing}")


def load_inputs(
    candidates_path: Path,
    crosswalk_path: Path,
    country_master_path: Path,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    candidates = pd.read_csv(candidates_path)
    crosswalk = pd.read_csv(crosswalk_path)
    country_master = pd.read_csv(country_master_path)

    require_columns(
        candidates,
        {
            "country_source_name", "anchor", "reporting_perspective",
            "economic_direction", "DV_TYPE", "year",
            "fdi_position_usd_millions",
        },
        "IMF DIP candidates",
    )
    require_columns(
        crosswalk,
        {"country_source_name", "country_iso3", "country_name", "dip_period_eligible"},
        "IMF DIP country crosswalk",
    )
    require_columns(
        country_master,
        {"iso3", "country_name", "historical_entity"},
        "Project country master",
    )
    if crosswalk["country_source_name"].duplicated().any():
        raise ValueError("IMF DIP country crosswalk has duplicate source names.")
    if country_master["iso3"].duplicated().any():
        raise ValueError("Project country master has duplicate ISO3 identifiers.")
    return candidates, crosswalk, country_master


def select_official_outward(
    candidates: pd.DataFrame,
    crosswalk: pd.DataFrame,
) -> pd.DataFrame:
    mapped = candidates.merge(
        crosswalk[
            ["country_source_name", "country_iso3", "country_name", "dip_period_eligible"]
        ],
        on="country_source_name",
        how="left",
        validate="many_to_one",
    )
    eligible = mapped["dip_period_eligible"].astype("boolean").fillna(False)
    selected = mapped.loc[
        mapped["country_iso3"].notna()
        & eligible
        & mapped["economic_direction"].eq("anchor_to_country")
        & mapped["reporting_perspective"].eq("anchor_report")
        & mapped["DV_TYPE"].eq("Reported official data")
        & mapped["anchor"].isin(ANCHORS)
        & mapped["year"].between(START_YEAR, END_YEAR)
    ].copy()
    selected = selected.loc[
        selected["country_iso3"] != selected["anchor"].map(ANCHOR_ISO3)
    ]
    if selected.duplicated(KEYS).any():
        duplicates = selected.loc[selected.duplicated(KEYS, keep=False), KEYS]
        raise ValueError(
            "Official outward selection has duplicate country-anchor-year keys: "
            f"{duplicates.head().to_dict('records')}"
        )
    return selected


def build_full_grid(country_master: pd.DataFrame) -> pd.DataFrame:
    countries = country_master.loc[
        ~country_master["iso3"].isin(HISTORICAL_ENTITY_CODES),
        ["iso3", "country_name"],
    ].rename(columns={"iso3": "country_iso3"})
    grid = pd.MultiIndex.from_product(
        [countries["country_iso3"], ANCHORS, range(START_YEAR, END_YEAR + 1)],
        names=KEYS,
    ).to_frame(index=False)
    grid = grid.loc[
        grid["country_iso3"] != grid["anchor"].map(ANCHOR_ISO3)
    ]
    return grid.merge(countries, on="country_iso3", how="left", validate="many_to_one")


def score_anchor_year(group: pd.DataFrame) -> pd.DataFrame:
    result = group.copy()
    observed = result["observed"]
    positive = result["positive_position_usd_mn"]
    positive_mask = observed & positive.gt(0)
    log_positive = np.log1p(positive)
    cap = log_positive.loc[positive_mask].quantile(0.95)
    if pd.isna(cap) or cap <= 0:
        score = pd.Series(np.where(observed, 0.0, np.nan), index=result.index)
    else:
        score = pd.Series(
            np.where(observed, np.minimum(log_positive / cap, 1.0), np.nan),
            index=result.index,
        )
    result["fdi_structural_score_raw"] = score
    result["log_p95_cap"] = cap
    return result


def build_panel(
    candidates: pd.DataFrame,
    crosswalk: pd.DataFrame,
    country_master: pd.DataFrame,
) -> pd.DataFrame:
    selected = select_official_outward(candidates, crosswalk)
    panel = build_full_grid(country_master).merge(
        selected[KEYS + ["fdi_position_usd_millions"]],
        on=KEYS,
        how="left",
        validate="one_to_one",
    ).rename(columns={"fdi_position_usd_millions": "fdi_outward_position_usd_mn"})

    panel["observed"] = panel["fdi_outward_position_usd_mn"].notna()
    panel["observed_zero"] = panel["fdi_outward_position_usd_mn"].eq(0)
    panel["observed_negative"] = panel["fdi_outward_position_usd_mn"].lt(0)
    panel["positive_position_usd_mn"] = panel["fdi_outward_position_usd_mn"].clip(lower=0)

    scored = pd.concat(
        [
            score_anchor_year(group)
            for _, group in panel.groupby(["anchor", "year"], sort=True)
        ],
        ignore_index=True,
    )
    scored["method"] = METHOD
    scored["source"] = SOURCE
    columns = [
        "country_iso3", "country_name", "anchor", "year",
        "fdi_outward_position_usd_mn", "observed", "observed_zero",
        "observed_negative", "fdi_structural_score_raw", "log_p95_cap",
        "method", "source",
    ]
    return scored[columns].sort_values(KEYS).reset_index(drop=True)


def validate_panel(panel: pd.DataFrame) -> None:
    if panel.duplicated(KEYS).any():
        raise AssertionError("Production panel has duplicate keys.")
    if not panel["year"].between(START_YEAR, END_YEAR).all():
        raise AssertionError("Production panel contains years outside 2018-2024.")
    if not panel.loc[~panel["observed"], "fdi_structural_score_raw"].isna().all():
        raise AssertionError("Missing observations must retain missing scores.")
    if not panel.loc[panel["observed_negative"], "fdi_structural_score_raw"].eq(0).all():
        raise AssertionError("Observed negative positions must receive zero intensity.")
    scores = panel["fdi_structural_score_raw"].dropna()
    if not scores.between(0, 1).all():
        raise AssertionError("FDI scores must lie in [0, 1].")
    maxima = panel.groupby(["anchor", "year"])["fdi_structural_score_raw"].max()
    if not np.allclose(maxima.to_numpy(), 1.0):
        raise AssertionError("Every anchor-year must contain at least one score of 1.")


def build_summary(panel: pd.DataFrame) -> dict[str, object]:
    by_anchor = {}
    for anchor, group in panel.groupby("anchor"):
        by_anchor[anchor] = {
            "rows": int(len(group)),
            "observed": int(group["observed"].sum()),
            "missing": int((~group["observed"]).sum()),
            "observed_zero": int(group["observed_zero"].sum()),
            "observed_negative": int(group["observed_negative"].sum()),
        }
    return {
        "method": METHOD,
        "source": SOURCE,
        "start_year": START_YEAR,
        "end_year": END_YEAR,
        "rows": int(len(panel)),
        "unique_countries_or_entities": int(panel["country_iso3"].nunique()),
        "anchors": list(ANCHORS),
        "by_anchor": by_anchor,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--candidates",
        type=Path,
        default=Path("data/interim/fdi/imf_dip_primary_candidates.csv"),
    )
    parser.add_argument(
        "--crosswalk",
        type=Path,
        default=Path("outputs/tables/fdi/imf_dip_country_crosswalk_audit.csv"),
    )
    parser.add_argument(
        "--country-master",
        type=Path,
        default=Path(
            "outputs/tables/relations_condition/relationship_condition_country_master.csv"
        ),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/processed/fdi_structural_ties_country_anchor_year.csv"),
    )
    parser.add_argument(
        "--summary",
        type=Path,
        default=Path("outputs/tables/fdi/fdi_structural_ties_summary.json"),
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    candidates, crosswalk, country_master = load_inputs(
        args.candidates, args.crosswalk, args.country_master
    )
    panel = build_panel(candidates, crosswalk, country_master)
    validate_panel(panel)
    summary = build_summary(panel)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.summary.parent.mkdir(parents=True, exist_ok=True)
    panel.to_csv(args.output, index=False)
    args.summary.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")

    print(f"Wrote {args.output} ({len(panel):,} rows)")
    print(f"Wrote {args.summary}")
    print(f"Production period: {START_YEAR}-{END_YEAR}")
    print(f"Method: {METHOD}")


if __name__ == "__main__":
    main()
