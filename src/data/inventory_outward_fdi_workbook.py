"""Inventory the national outward-direct-investment workbook.

Run from the repository root:
    python -u src/data/inventory_outward_fdi_workbook.py

The script reads the Annual sheet, inventories the China ODI stock, US ODI
stock, prototype US-minus-China block, and World Bank GDP block, and writes
reproducible diagnostics without modifying the source workbook.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

BLOCK_LABELS = {
    "China Outward Direct Investment": "china_odi_stock",
    "US Outward Direct Investment": "us_odi_stock",
    "US Less China Outward Direct Investment": "prototype_us_minus_china",
    "World Bank Nominal GDP": "world_bank_nominal_gdp",
}
AGGREGATE_NAMES = {
    "africa", "all countries total", "asia", "east asia & pacific",
    "europe", "european union", "latin america", "middle east",
    "north america", "oceania", "other western hemisphere",
    "south and central america", "total", "world",
}
MISSING_TOKENS = {"", "n.s.", "na", "n/a", "nan", "-"}


def find_block_bounds(frame: pd.DataFrame) -> list[dict[str, Any]]:
    starts = []
    for column, value in enumerate(frame.iloc[0]):
        if value in BLOCK_LABELS:
            starts.append((column, str(value)))
    starts.sort()
    blocks = []
    for index, (start, label) in enumerate(starts):
        end = starts[index + 1][0] - 1 if index + 1 < len(starts) else frame.shape[1] - 1
        blocks.append({"label": label, "block": BLOCK_LABELS[label], "start": start, "end": end})
    return blocks


def stock_rows(frame: pd.DataFrame) -> pd.DataFrame:
    rows = frame.iloc[6:33].copy()
    rows[0] = pd.to_datetime(rows[0], errors="coerce")
    rows = rows[rows[0].notna()].copy()
    rows["year"] = rows[0].dt.year.astype(int)
    return rows


def classify_name(name: Any) -> str:
    if pd.isna(name):
        return "blank"
    normalized = str(name).strip().lower()
    if normalized in AGGREGATE_NAMES:
        return "aggregate"
    aggregate_terms = [
        "income", "region", "countries", "world", "africa", "asia",
        "europe", "america", "caribbean", "oecd", "heavily indebted",
        "least developed", "small states", "demographic dividend",
    ]
    if any(term in normalized for term in aggregate_terms):
        return "aggregate_or_group"
    return "economy_candidate"


def numeric_value(value: Any) -> float:
    if pd.isna(value):
        return np.nan
    if isinstance(value, str) and value.strip().lower() in MISSING_TOKENS:
        return np.nan
    return pd.to_numeric(value, errors="coerce")


def extract_block(frame: pd.DataFrame, rows: pd.DataFrame, block: dict[str, Any]) -> tuple[pd.DataFrame, pd.DataFrame]:
    column_rows = []
    observation_rows = []
    for column in range(block["start"], block["end"] + 1):
        country = frame.iat[4, column]
        unit = frame.iat[5, column]
        category = classify_name(country)
        series = rows[["year", column]].copy()
        series["value"] = series[column].map(numeric_value)
        series = series.drop(columns=[column])
        observed = series["value"].notna()
        column_rows.append({
            "block": block["block"],
            "source_label": block["label"],
            "excel_column_index_zero_based": column,
            "country_source_name": country,
            "unit": unit,
            "name_classification": category,
            "first_observed_year": int(series.loc[observed, "year"].min()) if observed.any() else None,
            "last_observed_year": int(series.loc[observed, "year"].max()) if observed.any() else None,
            "observed_values": int(observed.sum()),
            "negative_values": int(series["value"].lt(0).sum()),
            "zero_values": int(series["value"].eq(0).sum()),
        })
        for row in series.itertuples(index=False):
            observation_rows.append({
                "block": block["block"],
                "country_source_name": country,
                "unit": unit,
                "name_classification": category,
                "year": int(row.year),
                "value": row.value,
                "observed": bool(pd.notna(row.value)),
                "negative": bool(pd.notna(row.value) and row.value < 0),
                "zero": bool(pd.notna(row.value) and row.value == 0),
            })
    return pd.DataFrame(column_rows), pd.DataFrame(observation_rows)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--workbook",
        type=Path,
        default=Path("data/sources/fdi/Outward Direct Investment.xlsx"),
    )
    parser.add_argument(
        "--report-directory",
        type=Path,
        default=Path("outputs/tables/fdi_national_sources"),
    )
    args = parser.parse_args()
    args.report_directory.mkdir(parents=True, exist_ok=True)

    frame = pd.read_excel(args.workbook, sheet_name="Annual", header=None, engine="openpyxl")
    blocks = find_block_bounds(frame)
    rows = stock_rows(frame)

    inventories = []
    observations = []
    for block in blocks:
        inventory, observed = extract_block(frame, rows, block)
        inventories.append(inventory)
        observations.append(observed)
    inventory = pd.concat(inventories, ignore_index=True)
    long = pd.concat(observations, ignore_index=True)

    coverage = (
        long.groupby(["block", "year"], dropna=False)
        .agg(
            columns=("country_source_name", "size"),
            observed_values=("observed", "sum"),
            negative_values=("negative", "sum"),
            zero_values=("zero", "sum"),
            economy_candidates=(
                "name_classification",
                lambda values: int(values.eq("economy_candidate").sum()),
            ),
        )
        .reset_index()
    )
    duplicates = (
        inventory[inventory["country_source_name"].notna()]
        .groupby(["block", "country_source_name"], dropna=False)
        .size()
        .rename("columns")
        .reset_index()
    )
    duplicates = duplicates[duplicates["columns"].gt(1)]

    summary = {
        "source_file": args.workbook.name,
        "source_size_bytes": int(args.workbook.stat().st_size),
        "sheet_names": pd.ExcelFile(args.workbook, engine="openpyxl").sheet_names,
        "annual_shape": [int(frame.shape[0]), int(frame.shape[1])],
        "stock_years": [int(rows["year"].min()), int(rows["year"].max())],
        "blocks": blocks,
        "block_column_counts": inventory.groupby("block").size().to_dict(),
        "block_observed_values": long.groupby("block")["observed"].sum().astype(int).to_dict(),
        "block_negative_values": long.groupby("block")["negative"].sum().astype(int).to_dict(),
        "block_zero_values": long.groupby("block")["zero"].sum().astype(int).to_dict(),
        "duplicate_country_columns": int(len(duplicates)),
    }

    inventory.to_csv(args.report_directory / "outward_fdi_column_inventory.csv", index=False)
    long.to_csv(args.report_directory / "outward_fdi_stock_long.csv", index=False)
    coverage.to_csv(args.report_directory / "outward_fdi_coverage_by_year.csv", index=False)
    duplicates.to_csv(args.report_directory / "outward_fdi_duplicate_country_columns.csv", index=False)
    (args.report_directory / "outward_fdi_inventory_summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )

    print("=" * 72)
    print("NATIONAL OUTWARD FDI WORKBOOK INVENTORY")
    print("=" * 72)
    print(json.dumps(summary, indent=2))
    print("\nReports:", args.report_directory)


if __name__ == "__main__":
    main()
