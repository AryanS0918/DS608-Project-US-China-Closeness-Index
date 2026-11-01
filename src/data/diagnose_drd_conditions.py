"""Diagnose provisional diplomatic-condition rules from the DRD anchor panel.

Complete runnable example.

Run from the repository root:
    python -u src/data/diagnose_drd_conditions.py

Inputs:
    data/interim/relations/drd_anchor_directed_country_year.parquet

Outputs:
    outputs/tables/diplomatic_representation/drd_condition_diagnostic.csv
    outputs/tables/diplomatic_representation/drd_condition_frequency.csv
    outputs/tables/diplomatic_representation/drd_material_downgrades.csv
    outputs/tables/diplomatic_representation/drd_lor_zero_events.csv
    outputs/tables/diplomatic_representation/drd_restorations.csv
    outputs/tables/diplomatic_representation/drd_one_direction_only.csv
    outputs/tables/diplomatic_representation/drd_condition_summary.json

The diagnostic applies the provisional rules mechanically. It does not overwrite
source data and does not create a final project relationship-condition score.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd


DEFAULT_INPUT = Path(
    "data/interim/relations/drd_anchor_directed_country_year.parquet"
)
DEFAULT_OUTPUT_DIR = Path("outputs/tables/diplomatic_representation")

LOR_TO_BAND = {
    0.000: 0,
    0.100: 1,
    0.125: 1,
    0.375: 2,
    0.500: 2,
    0.750: 3,
    1.000: 4,
}

SEVERITY = {
    "missing": -1,
    "normal": 0,
    "strained": 1,
    "severely_strained": 2,
    "ruptured": 3,
}


def map_lor_to_band(value: object) -> float:
    if pd.isna(value):
        return np.nan
    numeric = round(float(value), 3)
    if numeric not in LOR_TO_BAND:
        raise ValueError(f"Unexpected LOR value: {value!r}")
    return float(LOR_TO_BAND[numeric])


def current_source_signal(group: pd.DataFrame) -> str:
    """Classify a country-anchor-year using two directed DRD observations."""
    by_direction = group.set_index("direction")
    anchor_lor = by_direction["LOR"].get("anchor_to_country", np.nan)
    country_lor = by_direction["LOR"].get("country_to_anchor", np.nan)
    anchor_drop = by_direction["band_drop"].get("anchor_to_country", np.nan)
    country_drop = by_direction["band_drop"].get("country_to_anchor", np.nan)

    observed_lors = [value for value in [anchor_lor, country_lor] if pd.notna(value)]
    observed_drops = [value for value in [anchor_drop, country_drop] if pd.notna(value)]

    if not observed_lors:
        return "missing"

    zero_count = sum(float(value) == 0.0 for value in observed_lors)
    if len(observed_lors) == 2 and zero_count == 2:
        return "ruptured"
    if zero_count >= 1:
        return "severely_strained"

    two_band_drops = sum(value >= 2 for value in observed_drops)
    one_band_drops = sum(value >= 1 for value in observed_drops)

    if two_band_drops >= 2:
        return "severely_strained"
    if two_band_drops >= 1:
        return "strained"
    if len(observed_drops) == 2 and one_band_drops == 2:
        return "strained"
    return "normal"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--start-year", type=int, default=2000)
    parser.add_argument("--end-year", type=int, default=2024)
    args = parser.parse_args()

    args.output_dir.mkdir(parents=True, exist_ok=True)

    directed = pd.read_parquet(args.input)
    required = {"country", "anchor", "year", "direction", "LOR", "Focus", "Embassy"}
    missing_columns = required.difference(directed.columns)
    if missing_columns:
        raise KeyError(f"Input is missing required columns: {sorted(missing_columns)}")

    directed = directed[
        directed["year"].between(args.start_year, args.end_year, inclusive="both")
    ].copy()
    directed["LOR"] = pd.to_numeric(directed["LOR"], errors="coerce")
    directed["lor_band"] = directed["LOR"].map(map_lor_to_band)

    duplicate_keys = int(
        directed.duplicated(["country", "anchor", "year", "direction"]).sum()
    )
    if duplicate_keys:
        raise ValueError(f"Found {duplicate_keys} duplicate directed panel keys")

    # Compare with the immediately preceding calendar year. A missing prior year
    # remains missing rather than being bridged across a gap.
    directed = directed.sort_values(["country", "anchor", "direction", "year"])
    group_keys = ["country", "anchor", "direction"]
    directed["previous_year"] = directed.groupby(group_keys)["year"].shift(1)
    directed["previous_lor"] = directed.groupby(group_keys)["LOR"].shift(1)
    directed["previous_band"] = directed.groupby(group_keys)["lor_band"].shift(1)
    directed["consecutive_previous_year"] = directed["previous_year"].eq(
        directed["year"] - 1
    )
    directed.loc[~directed["consecutive_previous_year"], ["previous_lor", "previous_band"]] = np.nan
    directed["band_drop"] = directed["previous_band"] - directed["lor_band"]
    directed["band_gain"] = directed["lor_band"] - directed["previous_band"]

    directed["lor_zero_event"] = directed["LOR"].eq(0)
    directed["focus_three_event"] = pd.to_numeric(
        directed["Focus"], errors="coerce"
    ).eq(3)
    directed["material_downgrade"] = directed["band_drop"].ge(2)
    directed["one_band_downgrade"] = directed["band_drop"].eq(1)
    directed["restoration_from_zero"] = directed["previous_lor"].eq(0) & directed["LOR"].gt(0)
    directed["material_restoration"] = directed["band_gain"].ge(2)

    condition = (
        directed.groupby(["country", "anchor", "year"], group_keys=False)
        .apply(current_source_signal, include_groups=False)
        .rename("drd_condition_signal")
        .reset_index()
    )

    wide_values = directed.pivot_table(
        index=["country", "anchor", "year"],
        columns="direction",
        values=[
            "LOR", "Embassy", "Focus", "lor_band", "previous_lor",
            "previous_band", "band_drop", "band_gain",
        ],
        aggfunc="first",
    )
    wide_values.columns = [f"{field}__{direction}" for field, direction in wide_values.columns]
    wide_values = wide_values.reset_index()
    diagnostic = condition.merge(
        wide_values,
        on=["country", "anchor", "year"],
        how="left",
        validate="one_to_one",
    )

    lor_a = diagnostic.get("LOR__anchor_to_country")
    lor_c = diagnostic.get("LOR__country_to_anchor")
    diagnostic["directional_coverage"] = np.select(
        [
            lor_a.notna() & lor_c.notna(),
            lor_a.notna() & lor_c.isna(),
            lor_a.isna() & lor_c.notna(),
        ],
        ["both_directions", "anchor_to_country_only", "country_to_anchor_only"],
        default="no_observation",
    )
    diagnostic["bilateral_lor_mean"] = diagnostic[
        ["LOR__anchor_to_country", "LOR__country_to_anchor"]
    ].mean(axis=1, skipna=False)
    diagnostic["available_direction_lor_mean"] = diagnostic[
        ["LOR__anchor_to_country", "LOR__country_to_anchor"]
    ].mean(axis=1, skipna=True)
    diagnostic["drd_condition_severity"] = diagnostic["drd_condition_signal"].map(SEVERITY)

    frequency = (
        diagnostic.groupby(["year", "anchor", "drd_condition_signal"], dropna=False)
        .size()
        .rename("country_years")
        .reset_index()
    )
    frequency["drd_condition_severity"] = frequency[
        "drd_condition_signal"
    ].map(SEVERITY)
    frequency = frequency.sort_values(
        ["year", "anchor", "drd_condition_severity"]
    ).reset_index(drop=True)

    lor_zero = directed[directed["lor_zero_event"] | directed["focus_three_event"]].copy()
    downgrades = directed[directed["material_downgrade"] | directed["one_band_downgrade"]].copy()
    restorations = directed[
        directed["restoration_from_zero"] | directed["material_restoration"]
    ].copy()
    one_direction = diagnostic[
        diagnostic["directional_coverage"].isin(
            ["anchor_to_country_only", "country_to_anchor_only"]
        )
    ].copy()

    diagnostic.to_csv(args.output_dir / "drd_condition_diagnostic.csv", index=False)
    frequency.to_csv(args.output_dir / "drd_condition_frequency.csv", index=False)
    downgrades.to_csv(args.output_dir / "drd_material_downgrades.csv", index=False)
    lor_zero.to_csv(args.output_dir / "drd_lor_zero_events.csv", index=False)
    restorations.to_csv(args.output_dir / "drd_restorations.csv", index=False)
    one_direction.to_csv(args.output_dir / "drd_one_direction_only.csv", index=False)

    summary = {
        "input": str(args.input),
        "study_period": [args.start_year, args.end_year],
        "directed_rows": int(len(directed)),
        "country_anchor_years": int(len(diagnostic)),
        "countries": int(diagnostic["country"].nunique()),
        "duplicate_directed_keys": duplicate_keys,
        "coverage_counts": diagnostic["directional_coverage"].value_counts().to_dict(),
        "condition_counts": diagnostic["drd_condition_signal"].value_counts().to_dict(),
        "lor_zero_or_focus_three_rows": int(len(lor_zero)),
        "material_downgrade_rows": int(directed["material_downgrade"].sum()),
        "one_band_downgrade_rows": int(directed["one_band_downgrade"].sum()),
        "restoration_from_zero_rows": int(directed["restoration_from_zero"].sum()),
        "material_restoration_rows": int(directed["material_restoration"].sum()),
    }
    (args.output_dir / "drd_condition_summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    print("=" * 72)
    print("DRD PROVISIONAL CONDITION DIAGNOSTIC")
    print("=" * 72)
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    print("\nRecent condition frequencies:")
    print(frequency[frequency["year"] >= args.end_year - 4].to_string(index=False))
    print("\nTop material downgrades:")
    top_columns = [
        "country", "anchor", "year", "direction", "previous_lor", "LOR",
        "previous_band", "lor_band", "band_drop",
    ]
    print(
        downgrades.sort_values(["band_drop", "year"], ascending=[False, False])
        .head(25)[top_columns]
        .to_string(index=False)
    )
    print("\nOutputs written to:", args.output_dir.resolve())


if __name__ == "__main__":
    main()
