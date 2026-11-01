"""Extract and inventory China/US-relevant series from the IMF DIP bulk CSV.

Run from the repository root:
    python -u src/data/inventory_imf_fdi.py

The 2+ GB source remains local and ignored. The script streams the wide CSV in
chunks, retains every series where either COUNTRY or COUNTERPART_COUNTRY is
China or the United States, writes a compact Parquet subset, and produces
small audit files suitable for review and upload.
"""
from __future__ import annotations

import argparse
import json
import re
import unicodedata
from pathlib import Path

import pandas as pd

METADATA_COLUMNS = [
    "DATASET",
    "SERIES_CODE",
    "OBS_MEASURE",
    "COUNTRY",
    "DV_TYPE",
    "INDICATOR",
    "COUNTERPART_COUNTRY",
    "FREQUENCY",
    "SCALE",
    "DECIMALS_DISPLAYED",
    "DI_DIRECTION",
    "FUNCTIONAL_CAT",
    "INSTR_ASSET",
    "DI_ENTITY",
    "ACCOUNTING_ENTRY",
    "UNIT",
    "OVERLAP",
    "GROUP_FLAG",
    "SERIES_NAME",
]
YEAR_COLUMNS = [str(year) for year in range(2009, 2025)]
USE_COLUMNS = METADATA_COLUMNS + YEAR_COLUMNS

ANCHOR_ALIASES = {
    "china": "China",
    "china people s republic of": "China",
    "china pr mainland": "China",
    "china p r mainland": "China",
    "united states": "United States",
    "united states of america": "United States",
    "usa": "United States",
}


def normalize_name(value: object) -> str:
    text = unicodedata.normalize("NFKD", str(value))
    text = "".join(
        character
        for character in text
        if not unicodedata.combining(character)
    )
    text = text.lower().replace("&", " and ")
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def canonical_anchor(series: pd.Series) -> pd.Series:
    normalized = series.astype("string").map(normalize_name)
    return normalized.map(ANCHOR_ALIASES)


