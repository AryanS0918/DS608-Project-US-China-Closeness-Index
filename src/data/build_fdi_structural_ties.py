"""Build country-fixed-regime FDI structural ties from IMF DIP positions.

Run from the repository root:
    python src/data/build_fdi_structural_ties.py

Each country is assigned one official reporting regime for its full FDI history:

- host-official when signed host-reported positions are available in at least
  6 of 9 years during 2009-2017 and at least 4 of 7 years during 2018-2024;
- anchor-official otherwise.

Host-regime countries use host-reported official inward positions for both
anchors during 2009-2024. Anchor-regime countries use anchor-reported official
outward positions for both anchors during 2018-2024. Countries never switch
reporting perspective. Missing official observations remain missing.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

ANCHORS = ("China", "United States")
PROJECT_START = 2004
PROJECT_END = 2025
HOST_START = 2009
SOURCE_END = 2024
ANCHOR_START = 2018
HOST_PRE_YEARS = range(2009, 2018)
HOST_POST_YEARS = range(2018, 2025)
PREFERRED_PRE_THRESHOLD = 6
PREFERRED_POST_THRESHOLD = 4
KEYS = ["country_iso3", "anchor", "year"]
METHOD = "country_fixed_official_regime_log1p_scaled_to_selected_anchor_year_p95"
SOURCE = "IMF Direct Investment Positions"


def require_columns(frame: pd.DataFrame, required: set[str], label: str) -> None:
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(f"{label} missing required columns: {missing}")


def build_universe(master: pd.DataFrame) -> pd.DataFrame:
    require_columns(
        master,
        {
            "iso3", "country_name", "preferred_country_name",
            "first_valid_year", "last_valid_year", "baseline_index_eligible",
        },
        "Country master",
    )
    rows = []
    for row in master.loc[master["baseline_index_eligible"].eq(True)].itertuples(index=False):
        first = PROJECT_START if pd.isna(row.first_valid_year) else max(PROJECT_START, int(row.first_valid_year))
        last = PROJECT_END if pd.isna(row.last_valid_year) else min(PROJECT_END, int(row.last_valid_year))
        for year in range(first, last + 1):
            for anchor in ANCHORS:
                rows.append({
                    "country_iso3": row.iso3,
                    "country_name": row.country_name,
                    "preferred_country_name": row.preferred_country_name,
                    "anchor": anchor,
                    "year": year,
                })
    universe = pd.DataFrame(rows).sort_values(KEYS).reset_index(drop=True)
    if universe.duplicated(KEYS).any():
        raise ValueError("Canonical FDI universe contains duplicate keys.")
    return universe


def build_source_name_map(crosswalk: pd.DataFrame, master: pd.DataFrame) -> dict[str, str]:
    require_columns(
        crosswalk,
        {"country_source_name", "canonical_country_iso3"},
        "FDI production crosswalk audit",
    )
    valid = set(master.loc[master["baseline_index_eligible"].eq(True), "iso3"])
    mapping = (
        crosswalk.dropna(subset=["canonical_country_iso3"])
        .loc[lambda d: d["canonical_country_iso3"].isin(valid)]
        .drop_duplicates("country_source_name")
        .set_index("country_source_name")["canonical_country_iso3"]
        .to_dict()
    )
    return mapping


def prepare_candidates(
    candidates: pd.DataFrame,
    crosswalk: pd.DataFrame,
    master: pd.DataFrame,
) -> pd.DataFrame:
    require_columns(
        candidates,
        {
            "country_source_name", "anchor", "reporting_perspective",
            "economic_direction", "DV_TYPE", "year",
            "fdi_position_usd_millions", "observed", "negative", "zero",
        },
        "IMF DIP candidates",
    )
    selected = candidates.loc[
        candidates["anchor"].isin(ANCHORS)
        & candidates["economic_direction"].eq("anchor_to_country")
        & candidates["DV_TYPE"].eq("Reported official data")
        & candidates["reporting_perspective"].isin(["anchor_report", "country_report"])
        & candidates["year"].between(HOST_START, SOURCE_END)
    ].copy()
    selected["country_iso3"] = selected["country_source_name"].map(
        build_source_name_map(crosswalk, master)
    )
    selected = selected.loc[selected["country_iso3"].notna()].copy()
    if selected.duplicated(KEYS + ["reporting_perspective"]).any():
        bad = selected.loc[
            selected.duplicated(KEYS + ["reporting_perspective"], keep=False),
            KEYS + ["reporting_perspective"],
        ]
        raise ValueError(f"Duplicate official candidate keys: {bad.head().to_dict('records')}")
    return selected


def signed_host_availability(candidates: pd.DataFrame) -> pd.DataFrame:
    host = candidates.loc[candidates["reporting_perspective"].eq("country_report")].copy()
    availability = host.pivot(
        index=["country_iso3", "year"], columns="anchor", values="observed"
    ).reset_index()
    availability["signed_host_available"] = (
        availability["China"].eq(True)
        & availability["United States"].eq(True)
    )
    return availability[["country_iso3", "year", "signed_host_available"]]


def assign_regimes(
    candidates: pd.DataFrame,
    master: pd.DataFrame,
    pre_threshold: int = PREFERRED_PRE_THRESHOLD,
    post_threshold: int = PREFERRED_POST_THRESHOLD,
) -> pd.DataFrame:
    eligible = (
        master.loc[
            master["baseline_index_eligible"].eq(True)
            & master["iso3"].ne("SCG"),
            ["iso3", "preferred_country_name"],
        ]
        .rename(columns={"iso3": "country_iso3"})
        .copy()
    )
    availability = signed_host_availability(candidates)
    rows = []
    for country in eligible["country_iso3"]:
        group = availability.loc[availability["country_iso3"].eq(country)]
        pre = int(group.loc[group["year"].isin(HOST_PRE_YEARS), "signed_host_available"].sum())
        post = int(group.loc[group["year"].isin(HOST_POST_YEARS), "signed_host_available"].sum())
        regime = (
            "host_official_fixed_regime"
            if pre >= pre_threshold and post >= post_threshold
            else "anchor_official_fixed_regime"
        )
        rows.append({
            "country_iso3": country,
            "host_signed_years_2009_2017": pre,
            "host_signed_years_2018_2024": post,
            "fdi_reporting_regime": regime,
            "regime_pre_threshold": pre_threshold,
            "regime_post_threshold": post_threshold,
            "regime_assignment_rule": (
                f"host_if_pre_ge_{pre_threshold}_and_post_ge_{post_threshold}"
            ),
        })
    audit = eligible.merge(pd.DataFrame(rows), on="country_iso3", validate="one_to_one")
    return audit.sort_values("country_iso3").reset_index(drop=True)


def select_fixed_regime_evidence(
    candidates: pd.DataFrame,
    regime_audit: pd.DataFrame,
) -> pd.DataFrame:
    regime = regime_audit.set_index("country_iso3")["fdi_reporting_regime"]
    selected = candidates.copy()
    selected["fdi_reporting_regime"] = selected["country_iso3"].map(regime)
    selected = selected.loc[
        (
            selected["fdi_reporting_regime"].eq("host_official_fixed_regime")
            & selected["reporting_perspective"].eq("country_report")
        )
        |
        (
            selected["fdi_reporting_regime"].eq("anchor_official_fixed_regime")
            & selected["reporting_perspective"].eq("anchor_report")
            & selected["year"].ge(ANCHOR_START)
        )
    ].copy()
    selected["fdi_position_provenance"] = np.where(
        selected["reporting_perspective"].eq("country_report"),
        "host_reported_official",
        "anchor_reported_official",
    )
    return selected


def score_anchor_year(group: pd.DataFrame) -> pd.DataFrame:
    result = group.copy()
    observed_positive = (
        result["observed"]
        & result["fdi_outward_position_usd_mn"].gt(0)
    )
    result["positive_position_usd_mn"] = result[
        "fdi_outward_position_usd_mn"
    ].where(observed_positive, 0.0)
    result["log_positive_position"] = np.log1p(result["positive_position_usd_mn"])
    positive_logs = result.loc[observed_positive, "log_positive_position"]
    cap = float(positive_logs.quantile(0.95)) if not positive_logs.empty else np.nan
    result["log_p95_cap"] = cap
    result["fdi_structural_score_raw"] = np.nan
    if pd.notna(cap) and cap > 0:
        result.loc[result["observed"], "fdi_structural_score_raw"] = (
            result.loc[result["observed"], "log_positive_position"] / cap
        ).clip(upper=1.0)
    elif result["observed"].any():
        result.loc[result["observed"], "fdi_structural_score_raw"] = 0.0
    return result


def build_panel(
    candidates: pd.DataFrame,
    crosswalk: pd.DataFrame,
    master: pd.DataFrame,
    pre_threshold: int = PREFERRED_PRE_THRESHOLD,
    post_threshold: int = PREFERRED_POST_THRESHOLD,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    universe = build_universe(master)
    prepared = prepare_candidates(candidates, crosswalk, master)
    audit = assign_regimes(prepared, master, pre_threshold, post_threshold)
    selected = select_fixed_regime_evidence(prepared, audit)
    evidence = selected[
        [
            "country_iso3", "anchor", "year", "country_source_name",
            "fdi_position_usd_millions", "observed", "negative", "zero",
            "fdi_reporting_regime", "fdi_position_provenance",
        ]
    ].rename(columns={
        "fdi_position_usd_millions": "fdi_outward_position_usd_mn",
        "negative": "observed_negative",
        "zero": "observed_zero",
    })
    panel = universe.merge(evidence, on=KEYS, how="left", validate="one_to_one")
    panel = panel.merge(
        audit[
            [
                "country_iso3", "host_signed_years_2009_2017",
                "host_signed_years_2018_2024", "fdi_reporting_regime",
                "regime_assignment_rule",
            ]
        ],
        on="country_iso3",
        how="left",
        suffixes=("", "_assigned"),
        validate="many_to_one",
    )
    panel["fdi_reporting_regime"] = panel["fdi_reporting_regime"].combine_first(
        panel["fdi_reporting_regime_assigned"]
    )
    panel = panel.drop(columns=["fdi_reporting_regime_assigned"])

    host_regime = panel["fdi_reporting_regime"].eq("host_official_fixed_regime")
    anchor_regime = panel["fdi_reporting_regime"].eq("anchor_official_fixed_regime")
    regime_source_period = (
        (host_regime & panel["year"].between(HOST_START, SOURCE_END))
        | (anchor_regime & panel["year"].between(ANCHOR_START, SOURCE_END))
    )
    panel["observed"] = panel["observed"].eq(True) & regime_source_period
    panel["observed_negative"] = panel["observed_negative"].eq(True) & panel["observed"]
    panel["observed_zero"] = panel["observed_zero"].eq(True) & panel["observed"]
    panel.loc[~panel["observed"], "fdi_outward_position_usd_mn"] = np.nan
    panel.loc[
        regime_source_period & ~panel["observed"], "fdi_position_provenance"
    ] = "official_position_unavailable"
    panel.loc[
        ~regime_source_period, "fdi_position_provenance"
    ] = "source_period_unavailable"

    panel["fdi_evidence_status"] = np.select(
        [
            ~regime_source_period,
            regime_source_period & panel["observed_negative"],
            regime_source_period & panel["observed_zero"],
            regime_source_period & panel["observed"] & panel["fdi_outward_position_usd_mn"].gt(0),
            regime_source_period & ~panel["observed"],
        ],
        [
            "source_period_unavailable",
            "observed_negative_net_position",
            "observed_zero_position",
            "observed_positive_position",
            "official_position_unobserved",
        ],
        default="invalid",
    )

    score_parts = []
    for (_, _), group in panel.loc[regime_source_period].groupby(["anchor", "year"], sort=False):
        score_parts.append(score_anchor_year(group))
    scored = pd.concat(score_parts, ignore_index=True)
    score_columns = KEYS + [
        "positive_position_usd_mn", "log_positive_position",
        "log_p95_cap", "fdi_structural_score_raw",
    ]
    panel = panel.merge(scored[score_columns], on=KEYS, how="left", validate="one_to_one")

    panel["fdi_period_status"] = np.select(
        [
            panel["year"].between(2004, 2008),
            host_regime & panel["year"].between(2009, 2017),
            anchor_regime & panel["year"].between(2009, 2017),
            panel["year"].between(2018, 2024),
            panel["year"].eq(2025),
        ],
        [
            "pre_fdi_source_period_unavailable",
            "host_official_historical_extension",
            "pre_anchor_source_period_unavailable",
            "fixed_regime_common_period",
            "provisional_latest_year_source_unavailable",
        ],
        default="invalid",
    )
    panel["method"] = METHOD
    panel["source"] = SOURCE

    output_columns = [
        "country_iso3", "country_name", "preferred_country_name", "anchor", "year",
        "fdi_reporting_regime", "regime_assignment_rule",
        "host_signed_years_2009_2017", "host_signed_years_2018_2024",
        "country_source_name", "fdi_position_provenance",
        "fdi_outward_position_usd_mn", "observed", "observed_zero",
        "observed_negative", "fdi_evidence_status", "positive_position_usd_mn",
        "log_positive_position", "log_p95_cap", "fdi_structural_score_raw",
        "fdi_period_status", "method", "source",
    ]
    output = panel[output_columns].sort_values(KEYS).reset_index(drop=True)
    validate_panel(output, pre_threshold, post_threshold)
    return output, audit


def validate_panel(panel: pd.DataFrame, pre_threshold: int, post_threshold: int) -> dict[str, int]:
    failures = {
        "unexpected_rows": int(len(panel) != 8410),
        "unexpected_entities": int(panel["country_iso3"].nunique() != 192),
        "duplicate_keys": int(panel.duplicated(KEYS).sum()),
        "invalid_status": int((panel[["fdi_evidence_status", "fdi_period_status"]] == "invalid").any(axis=1).sum()),
        "score_out_of_bounds": int((~panel["fdi_structural_score_raw"].dropna().between(0, 1)).sum()),
        "score_without_observation": int((panel["fdi_structural_score_raw"].notna() & ~panel["observed"]).sum()),
        "missing_observed_score": int((panel["observed"] & panel["fdi_structural_score_raw"].isna()).sum()),
        "nonzero_zero_or_negative": int(((panel["observed_zero"] | panel["observed_negative"]) & panel["fdi_structural_score_raw"].ne(0)).sum()),
        "host_regime_below_threshold": int((
            panel["fdi_reporting_regime"].eq("host_official_fixed_regime")
            & (
                panel["host_signed_years_2009_2017"].lt(pre_threshold)
                | panel["host_signed_years_2018_2024"].lt(post_threshold)
            )
        ).sum()),
        "host_rows_using_anchor_provenance": int((
            panel["fdi_reporting_regime"].eq("host_official_fixed_regime")
            & panel["fdi_position_provenance"].eq("anchor_reported_official")
        ).sum()),
        "anchor_rows_using_host_provenance": int((
            panel["fdi_reporting_regime"].eq("anchor_official_fixed_regime")
            & panel["fdi_position_provenance"].eq("host_reported_official")
        ).sum()),
        "pre_2009_scores": int(panel.loc[panel["year"].lt(2009), "fdi_structural_score_raw"].notna().sum()),
        "2025_scores": int(panel.loc[panel["year"].eq(2025), "fdi_structural_score_raw"].notna().sum()),
    }
    if any(failures.values()):
        raise ValueError(f"FDI fixed-regime validation failed: {failures}")
    return failures


def build_summary(panel: pd.DataFrame, audit: pd.DataFrame) -> dict:
    signed = panel.pivot(
        index=["country_iso3", "year"], columns="anchor",
        values="fdi_structural_score_raw",
    ).reset_index()
    signed["signed_available"] = signed["China"].notna() & signed["United States"].notna()
    annual = {
        str(int(year)): int(group["signed_available"].sum())
        for year, group in signed.groupby("year")
    }
    return {
        "method": METHOD,
        "source": SOURCE,
        "rows": int(len(panel)),
        "entities": int(panel["country_iso3"].nunique()),
        "years": [PROJECT_START, PROJECT_END],
        "regime_assignment": {
            "pre_period": [2009, 2017],
            "post_period": [2018, 2024],
            "host_pre_threshold": PREFERRED_PRE_THRESHOLD,
            "host_post_threshold": PREFERRED_POST_THRESHOLD,
            "regime_counts": {
                key: int(value)
                for key, value in audit["fdi_reporting_regime"].value_counts().items()
            },
        },
        "signed_fdi_scores_by_year": annual,
        "position_provenance_counts": {
            key: int(value)
            for key, value in panel["fdi_position_provenance"].value_counts().items()
        },
        "evidence_status_counts": {
            key: int(value)
            for key, value in panel["fdi_evidence_status"].value_counts().items()
        },
        "validation_failures": validate_panel(
            panel, PREFERRED_PRE_THRESHOLD, PREFERRED_POST_THRESHOLD
        ),
    }


def write_sensitivities(
    candidates: pd.DataFrame,
    crosswalk: pd.DataFrame,
    master: pd.DataFrame,
    output_dir: Path,
) -> None:
    rows = []
    for name, pre, post in [
        ("moderate", 5, 4),
        ("preferred", 6, 4),
        ("strict", 7, 5),
    ]:
        panel, audit = build_panel(candidates, crosswalk, master, pre, post)
        signed = panel.pivot(
            index=["country_iso3", "year"], columns="anchor",
            values="fdi_structural_score_raw",
        ).reset_index()
        signed["fdi_orientation_score"] = signed["United States"] - signed["China"]
        for year, group in signed.groupby("year"):
            rows.append({
                "assignment_rule": name,
                "pre_threshold": pre,
                "post_threshold": post,
                "year": int(year),
                "host_regime_countries": int(
                    audit["fdi_reporting_regime"].eq("host_official_fixed_regime").sum()
                ),
                "anchor_regime_countries": int(
                    audit["fdi_reporting_regime"].eq("anchor_official_fixed_regime").sum()
                ),
                "signed_fdi_scores": int(group["fdi_orientation_score"].notna().sum()),
            })
    pd.DataFrame(rows).to_csv(
        output_dir / "fdi_regime_assignment_sensitivity_by_year.csv", index=False
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidates", type=Path, default=Path("data/interim/fdi/imf_dip_primary_candidates.csv"))
    parser.add_argument("--crosswalk", type=Path, default=Path("outputs/tables/fdi/fdi_country_crosswalk_production_audit.csv"))
    parser.add_argument("--country-master", type=Path, default=Path("outputs/tables/relations_condition/relationship_condition_country_master.csv"))
    parser.add_argument("--output", type=Path, default=Path("data/processed/fdi_structural_ties_country_anchor_year.csv"))
    parser.add_argument("--audit-directory", type=Path, default=Path("outputs/tables/fdi"))
    args = parser.parse_args()
    candidates = pd.read_csv(args.candidates, low_memory=False)
    crosswalk = pd.read_csv(args.crosswalk, low_memory=False)
    master = pd.read_csv(args.country_master, low_memory=False)
    panel, audit = build_panel(candidates, crosswalk, master)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.audit_directory.mkdir(parents=True, exist_ok=True)
    panel.to_csv(args.output, index=False)
    audit.to_csv(args.audit_directory / "fdi_reporting_regime_assignment.csv", index=False)
    (args.audit_directory / "fdi_structural_ties_summary.json").write_text(
        json.dumps(build_summary(panel, audit), indent=2) + "\n"
    )
    write_sensitivities(candidates, crosswalk, master, args.audit_directory)
    print(f"Wrote {len(panel):,} rows to {args.output}")


if __name__ == "__main__":
    main()
