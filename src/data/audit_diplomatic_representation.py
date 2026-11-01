"""Audit the Diplomatic Representation Database for US-China index use.

Complete runnable example.

Run from the repository root:
    python -u src/data/audit_diplomatic_representation.py

The script does not overwrite the source workbook. It writes compact audit
outputs under outputs/tables/diplomatic_representation/ and a filtered,
reproducible anchor-country panel under data/interim/relations/.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import numpy as np
import pandas as pd

DEFAULT_SOURCE = Path(
    "data/sources/relations/diplomatic_representation/"
    "Diplometrics_Diplomatic-Representation_1960-2024_20250825.xlsx"
)


def key(text: object) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(text).strip().lower())


def find_column(columns: list[str], candidates: list[str], required: bool = True) -> str | None:
    keyed = {key(column): column for column in columns}
    for candidate in candidates:
        if key(candidate) in keyed:
            return keyed[key(candidate)]
    if required:
        raise KeyError(
            f"Could not identify required field from candidates {candidates}. "
            f"Available fields: {columns}"
        )
    return None


def normalize_country(value: object) -> str:
    text = re.sub(r"\s+", " ", str(value).strip())
    aliases = {
        "United States of America": "United States",
        "USA": "United States",
        "US": "United States",
        "People's Republic of China": "China",
        "China, People's Republic of": "China",
        "PRC": "China",
    }
    return aliases.get(text, text)


def safe_mode(series: pd.Series):
    mode = series.dropna().mode()
    return mode.iloc[0] if not mode.empty else pd.NA


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("outputs/tables/diplomatic_representation"),
    )
    parser.add_argument(
        "--interim-dir",
        type=Path,
        default=Path("data/interim/relations"),
    )
    parser.add_argument("--start-year", type=int, default=2000)
    parser.add_argument("--end-year", type=int, default=2024)
    args = parser.parse_args()

    args.output_dir.mkdir(parents=True, exist_ok=True)
    args.interim_dir.mkdir(parents=True, exist_ok=True)

    excel = pd.ExcelFile(args.source, engine="openpyxl")
    if len(excel.sheet_names) != 1:
        print("Workbook sheets:", excel.sheet_names)
    sheet = excel.sheet_names[0]
    data = pd.read_excel(args.source, sheet_name=sheet, engine="openpyxl")
    data.columns = [str(column).strip() for column in data.columns]

    columns = list(data.columns)
    year_col = find_column(columns, ["Year"])
    sender_col = find_column(columns, ["SendingCountry", "Sender", "CountryA"])
    destination_col = find_column(columns, ["Destination", "ReceivingCountry", "CountryB"])

    # These are discovered permissively because naming may vary by release.
    embassy_col = find_column(
        columns,
        ["EmbassyCode", "Embassy", "EmbassyNew", "EmbassyLevel"],
        required=False,
    )
    focus_col = find_column(
        columns,
        ["FocusCode", "Focus", "DiplomaticFocus"],
        required=False,
    )
    representation_col = find_column(
        columns,
        [
            "RepresentationLevelIndex",
            "RepresentationLevel",
            "LevelOfRepresentation",
            "RepresentationIndex",
            "DiplomaticRepresentationIndex",
        ],
        required=False,
    )

    data[year_col] = pd.to_numeric(data[year_col], errors="coerce").astype("Int64")
    data["sending_country_standard"] = data[sender_col].map(normalize_country)
    data["destination_standard"] = data[destination_col].map(normalize_country)

    key_cols = [year_col, "sending_country_standard", "destination_standard"]
    exact_duplicates = int(data.duplicated().sum())
    duplicate_keys = int(data.duplicated(key_cols, keep=False).sum())

    schema_rows = []
    for column in data.columns:
        series = data[column]
        schema_rows.append(
            {
                "column": column,
                "dtype": str(series.dtype),
                "rows": len(series),
                "non_missing": int(series.notna().sum()),
                "missing": int(series.isna().sum()),
                "missing_pct": round(float(series.isna().mean() * 100), 4),
                "unique_non_missing": int(series.nunique(dropna=True)),
            }
        )
    schema = pd.DataFrame(schema_rows)

    anchors = {"United States", "China"}
    study = data[data[year_col].between(args.start_year, args.end_year, inclusive="both")].copy()
    anchor_rows = study[
        study["sending_country_standard"].isin(anchors)
        | study["destination_standard"].isin(anchors)
    ].copy()

    # Exclude anchor-anchor and same-country observations from country-anchor output.
    anchor_rows = anchor_rows[
        anchor_rows["sending_country_standard"] != anchor_rows["destination_standard"]
    ].copy()

    def classify(row: pd.Series) -> tuple[str, str, str]:
        sender = row["sending_country_standard"]
        destination = row["destination_standard"]
        if sender in anchors:
            return sender, destination, "anchor_to_country"
        return destination, sender, "country_to_anchor"

    classified = anchor_rows.apply(classify, axis=1, result_type="expand")
    classified.columns = ["anchor", "country", "direction"]
    anchor_rows = pd.concat([anchor_rows, classified], axis=1)

    anchor_key = ["country", "anchor", year_col, "direction"]
    anchor_duplicate_keys = int(anchor_rows.duplicated(anchor_key, keep=False).sum())

    measure_columns = [column for column in data.columns if column not in {
        sender_col,
        destination_col,
        year_col,
        "sending_country_standard",
        "destination_standard",
    }]

    coverage = (
        anchor_rows.groupby(["anchor", "direction", year_col], dropna=False)
        .agg(
            observations=("country", "size"),
            countries=("country", "nunique"),
        )
        .reset_index()
        .sort_values([year_col, "anchor", "direction"])
    )

    expected_directions = pd.MultiIndex.from_product(
        [
            sorted(anchor_rows["country"].dropna().unique()),
            sorted(anchors),
            range(args.start_year, args.end_year + 1),
            ["anchor_to_country", "country_to_anchor"],
        ],
        names=["country", "anchor", year_col, "direction"],
    ).to_frame(index=False)
    observed = anchor_rows[anchor_key].drop_duplicates()
    completeness = expected_directions.merge(
        observed.assign(observed=True),
        on=anchor_key,
        how="left",
    )
    completeness["observed"] = completeness["observed"].fillna(False)
    completeness_summary = (
        completeness.groupby(["anchor", "direction", year_col])
        .agg(
            expected=("observed", "size"),
            observed=("observed", "sum"),
        )
        .reset_index()
    )
    completeness_summary["coverage_rate"] = (
        completeness_summary["observed"] / completeness_summary["expected"]
    )

    value_profiles = []
    for column in measure_columns:
        counts = (
            anchor_rows[column]
            .value_counts(dropna=False)
            .rename_axis("value")
            .reset_index(name="count")
        )
        counts["column"] = column
        counts["value"] = counts["value"].astype("string")
        value_profiles.append(counts[["column", "value", "count"]])
    value_profiles_df = (
        pd.concat(value_profiles, ignore_index=True)
        if value_profiles
        else pd.DataFrame(columns=["column", "value", "count"])
    )

    # One row per directed country-anchor-year. If duplicate keys exist, preserve
    # a deterministic modal record for audit while reporting the duplication.
    aggregations = {column: safe_mode for column in measure_columns}
    panel = (
        anchor_rows.groupby(anchor_key, dropna=False)
        .agg(aggregations)
        .reset_index()
        .sort_values([year_col, "country", "anchor", "direction"])
    )
    panel = panel.rename(columns={year_col: "year"})

    # Form a wide relationship profile retaining each direction separately.
    value_cols = [column for column in measure_columns if column in panel.columns]
    wide = panel.pivot_table(
        index=["country", "anchor", "year"],
        columns="direction",
        values=value_cols,
        aggfunc="first",
    )
    wide.columns = [f"{column}__{direction}" for column, direction in wide.columns]
    wide = wide.reset_index().sort_values(["year", "country", "anchor"])

    # Summary diagnostics.
    summary = {
        "source": str(args.source),
        "sheet": sheet,
        "rows": int(len(data)),
        "columns": int(len(data.columns)),
        "year_min": int(data[year_col].min()),
        "year_max": int(data[year_col].max()),
        "sending_countries": int(data["sending_country_standard"].nunique()),
        "destinations": int(data["destination_standard"].nunique()),
        "exact_duplicate_rows": exact_duplicates,
        "duplicate_directed_dyad_year_rows": duplicate_keys,
        "anchor_rows_2000_2024": int(len(anchor_rows)),
        "anchor_duplicate_key_rows": anchor_duplicate_keys,
        "countries_in_anchor_panel": int(anchor_rows["country"].nunique()),
        "identified_columns": {
            "year": year_col,
            "sender": sender_col,
            "destination": destination_col,
            "embassy": embassy_col,
            "focus": focus_col,
            "representation": representation_col,
        },
        "measure_columns": measure_columns,
    }

    schema.to_csv(args.output_dir / "drd_schema.csv", index=False)
    coverage.to_csv(args.output_dir / "drd_anchor_coverage_by_year.csv", index=False)
    completeness_summary.to_csv(
        args.output_dir / "drd_anchor_completeness_by_year.csv", index=False
    )
    value_profiles_df.to_csv(args.output_dir / "drd_anchor_value_profiles.csv", index=False)
    panel.to_parquet(args.interim_dir / "drd_anchor_directed_country_year.parquet", index=False)
    wide.to_parquet(args.interim_dir / "drd_anchor_country_year.parquet", index=False)
    (args.output_dir / "drd_audit_summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )

    print("=" * 72)
    print("DIPLOMATIC REPRESENTATION DATABASE AUDIT")
    print("=" * 72)
    for field, value in summary.items():
        if field not in {"measure_columns", "identified_columns"}:
            print(f"{field}: {value}")
    print("identified_columns:", json.dumps(summary["identified_columns"], ensure_ascii=False))
    print("measure_columns:", measure_columns)
    print("\nLatest coverage rows:")
    print(coverage[coverage[year_col] >= max(args.end_year - 4, args.start_year)].to_string(index=False))
    print("\nLatest completeness rows:")
    print(
        completeness_summary[
            completeness_summary[year_col] >= max(args.end_year - 4, args.start_year)
        ].to_string(index=False)
    )
    print("\nOutputs written to:", args.output_dir.resolve())
    print("Interim panels written to:", args.interim_dir.resolve())


if __name__ == "__main__":
    main()
