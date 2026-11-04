"""Build the canonical country-year trade-orientation component.

Run from the repository root:
    python src/data/build_trade_orientation.py

The upstream collector creates a broad UN Comtrade reporter-year panel. This
builder applies the canonical project universe, preserves reporter-side and
mirror-side provenance, and retains missing trade evidence as missing rather
than zero. The complete-data baseline period is 2004-2024; 2025 is retained
only as a provisional latest-year extension.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_START = 2004
PROJECT_END = 2025
COMPARABLE_END = 2024
KEYS = ["country_iso3", "year"]
FLOW_COLUMNS = [
    "imports_from_china",
    "exports_to_china",
    "imports_from_us",
    "exports_to_us",
]
SOURCE_COLUMNS = [f"{column}_source" for column in FLOW_COLUMNS]


def require_columns(frame: pd.DataFrame, required: set[str], label: str) -> None:
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(f"{label} missing required columns: {missing}")


def build_universe(country_master: pd.DataFrame) -> pd.DataFrame:
    require_columns(
        country_master,
        {
            "iso3",
            "country_name",
            "preferred_country_name",
            "first_valid_year",
            "last_valid_year",
            "baseline_index_eligible",
        },
        "Country master",
    )
    eligible = country_master.loc[
        country_master["baseline_index_eligible"].eq(True)
    ].copy()
    rows: list[dict] = []
    for row in eligible.itertuples(index=False):
        first = (
            PROJECT_START
            if pd.isna(row.first_valid_year)
            else max(PROJECT_START, int(row.first_valid_year))
        )
        last = (
            PROJECT_END
            if pd.isna(row.last_valid_year)
            else min(PROJECT_END, int(row.last_valid_year))
        )
        for year in range(first, last + 1):
            rows.append(
                {
                    "country_iso3": row.iso3,
                    "country_name": row.country_name,
                    "preferred_country_name": row.preferred_country_name,
                    "year": year,
                }
            )
    universe = pd.DataFrame(rows).sort_values(KEYS).reset_index(drop=True)
    if universe.duplicated(KEYS).any():
        raise ValueError("Canonical trade universe contains duplicate keys.")
    return universe


def prepare_trade_source(trade_raw: pd.DataFrame) -> pd.DataFrame:
    required = {
        "year",
        "reporter_iso",
        "reporter_name",
        *FLOW_COLUMNS,
        *SOURCE_COLUMNS,
        "china_total_trade_usd",
        "us_total_trade_usd",
        "available_flow_count",
        "complete_four_flow_record",
        "trade_orientation_score",
        "is_anchor_country",
    }
    require_columns(trade_raw, required, "Trade source panel")
    source = trade_raw.loc[
        trade_raw["year"].between(PROJECT_START, PROJECT_END)
    ].copy()
    if source["reporter_iso"].isna().any():
        raise ValueError("Trade source contains missing reporter ISO3 codes.")
    if source.duplicated(["reporter_iso", "year"]).any():
        raise ValueError("Trade source contains duplicate reporter-year keys.")
    score_available = source["trade_orientation_score"].notna()
    complete = source["complete_four_flow_record"].eq(True)
    non_anchor = ~source["is_anchor_country"].fillna(False).astype(bool)
    if not score_available.eq(complete & non_anchor).all():
        raise ValueError("Trade score availability disagrees with completeness or anchor rules.")
    if not source["trade_orientation_score"].dropna().between(-1, 1).all():
        raise ValueError("Trade orientation scores fall outside [-1, 1].")
    return source


def build_trade_orientation(
    trade_raw: pd.DataFrame,
    country_master: pd.DataFrame,
) -> pd.DataFrame:
    universe = build_universe(country_master)
    source = prepare_trade_source(trade_raw)
    keep = [
        "reporter_iso",
        "year",
        "reporter_name",
        *FLOW_COLUMNS,
        *SOURCE_COLUMNS,
        "china_total_trade_usd",
        "us_total_trade_usd",
        "available_flow_count",
        "complete_four_flow_record",
        "trade_orientation_score",
    ]
    panel = universe.merge(
        source[keep],
        left_on=["country_iso3", "year"],
        right_on=["reporter_iso", "year"],
        how="left",
        validate="one_to_one",
        indicator="trade_source_merge_status",
    )

    source_row_available = panel["trade_source_merge_status"].eq("both")
    score_available = panel["trade_orientation_score"].notna()
    complete = panel["complete_four_flow_record"].eq(True)
    flow_count = panel[FLOW_COLUMNS].notna().sum(axis=1)

    if not panel.loc[source_row_available, "available_flow_count"].eq(
        flow_count[source_row_available]
    ).all():
        raise ValueError("Available-flow counts disagree with constituent flows.")
    if not score_available.eq(source_row_available & complete).all():
        raise ValueError("Canonical score availability disagrees with source completeness.")

    panel["trade_evidence_status"] = np.select(
        [
            score_available,
            source_row_available & ~complete,
            ~source_row_available,
        ],
        [
            "complete_four_flow_score_available",
            "source_row_incomplete_four_flows",
            "no_source_row",
        ],
        default="invalid",
    )

    mirror_count = panel[SOURCE_COLUMNS].eq("mirror").sum(axis=1)
    reporter_side_count = panel[SOURCE_COLUMNS].eq("reporter").sum(axis=1)
    panel["mirror_flow_count"] = np.where(score_available, mirror_count, pd.NA)
    panel["reporter_side_flow_count"] = np.where(
        score_available, reporter_side_count, pd.NA
    )
    panel["trade_provenance_status"] = np.select(
        [
            score_available & mirror_count.eq(0),
            score_available & mirror_count.gt(0),
            ~score_available,
        ],
        [
            "all_reporter_side",
            "includes_mirror_side_recovery",
            "score_unavailable",
        ],
        default="invalid",
    )

    panel["trade_comparability_status"] = np.select(
        [
            panel["year"].eq(2025) & score_available,
            panel["year"].eq(2025) & ~score_available,
            panel["year"].le(COMPARABLE_END) & score_available,
            panel["year"].le(COMPARABLE_END) & ~score_available,
        ],
        [
            "provisional_latest_year_extension",
            "provisional_latest_year_score_unavailable",
            "comparable_baseline_period_score_available",
            "baseline_period_score_unavailable",
        ],
        default="invalid",
    )

    output = panel[
        [
            "country_iso3",
            "country_name",
            "preferred_country_name",
            "year",
            "reporter_name",
            *FLOW_COLUMNS,
            *SOURCE_COLUMNS,
            "china_total_trade_usd",
            "us_total_trade_usd",
            "available_flow_count",
            "complete_four_flow_record",
            "mirror_flow_count",
            "reporter_side_flow_count",
            "trade_evidence_status",
            "trade_provenance_status",
            "trade_comparability_status",
            "trade_orientation_score",
        ]
    ].sort_values(KEYS).reset_index(drop=True)
    validate_output(output)
    return output


def validate_output(output: pd.DataFrame) -> dict[str, int]:
    expected_year_counts = {year: 191 for year in range(2007, 2026)}
    expected_year_counts.update({2004: 192, 2005: 192, 2006: 192})
    actual_year_counts = output.groupby("year").size().to_dict()
    failures = {
        "unexpected_rows": int(len(output) != 4205),
        "unexpected_entities": int(output["country_iso3"].nunique() != 192),
        "duplicate_keys": int(output.duplicated(KEYS).sum()),
        "unexpected_year_counts": int(actual_year_counts != expected_year_counts),
        "invalid_status": int(
            output[
                [
                    "trade_evidence_status",
                    "trade_provenance_status",
                    "trade_comparability_status",
                ]
            ]
            .eq("invalid")
            .any(axis=1)
            .sum()
        ),
        "score_out_of_bounds": int(
            (~output["trade_orientation_score"].dropna().between(-1, 1)).sum()
        ),
        "score_without_four_flows": int(
            (
                output["trade_orientation_score"].notna()
                & output[FLOW_COLUMNS].isna().any(axis=1)
            ).sum()
        ),
    }
    if any(failures.values()):
        raise ValueError(f"Trade-orientation validation failed: {failures}")
    return failures


def write_audits(output: pd.DataFrame, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    summary = {
        "rows": int(len(output)),
        "entities": int(output["country_iso3"].nunique()),
        "years": [int(output["year"].min()), int(output["year"].max())],
        "comparable_baseline_period": [PROJECT_START, COMPARABLE_END],
        "provisional_extension_year": 2025,
        "non_missing_scores": int(output["trade_orientation_score"].notna().sum()),
        "missing_scores": int(output["trade_orientation_score"].isna().sum()),
        "score_min": float(output["trade_orientation_score"].min()),
        "score_max": float(output["trade_orientation_score"].max()),
        "evidence_status_counts": {
            key: int(value)
            for key, value in output["trade_evidence_status"].value_counts().items()
        },
        "provenance_status_counts": {
            key: int(value)
            for key, value in output["trade_provenance_status"].value_counts().items()
        },
        "comparability_status_counts": {
            key: int(value)
            for key, value in output[
                "trade_comparability_status"
            ].value_counts().items()
        },
        "validation_failures": validate_output(output),
    }
    (output_dir / "trade_orientation_summary.json").write_text(
        json.dumps(summary, indent=2) + "\n"
    )

    coverage = output.groupby("year").agg(
        eligible_country_years=("country_iso3", "size"),
        source_rows=("reporter_name", "count"),
        complete_four_flow_scores=("trade_orientation_score", "count"),
        mirror_assisted_scores=(
            "trade_provenance_status",
            lambda values: int(values.eq("includes_mirror_side_recovery").sum()),
        ),
        missing_scores=(
            "trade_orientation_score",
            lambda values: int(values.isna().sum()),
        ),
    ).reset_index()
    coverage["score_coverage_rate"] = (
        coverage["complete_four_flow_scores"]
        / coverage["eligible_country_years"]
    )
    coverage.to_csv(
        output_dir / "trade_orientation_coverage_by_year.csv", index=False
    )

    provenance = (
        output.groupby(
            ["year", "trade_provenance_status"], dropna=False
        )
        .size()
        .rename("country_years")
        .reset_index()
    )
    provenance.to_csv(
        output_dir / "trade_orientation_provenance_audit.csv", index=False
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--trade-source",
        type=Path,
        default=Path("data/processed/trade_total_country_year.csv"),
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
        default=Path("data/processed/trade_orientation_country_year.csv"),
    )
    parser.add_argument(
        "--audit-directory",
        type=Path,
        default=Path("outputs/tables/trade_orientation"),
    )
    args = parser.parse_args()
    output = build_trade_orientation(
        pd.read_csv(args.trade_source, low_memory=False),
        pd.read_csv(args.country_master, low_memory=False),
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    output.to_csv(args.output, index=False)
    write_audits(output, args.audit_directory)
    print(f"Wrote {len(output):,} rows to {args.output}")


if __name__ == "__main__":
    main()
