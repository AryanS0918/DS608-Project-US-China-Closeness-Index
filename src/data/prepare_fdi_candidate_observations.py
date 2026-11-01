"""Prepare primary IMF DIP bilateral FDI candidate observations.

Run from the repository root:
    python -u src/data/prepare_fdi_candidate_observations.py

This stage does not calculate an FDI structural-ties score. It selects the
all-financial-instruments, all-entities net-position series, reshapes annual
values to long form, assigns the economic direction of investment, and retains
both reporting perspectives and IMF data types for methodology comparison.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

YEAR_COLUMNS = [str(year) for year in range(2009, 2025)]
PRIMARY_FILTERS = {
    "INSTR_ASSET": "All financial instruments",
    "DI_ENTITY": "All entities",
}
EXPECTED_ACCOUNTING = {
    "Outward": "Net (assets less liabilities)",
    "Inward": "Net (liabilities less assets)",
}


def read_subset(path: Path) -> pd.DataFrame:
    if path.suffix.lower() == ".parquet":
        return pd.read_parquet(path)
    if path.suffix.lower() == ".csv":
        return pd.read_csv(path, low_memory=False)
    raise ValueError(f"Unsupported IMF anchor-subset format: {path.suffix}")


def assign_economic_direction(row: pd.Series) -> str:
    involvement = row["anchor_involvement"]
    direction = row["DI_DIRECTION"]

    if involvement == "reporting_economy":
        return (
            "anchor_to_country"
            if direction == "Outward"
            else "country_to_anchor"
        )
    if involvement == "counterpart_economy":
        return (
            "country_to_anchor"
            if direction == "Outward"
            else "anchor_to_country"
        )
    if involvement == "both_sides_are_anchors":
        return (
            "anchor_to_country"
            if direction == "Outward"
            else "country_to_anchor"
        )
    raise ValueError(f"Unexpected anchor involvement: {involvement!r}")


def assign_reporting_perspective(row: pd.Series) -> str:
    involvement = row["anchor_involvement"]
    if involvement == "reporting_economy":
        return "anchor_report"
    if involvement == "counterpart_economy":
        return "country_report"
    if involvement == "both_sides_are_anchors":
        return "anchor_report"
    raise ValueError(f"Unexpected anchor involvement: {involvement!r}")


def prepare_candidates(frame: pd.DataFrame) -> pd.DataFrame:
    required = {
        "SERIES_CODE",
        "COUNTRY",
        "COUNTERPART_COUNTRY",
        "DV_TYPE",
        "DI_DIRECTION",
        "INSTR_ASSET",
        "DI_ENTITY",
        "ACCOUNTING_ENTRY",
        "UNIT",
        "anchor_involvement",
        "anchor",
        *YEAR_COLUMNS,
    }
    missing = required.difference(frame.columns)
    if missing:
        raise KeyError(f"IMF anchor subset is missing fields: {sorted(missing)}")

    selected = frame.copy()
    for column, value in PRIMARY_FILTERS.items():
        selected = selected[selected[column].eq(value)]
    selected = selected[
        selected.apply(
            lambda row: row["ACCOUNTING_ENTRY"]
            == EXPECTED_ACCOUNTING.get(row["DI_DIRECTION"]),
            axis=1,
        )
    ].copy()

    selected["economic_direction"] = selected.apply(
        assign_economic_direction,
        axis=1,
    )
    selected["reporting_perspective"] = selected.apply(
        assign_reporting_perspective,
        axis=1,
    )
    selected["country_source_name"] = selected.apply(
        lambda row: (
            row["COUNTERPART_COUNTRY"]
            if row["anchor_involvement"] == "reporting_economy"
            else row["COUNTRY"]
        ),
        axis=1,
    )

    identifier_columns = [
        "SERIES_CODE",
        "COUNTRY",
        "COUNTERPART_COUNTRY",
        "country_source_name",
        "anchor",
        "anchor_involvement",
        "reporting_perspective",
        "economic_direction",
        "DV_TYPE",
        "DI_DIRECTION",
        "INSTR_ASSET",
        "DI_ENTITY",
        "ACCOUNTING_ENTRY",
        "UNIT",
    ]
    long = selected.melt(
        id_vars=identifier_columns,
        value_vars=YEAR_COLUMNS,
        var_name="year",
        value_name="fdi_position_usd_millions",
    )
    long["year"] = long["year"].astype(int)
    long["fdi_position_usd_millions"] = pd.to_numeric(
        long["fdi_position_usd_millions"],
        errors="coerce",
    )
    long["observed"] = long["fdi_position_usd_millions"].notna()
    long["negative"] = long["fdi_position_usd_millions"].lt(0)
    long["zero"] = long["fdi_position_usd_millions"].eq(0)
    return long.sort_values(
        [
            "year",
            "anchor",
            "country_source_name",
            "economic_direction",
            "reporting_perspective",
            "DV_TYPE",
        ]
    ).reset_index(drop=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("data/interim/fdi/imf_dip_anchor_series.parquet"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/interim/fdi/imf_dip_primary_candidates.parquet"),
    )
    parser.add_argument(
        "--report-directory",
        type=Path,
        default=Path("outputs/tables/fdi"),
    )
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.report_directory.mkdir(parents=True, exist_ok=True)

    source = read_subset(args.input)
    candidates = prepare_candidates(source)
    candidates.to_parquet(args.output, index=False)

    observed = candidates[candidates["observed"]].copy()
    coverage = (
        candidates.groupby(
            [
                "year",
                "anchor",
                "economic_direction",
                "reporting_perspective",
                "DV_TYPE",
            ],
            dropna=False,
        )
        .agg(
            series_rows=("SERIES_CODE", "size"),
            observed_values=("observed", "sum"),
            countries=("country_source_name", "nunique"),
            negative_values=("negative", "sum"),
            zero_values=("zero", "sum"),
        )
        .reset_index()
    )
    duplicate_profile = (
        observed.groupby(
            [
                "country_source_name",
                "anchor",
                "year",
                "economic_direction",
                "reporting_perspective",
                "DV_TYPE",
            ],
            dropna=False,
        )
        .size()
        .rename("observations")
        .reset_index()
    )
    duplicate_profile = duplicate_profile[
        duplicate_profile["observations"].gt(1)
    ]

    summary = {
        "source_series_rows": int(len(source)),
        "selected_primary_series_rows": int(
            candidates["SERIES_CODE"].nunique()
        ),
        "candidate_long_rows": int(len(candidates)),
        "observed_candidate_values": int(candidates["observed"].sum()),
        "negative_candidate_values": int(candidates["negative"].sum()),
        "zero_candidate_values": int(candidates["zero"].sum()),
        "duplicate_candidate_keys": int(len(duplicate_profile)),
        "years": [int(candidates["year"].min()), int(candidates["year"].max())],
        "economic_direction_counts": observed[
            "economic_direction"
        ].value_counts().to_dict(),
        "reporting_perspective_counts": observed[
            "reporting_perspective"
        ].value_counts().to_dict(),
        "data_type_counts": observed["DV_TYPE"].value_counts().to_dict(),
    }

    coverage.to_csv(
        args.report_directory / "imf_dip_primary_candidate_coverage.csv",
        index=False,
    )
    duplicate_profile.to_csv(
        args.report_directory / "imf_dip_primary_candidate_duplicates.csv",
        index=False,
    )
    (
        args.report_directory / "imf_dip_primary_candidate_summary.json"
    ).write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print("=" * 72)
    print("IMF DIP PRIMARY FDI CANDIDATES")
    print("=" * 72)
    print(json.dumps(summary, indent=2))
    print("\nCandidate output:", args.output)
    print("Reports directory:", args.report_directory)


if __name__ == "__main__":
    main()
