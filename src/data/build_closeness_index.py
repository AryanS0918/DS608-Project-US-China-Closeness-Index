"""Build the official core and experimental US-China orientation indices.

Positive scores indicate greater US orientation; negative scores indicate
greater China orientation. Technology is retained as an experimental ICT-goods
trade measure and does not enter the official core index.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

CORE_PILLARS = ["security_score", "diplomatic_score", "economic_score"]
EXPERIMENTAL_PILLARS = CORE_PILLARS + ["technology_score"]
TECHNOLOGY_SOURCE_COLUMN = "dva_adjusted_orientation_score"


def weighted_index(frame: pd.DataFrame, weights: dict[str, float], min_available: int) -> pd.DataFrame:
    """Return scores and effective weights without ever zero-filling missing evidence."""
    columns = list(weights)
    missing = set(columns) - set(frame.columns)
    if missing:
        raise KeyError(f"Missing score columns: {sorted(missing)}")
    requested = pd.Series(weights, dtype=float)
    if (requested < 0).any():
        raise ValueError("Weights must be non-negative")
    if requested.sum() <= 0:
        raise ValueError("At least one weight must be positive")
    requested = requested / requested.sum()

    observed = frame[columns].notna()
    positive_observed = observed.mul(requested.gt(0), axis=1)
    available_count = positive_observed.sum(axis=1)
    effective_raw = observed.astype(float).mul(requested, axis=1)
    coverage = effective_raw.sum(axis=1)
    effective = effective_raw.div(coverage.replace(0, np.nan), axis=0)

    # min_count=1 prevents an all-missing weighted row from becoming zero.
    contributions = frame[columns].mul(effective)
    score = contributions.sum(axis=1, min_count=1)
    valid = coverage.gt(0) & available_count.ge(min_available)

    result = pd.DataFrame(index=frame.index)
    result["score"] = score.where(valid)
    result["available_count"] = available_count.astype(int)
    result["requested_weight_coverage"] = coverage
    result["missing_pillars"] = observed.apply(
        lambda row: "|".join(c.removesuffix("_score") for c, ok in row.items() if not ok), axis=1
    )
    for column in columns:
        result[f"effective_{column.removesuffix('_score')}_weight"] = effective[column].where(valid)
    return result


def eligible_country_years(master: pd.DataFrame, start: int = 2004, end: int = 2024) -> pd.DataFrame:
    years = pd.DataFrame({"year": range(start, end + 1)})
    eligible = master.loc[master["baseline_index_eligible"].astype(bool)].copy()
    grid = eligible.assign(_key=1).merge(years.assign(_key=1), on="_key").drop(columns="_key")
    first = pd.to_numeric(grid["first_valid_year"], errors="coerce")
    last = pd.to_numeric(grid["last_valid_year"], errors="coerce")
    valid = (first.isna() | grid["year"].ge(first)) & (last.isna() | grid["year"].le(last))
    return grid.loc[valid, ["iso3", "preferred_country_name", "year"]].rename(columns={"iso3": "country_iso3"})


def build_panel(security: pd.DataFrame, diplomatic: pd.DataFrame, economic: pd.DataFrame,
                technology: pd.DataFrame, master: pd.DataFrame) -> pd.DataFrame:
    spine = eligible_country_years(master)
    sec = security.rename(columns={"iso3": "country_iso3"})[
        ["country_iso3", "year", "security_score", "institutional_signed_score",
         "arms_transfer_score", "arms_observation_status", "security_integration_status"]
    ]
    dip = diplomatic[["country_iso3", "year", "diplomatic_score",
                      "diplomatic_integration_status", "diplomatic_comparability_status"]]
    eco = economic[["country_iso3", "year", "economic_score", "available_component_count",
                    "economic_component_status", "economic_comparability_status"]].rename(
        columns={"available_component_count": "economic_available_component_count"}
    )
    tech = technology.rename(columns={"reporter_iso": "country_iso3",
                                      TECHNOLOGY_SOURCE_COLUMN: "technology_score"})[
        ["country_iso3", "year", "technology_score", "china_ratio_status", "us_ratio_status"]
    ]
    panel = spine.merge(sec, on=["country_iso3", "year"], how="left", validate="one_to_one")
    panel = panel.merge(dip, on=["country_iso3", "year"], how="left", validate="one_to_one")
    panel = panel.merge(eco, on=["country_iso3", "year"], how="left", validate="one_to_one")
    panel = panel.merge(tech, on=["country_iso3", "year"], how="left", validate="one_to_one")

    panel["security_no_ties_flag"] = (
        panel["security_score"].eq(0)
        & panel["institutional_signed_score"].eq(0)
        & panel["arms_transfer_score"].fillna(0).eq(0)
    )

    core = weighted_index(panel, {c: 1 for c in CORE_PILLARS}, min_available=2)
    panel["core_index_available"] = core["score"]
    panel["core_available_pillar_count"] = core["available_count"]
    panel["core_missing_pillars"] = core["missing_pillars"]
    panel["core_requested_weight_coverage"] = core["requested_weight_coverage"]
    for p in ["security", "diplomatic", "economic"]:
        panel[f"core_effective_{p}_weight"] = core[f"effective_{p}_weight"]
    panel["core_index_complete"] = panel[CORE_PILLARS].mean(axis=1).where(panel[CORE_PILLARS].notna().all(axis=1))

    experimental = weighted_index(panel, {c: 1 for c in EXPERIMENTAL_PILLARS}, min_available=3)
    panel["experimental_technology_index"] = experimental["score"].where(
    panel["technology_score"].notna()
    )  
    panel["experimental_available_pillar_count"] = experimental["available_count"]
    panel["experimental_missing_pillars"] = experimental["missing_pillars"]

    no_ties = panel.copy()
    no_ties.loc[no_ties["security_no_ties_flag"], "security_score"] = np.nan
    sensitivity = weighted_index(no_ties, {c: 1 for c in CORE_PILLARS}, min_available=2)
    panel["core_index_security_no_ties_unavailable"] = sensitivity["score"]
    panel["security_zero_treatment_difference"] = (
        panel["core_index_security_no_ties_unavailable"] - panel["core_index_available"]
    )

    panel["core_index_status"] = np.select(
        [panel["core_available_pillar_count"].eq(3), panel["core_available_pillar_count"].eq(2)],
        ["complete_three_pillar", "available_two_pillar_renormalised"],
        default="insufficient_core_pillars",
    )
    panel["technology_status"] = np.where(panel["technology_score"].notna(), "experimental_available", "experimental_unavailable")
    return panel.sort_values(["country_iso3", "year"]).reset_index(drop=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-dir", type=Path, default=Path("data/processed"))
    parser.add_argument("--master", type=Path, default=Path("outputs/tables/relations_condition/relationship_condition_country_master.csv"))
    parser.add_argument("--output-dir", type=Path, default=Path("outputs/tables/closeness_index"))
    args = parser.parse_args()
    panel = build_panel(
        pd.read_csv(args.input_dir / "security_subindex_country_year.csv"),
        pd.read_csv(args.input_dir / "diplomatic_subindex_country_year.csv"),
        pd.read_csv(args.input_dir / "economic_subindex_country_year.csv"),
        pd.read_csv(args.input_dir / "technology_trade_country_year.csv"),
        pd.read_csv(args.master),
    )
    args.output_dir.mkdir(parents=True, exist_ok=True)
    panel.to_csv(args.output_dir / "us_china_relative_orientation_index_country_year.csv", index=False)
    summary = {
        "period": [2004, 2024],
        "sign_convention": "positive_US_negative_China",
        "official_core_pillars": CORE_PILLARS,
        "official_complete_scores": int(panel["core_index_complete"].notna().sum()),
        "official_available_scores": int(panel["core_index_available"].notna().sum()),
        "technology_role": "experimental_ICT_goods_trade_orientation",
        "experimental_scores": int(panel["experimental_technology_index"].notna().sum()),
        "security_no_ties_rows": int(panel["security_no_ties_flag"].sum()),
    }
    (args.output_dir / "closeness_index_summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))

if __name__ == "__main__":
    main()