def locate_source(directory: Path) -> Path:
    candidates = sorted(
        path
        for path in directory.glob("*.csv")
        if path.is_file()
    )
    if len(candidates) != 1:
        names = [path.name for path in candidates]
        raise ValueError(
            "Expected exactly one IMF DIP CSV under "
            f"{directory}. Found: {names}"
        )
    return candidates[0]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source-directory",
        type=Path,
        default=Path("data/sources/IMF DIP"),
    )
    parser.add_argument(
        "--interim-directory",
        type=Path,
        default=Path("data/interim/fdi"),
    )
    parser.add_argument(
        "--report-directory",
        type=Path,
        default=Path("outputs/tables/fdi"),
    )
    parser.add_argument(
        "--chunk-size",
        type=int,
        default=50_000,
    )
    args = parser.parse_args()

    source = locate_source(args.source_directory)
    args.interim_directory.mkdir(parents=True, exist_ok=True)
    args.report_directory.mkdir(parents=True, exist_ok=True)

    subset_path = args.interim_directory / "imf_dip_anchor_series.parquet"
    if subset_path.exists():
        subset_path.unlink()

    anchor_frames: list[pd.DataFrame] = []
    candidate_names: set[str] = set()
    chunks_read = 0
    rows_read = 0
    rows_retained = 0

    reader = pd.read_csv(
        source,
        usecols=USE_COLUMNS,
        chunksize=args.chunk_size,
        low_memory=False,
        encoding="utf-8-sig",
    )

    for chunk in reader:
        chunks_read += 1
        rows_read += len(chunk)

        country_normalized = chunk["COUNTRY"].astype("string").map(
            normalize_name
        )
        counterpart_normalized = (
            chunk["COUNTERPART_COUNTRY"]
            .astype("string")
            .map(normalize_name)
        )

        country_candidate = country_normalized.str.contains(
            r"china|united states|usa",
            regex=True,
            na=False,
        )
        counterpart_candidate = counterpart_normalized.str.contains(
            r"china|united states|usa",
            regex=True,
            na=False,
        )
        candidate_names.update(
            chunk.loc[country_candidate, "COUNTRY"]
            .dropna()
            .astype(str)
            .tolist()
        )
        candidate_names.update(
            chunk.loc[counterpart_candidate, "COUNTERPART_COUNTRY"]
            .dropna()
            .astype(str)
            .tolist()
        )

        country_anchor = country_normalized.map(ANCHOR_ALIASES)
        counterpart_anchor = counterpart_normalized.map(ANCHOR_ALIASES)
        retain = country_anchor.notna() | counterpart_anchor.notna()

        selected = chunk.loc[retain].copy()
        if not selected.empty:
            selected["country_anchor"] = country_anchor.loc[retain]
            selected["counterpart_anchor"] = (
                counterpart_anchor.loc[retain]
            )
            anchor_frames.append(selected)
            rows_retained += len(selected)

        print(
            f"Chunk {chunks_read:>3}: "
            f"read {rows_read:,} rows; "
            f"retained {rows_retained:,} rows",
            flush=True,
        )

    if not anchor_frames:
        raise ValueError("No China/US anchor-relevant IMF DIP rows found")

    subset = pd.concat(anchor_frames, ignore_index=True)

    subset["anchor_involvement"] = ""
    subset.loc[
        subset["country_anchor"].notna()
        & subset["counterpart_anchor"].isna(),
        "anchor_involvement",
    ] = "reporting_economy"
    subset.loc[
        subset["country_anchor"].isna()
        & subset["counterpart_anchor"].notna(),
        "anchor_involvement",
    ] = "counterpart_economy"
    subset.loc[
        subset["country_anchor"].notna()
        & subset["counterpart_anchor"].notna(),
        "anchor_involvement",
    ] = "both_sides_are_anchors"
    subset["anchor"] = subset["country_anchor"].fillna(
        subset["counterpart_anchor"]
    )

    subset.to_parquet(subset_path, index=False)

    id_columns = [
        column
        for column in subset.columns
        if column not in YEAR_COLUMNS
    ]
    long = subset.melt(
        id_vars=id_columns,
        value_vars=YEAR_COLUMNS,
        var_name="year",
        value_name="value_usd_millions",
    )
    long["year"] = pd.to_numeric(
        long["year"],
        errors="raise",
    ).astype(int)
    long["value_usd_millions"] = pd.to_numeric(
        long["value_usd_millions"],
        errors="coerce",
    )

    observed = long[long["value_usd_millions"].notna()].copy()

    dimension_columns = [
        "DV_TYPE",
        "DI_DIRECTION",
        "INSTR_ASSET",
        "DI_ENTITY",
        "ACCOUNTING_ENTRY",
        "UNIT",
        "SCALE",
        "GROUP_FLAG",
        "anchor_involvement",
        "anchor",
    ]
    profiles: list[pd.DataFrame] = []
    for dimension in dimension_columns:
        profile = (
            subset[dimension]
            .fillna("<missing>")
            .astype(str)
            .value_counts(dropna=False)
            .rename_axis("value")
            .reset_index(name="series_rows")
        )
        profile.insert(0, "dimension", dimension)
        profiles.append(profile)
    dimension_profile = pd.concat(profiles, ignore_index=True)

    coverage = (
        observed.groupby(
            [
                "year",
                "anchor",
                "anchor_involvement",
                "DV_TYPE",
                "DI_DIRECTION",
            ],
            dropna=False,
        )
        .agg(
            observed_values=("value_usd_millions", "size"),
            reporting_economies=("COUNTRY", "nunique"),
            counterpart_economies=(
                "COUNTERPART_COUNTRY",
                "nunique",
            ),
            negative_values=(
                "value_usd_millions",
                lambda values: int(values.lt(0).sum()),
            ),
            zero_values=(
                "value_usd_millions",
                lambda values: int(values.eq(0).sum()),
            ),
        )
        .reset_index()
    )

    indicator_profile = (
        subset.groupby(
            [
                "DI_DIRECTION",
                "DV_TYPE",
                "INSTR_ASSET",
                "DI_ENTITY",
                "ACCOUNTING_ENTRY",
                "INDICATOR",
                "SERIES_NAME",
            ],
            dropna=False,
        )
        .size()
        .rename("series_rows")
        .reset_index()
        .sort_values("series_rows", ascending=False)
    )

    anchor_countries = (
        observed.groupby(
            [
                "year",
                "anchor",
                "anchor_involvement",
            ],
            dropna=False,
        )
        .agg(
            observed_values=("value_usd_millions", "size"),
            unique_series=("SERIES_CODE", "nunique"),
            countries=("COUNTRY", "nunique"),
            counterparts=("COUNTERPART_COUNTRY", "nunique"),
        )
        .reset_index()
    )

    candidate_output = pd.DataFrame(
        {"candidate_name": sorted(candidate_names)}
    )
    candidate_output["normalized_name"] = (
        candidate_output["candidate_name"].map(normalize_name)
    )
    candidate_output["recognized_anchor"] = (
        candidate_output["normalized_name"].map(ANCHOR_ALIASES)
    )

    dimension_profile.to_csv(
        args.report_directory / "imf_dip_anchor_dimension_profile.csv",
        index=False,
    )
    indicator_profile.to_csv(
        args.report_directory / "imf_dip_anchor_indicator_profile.csv",
        index=False,
    )
    coverage.to_csv(
        args.report_directory / "imf_dip_anchor_coverage_by_year.csv",
        index=False,
    )
    anchor_countries.to_csv(
        args.report_directory / "imf_dip_anchor_observation_profile.csv",
        index=False,
    )
    candidate_output.to_csv(
        args.report_directory / "imf_dip_anchor_name_candidates.csv",
        index=False,
    )

    summary = {
        "source_file": source.name,
        "source_size_bytes": source.stat().st_size,
        "source_years": [2009, 2024],
        "source_rows_read": rows_read,
        "source_chunks_read": chunks_read,
        "anchor_series_rows_retained": int(len(subset)),
        "anchor_long_rows": int(len(long)),
        "anchor_observed_values": int(len(observed)),
        "recognized_anchor_names": sorted(
            set(ANCHOR_ALIASES.values())
        ),
        "unrecognized_anchor_like_names": (
            candidate_output.loc[
                candidate_output["recognized_anchor"].isna(),
                "candidate_name",
            ]
            .astype(str)
            .tolist()
        ),
        "dv_type_counts": (
            subset["DV_TYPE"].value_counts(dropna=False).to_dict()
        ),
        "direction_counts": (
            subset["DI_DIRECTION"]
            .value_counts(dropna=False)
            .to_dict()
        ),
        "instrument_counts": (
            subset["INSTR_ASSET"]
            .value_counts(dropna=False)
            .to_dict()
        ),
        "entity_counts": (
            subset["DI_ENTITY"]
            .value_counts(dropna=False)
            .to_dict()
        ),
        "accounting_entry_counts": (
            subset["ACCOUNTING_ENTRY"]
            .value_counts(dropna=False)
            .to_dict()
        ),
        "negative_observed_values": int(
            observed["value_usd_millions"].lt(0).sum()
        ),
        "zero_observed_values": int(
            observed["value_usd_millions"].eq(0).sum()
        ),
        "interim_subset": str(
            subset_path
        ),
    }

    (
        args.report_directory / "imf_dip_anchor_inventory_summary.json"
    ).write_text(
        json.dumps(summary, indent=2),
        encoding="utf-8",
    )

    print("=" * 72)
    print("IMF DIP CHINA/US ANCHOR INVENTORY")
    print("=" * 72)
    print(json.dumps(summary, indent=2))
    print("\nInterim subset:", subset_path)
    print("Reports:", args.report_directory)


if __name__ == "__main__":
    main()
