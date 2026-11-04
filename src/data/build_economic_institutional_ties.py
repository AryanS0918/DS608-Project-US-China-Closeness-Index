"""Build canonical economic institutional ties from trade agreements and BITs.

Run from the repository root:
    python src/data/build_economic_institutional_ties.py

The baseline combines 75% trade-agreement ties and 25% bilateral-investment-
treaty ties. Source registers are reconstructed directly through 2024. Analyst
review found no 2025 treaty-state changes, so 2025 carries forward the verified
31 December 2024 states and is explicitly flagged as such.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_START = 2004
PROJECT_END = 2025
DIRECT_END = 2024
ANCHORS = ("China", "United States")
KEYS = ["country_iso3", "anchor", "year"]
TRADE_WEIGHT = 0.75
BIT_WEIGHT = 0.25
METHOD_VERSION = "economic_institutional_ties_v2_trade75_bit25_verified2025"

TRADE_FIELDS = [
    "bilateral_fta_active", "regional_fta_active",
    "sectoral_trade_agreement_active", "bilateral_fta_count",
    "regional_fta_count", "sectoral_trade_agreement_count",
    "active_trade_agreement_count", "active_trade_agreement_family_count",
    "active_trade_agreement_ids", "active_trade_agreement_families",
    "original_signed_weight_sum", "original_absolute_weight_sum",
    "reconstructed_record_count", "trade_agreement_score_raw",
    "trade_agreement_score_scaled", "trade_agreement_source_available",
    "any_trade_agreement_active", "bilateral_plus_regional",
    "multiple_regional_agreements", "method_version",
]
BIT_FIELDS = [
    "bit_state_year_end", "bit_structural_score_raw",
    "bit_structural_score_scaled", "bit_in_force",
    "bit_signed_not_in_force", "bit_terminated_history",
    "bit_ever_signed", "bit_ever_in_force", "bit_in_force_count",
    "bit_signed_not_in_force_count", "bit_terminated_count",
    "bit_replacement_overlap", "bit_current_treaty_ids",
    "bit_current_treaty_titles", "bit_all_year_end_states",
    "method_version",
]


def require_columns(frame: pd.DataFrame, required: set[str], label: str) -> None:
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(f"{label} missing required columns: {missing}")


def build_universe(master: pd.DataFrame) -> pd.DataFrame:
    require_columns(
        master,
        {"iso3", "country_name", "preferred_country_name", "first_valid_year",
         "last_valid_year", "baseline_index_eligible"},
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
        raise ValueError("Canonical economic-institutional universe has duplicates.")
    return universe


def prepare_source(frame: pd.DataFrame, fields: list[str], label: str) -> pd.DataFrame:
    require_columns(frame, set(KEYS + fields), label)
    source = frame.loc[frame["year"].between(PROJECT_START, DIRECT_END), KEYS + fields].copy()
    if source.duplicated(KEYS).any():
        raise ValueError(f"{label} contains duplicate keys.")
    return source


def carry_forward_verified_2025(frame_2004_2024: pd.DataFrame) -> pd.DataFrame:
    rows_2024 = frame_2004_2024.loc[frame_2004_2024["year"].eq(2024)].copy()
    rows_2024["year"] = 2025
    return pd.concat([frame_2004_2024, rows_2024], ignore_index=True)


def build_panel(
    trade_raw: pd.DataFrame,
    bit_raw: pd.DataFrame,
    country_master: pd.DataFrame,
) -> pd.DataFrame:
    universe = build_universe(country_master)
    base_universe = universe.loc[universe["year"].le(DIRECT_END)].copy()
    trade = prepare_source(trade_raw, TRADE_FIELDS, "Trade-agreement panel")
    bit = prepare_source(bit_raw, BIT_FIELDS, "BIT panel")
    trade = trade.rename(columns={"method_version": "trade_agreement_method_version"})
    bit = bit.rename(columns={"method_version": "bit_method_version"})

    panel = base_universe.merge(
        trade, on=KEYS, how="left", validate="one_to_one",
        indicator="trade_merge_status",
    )
    panel = panel.merge(
        bit, on=KEYS, how="left", validate="one_to_one",
        indicator="bit_merge_status",
    )

    # The agreement registers are exhaustive state registers. A canonical
    # entity-year absent from the old source grid means no active agreement,
    # not unavailable evidence. Preserve an explicit evidence-status field.
    source_row_present = (
        panel["trade_merge_status"].eq("both")
        & panel["bit_merge_status"].eq("both")
    )
    panel["economic_institutional_source_grid_status"] = np.where(
        source_row_present,
        "source_grid_row_present",
        "canonical_zero_state_added",
    )

    trade_bool = [
        "bilateral_fta_active", "regional_fta_active",
        "sectoral_trade_agreement_active", "trade_agreement_source_available",
        "any_trade_agreement_active", "bilateral_plus_regional",
        "multiple_regional_agreements",
    ]
    trade_count = [
        "bilateral_fta_count", "regional_fta_count",
        "sectoral_trade_agreement_count", "active_trade_agreement_count",
        "active_trade_agreement_family_count", "reconstructed_record_count",
    ]
    trade_numeric = [
        "original_signed_weight_sum", "original_absolute_weight_sum",
        "trade_agreement_score_raw", "trade_agreement_score_scaled",
    ]
    for column in trade_bool:
        default = True if column == "trade_agreement_source_available" else False
        panel[column] = panel[column].where(panel[column].notna(), default).astype(bool)
    for column in trade_count + trade_numeric:
        panel[column] = panel[column].fillna(0)
    panel["trade_agreement_method_version"] = panel[
        "trade_agreement_method_version"
    ].fillna("trade_agreement_ties_v2_year_end_reconstructed")

    bit_bool = [
        "bit_in_force", "bit_signed_not_in_force", "bit_terminated_history",
        "bit_ever_signed", "bit_ever_in_force", "bit_replacement_overlap",
    ]
    bit_count = [
        "bit_in_force_count", "bit_signed_not_in_force_count",
        "bit_terminated_count",
    ]
    for column in bit_bool:
        panel[column] = panel[column].where(panel[column].notna(), False).astype(bool)
    for column in bit_count:
        panel[column] = panel[column].fillna(0)
    panel["bit_state_year_end"] = panel["bit_state_year_end"].fillna("none")
    panel["bit_structural_score_raw"] = panel[
        "bit_structural_score_raw"
    ].fillna(0.0)
    panel["bit_structural_score_scaled"] = panel[
        "bit_structural_score_scaled"
    ].fillna(0.0)
    panel["bit_method_version"] = panel["bit_method_version"].fillna(
        "bilateral_investment_treaties_v1_year_end_state"
    )

    panel["economic_institutional_score_raw"] = (
        TRADE_WEIGHT * panel["trade_agreement_score_raw"]
        + BIT_WEIGHT * panel["bit_structural_score_raw"]
    )
    panel["economic_institutional_score_scaled"] = (
        100 * panel["economic_institutional_score_raw"]
    )
    panel["economic_institutional_equal_blocks"] = (
        0.5 * panel["trade_agreement_score_raw"]
        + 0.5 * panel["bit_structural_score_raw"]
    )
    panel["economic_institutional_original_hierarchy"] = (
        0.6 * panel["trade_agreement_score_raw"]
        + 0.4 * panel["bit_structural_score_raw"]
    )
    panel["economic_institutional_evidence_status"] = "directly_reconstructed"
    panel["economic_institutional_comparability_status"] = (
        "comparable_direct_reconstruction"
    )

    # Carry the complete, canonical 2024 states into 2025 only after analyst
    # review confirmed no 2025 treaty-state changes.
    rows_2025 = panel.loc[panel["year"].eq(2024)].copy()
    rows_2025["year"] = 2025
    rows_2025["economic_institutional_evidence_status"] = (
        "verified_unchanged_carry_forward"
    )
    rows_2025["economic_institutional_comparability_status"] = (
        "comparable_verified_unchanged_2025"
    )
    panel = pd.concat([panel, rows_2025], ignore_index=True)
    panel["economic_institutional_method_version"] = METHOD_VERSION
    panel = panel.rename(columns={"bit_state_year_end": "bit_year_end_state"})

    output_cols = [
        "country_iso3", "country_name", "preferred_country_name", "anchor", "year",
        *[c for c in TRADE_FIELDS if c != "method_version"],
        "trade_agreement_method_version",
        "bit_year_end_state",
        *[c for c in BIT_FIELDS if c not in {"method_version", "bit_state_year_end"}],
        "bit_method_version",
        "economic_institutional_score_raw",
        "economic_institutional_score_scaled",
        "economic_institutional_equal_blocks",
        "economic_institutional_original_hierarchy",
        "economic_institutional_source_grid_status",
        "economic_institutional_evidence_status",
        "economic_institutional_comparability_status",
        "economic_institutional_method_version",
    ]
    output = panel[output_cols].sort_values(KEYS).reset_index(drop=True)
    validate_panel(output)
    return output


def validate_panel(panel: pd.DataFrame) -> dict[str, int]:
    formula = TRADE_WEIGHT * panel["trade_agreement_score_raw"] + BIT_WEIGHT * panel["bit_structural_score_raw"]
    carry_fields = [
        "trade_agreement_score_raw", "bit_structural_score_raw",
        "economic_institutional_score_raw", "bit_year_end_state",
        "bilateral_fta_active", "regional_fta_active",
        "sectoral_trade_agreement_active",
    ]
    prior = panel.loc[panel["year"].eq(2024), ["country_iso3", "anchor", *carry_fields]].copy()
    current = panel.loc[panel["year"].eq(2025), ["country_iso3", "anchor", *carry_fields]].copy()
    carry = prior.merge(current, on=["country_iso3", "anchor"], suffixes=("_2024", "_2025"), validate="one_to_one")
    carry_mismatches = 0
    for field in carry_fields:
        left, right = carry[f"{field}_2024"], carry[f"{field}_2025"]
        carry_mismatches += int((~(left.eq(right) | (left.isna() & right.isna()))).sum())
    failures = {
        "unexpected_rows": int(len(panel) != 8410),
        "unexpected_entities": int(panel["country_iso3"].nunique() != 192),
        "duplicate_keys": int(panel.duplicated(KEYS).sum()),
        "missing_component_scores": int(panel[["trade_agreement_score_raw", "bit_structural_score_raw"]].isna().any(axis=1).sum()),
        "score_out_of_bounds": int((~panel["economic_institutional_score_raw"].between(0, 1)).sum()),
        "formula_failures": int((panel["economic_institutional_score_raw"] - formula).abs().gt(1e-12).sum()),
        "missing_bit_states": int(panel["bit_year_end_state"].isna().sum()),
        "2025_carry_forward_mismatches": carry_mismatches,
        "unexpected_2025_evidence_status": int(~panel.loc[panel["year"].eq(2025), "economic_institutional_evidence_status"].eq("verified_unchanged_carry_forward").all()),
    }
    if any(failures.values()):
        raise ValueError(f"Economic institutional validation failed: {failures}")
    return failures


def build_summary(panel: pd.DataFrame) -> dict:
    return {
        "rows": int(len(panel)),
        "entities": int(panel["country_iso3"].nunique()),
        "years": [int(panel["year"].min()), int(panel["year"].max())],
        "component_weights": {"trade_agreement": TRADE_WEIGHT, "bit": BIT_WEIGHT},
        "effective_family_weights": {
            "bilateral_fta": 0.45,
            "regional_trade_agreement": 0.2625,
            "sectoral_trade_agreement": 0.0375,
            "bit": 0.25,
        },
        "evidence_status_counts": {k: int(v) for k, v in panel["economic_institutional_evidence_status"].value_counts().items()},
        "bit_state_counts": {k: int(v) for k, v in panel["bit_year_end_state"].value_counts().items()},
        "score_distribution": {k: float(v) for k, v in panel["economic_institutional_score_raw"].describe().items()},
        "validation_failures": validate_panel(panel),
    }


def write_outputs(panel: pd.DataFrame, output: Path, report_directory: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    report_directory.mkdir(parents=True, exist_ok=True)
    panel.to_csv(output, index=False)
    sensitivity = panel.groupby(["anchor", "year"])[[
        "economic_institutional_score_raw",
        "economic_institutional_equal_blocks",
        "economic_institutional_original_hierarchy",
    ]].mean().reset_index()
    sensitivity.to_csv(report_directory / "economic_institutional_sensitivity_by_year.csv", index=False)
    (report_directory / "economic_institutional_summary.json").write_text(json.dumps(build_summary(panel), indent=2) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trade-agreements", type=Path, default=Path("data/processed/trade_agreement_ties_country_anchor_year.csv"))
    parser.add_argument("--bits", type=Path, default=Path("data/processed/bilateral_investment_treaties_country_anchor_year.csv"))
    parser.add_argument("--country-master", type=Path, default=Path("outputs/tables/relations_condition/relationship_condition_country_master.csv"))
    parser.add_argument("--output", type=Path, default=Path("data/processed/economic_institutional_ties_country_anchor_year.csv"))
    parser.add_argument("--report-directory", type=Path, default=Path("outputs/tables/economic_institutional_ties"))
    args = parser.parse_args()
    panel = build_panel(
        pd.read_csv(args.trade_agreements, low_memory=False),
        pd.read_csv(args.bits, low_memory=False),
        pd.read_csv(args.country_master, low_memory=False),
    )
    write_outputs(panel, args.output, args.report_directory)
    print(f"Wrote {len(panel):,} rows to {args.output}")


if __name__ == "__main__":
    main()
