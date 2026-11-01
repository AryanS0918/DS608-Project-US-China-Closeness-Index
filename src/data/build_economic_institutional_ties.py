"""Combine BIT and trade-agreement ties into economic institutional ties.

Run from the repository root:
    python -u src/data/build_economic_institutional_ties.py
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

KEYS = ["country_iso3", "anchor", "year"]
TRADE_WEIGHT = 0.75
BIT_WEIGHT = 0.25
METHOD_VERSION = "economic_institutional_ties_v1_trade75_bit25"
BIT_STATE_ALIASES = [
    "bit_relationship_state",
    "bit_year_end_state",
    "bit_state",
    "year_end_state",
    "treaty_state",
]


def first_existing(columns: pd.Index, candidates: list[str]) -> str | None:
    for candidate in candidates:
        if candidate in columns:
            return candidate
    return None


def prepare_bit_panel(bit: pd.DataFrame) -> pd.DataFrame:
    required = {
        "bit_structural_score_raw",
        "bit_structural_score_scaled",
        "bit_signed_not_in_force",
        "bit_in_force",
        "bit_terminated_history",
    }
    missing = required.difference(bit.columns)
    if missing:
        raise KeyError(f"BIT panel is missing fields: {sorted(missing)}")

    state_column = first_existing(bit.columns, BIT_STATE_ALIASES)
    result = bit.copy()

    if state_column is not None:
        result["bit_year_end_state"] = result[state_column].astype("string")
    else:
        result["bit_year_end_state"] = "none"
        result.loc[
            result["bit_terminated_history"].astype(bool),
            "bit_year_end_state",
        ] = "historical_terminated"
        result.loc[
            result["bit_signed_not_in_force"].astype(bool),
            "bit_year_end_state",
        ] = "signed_not_in_force"
        result.loc[
            result["bit_in_force"].astype(bool),
            "bit_year_end_state",
        ] = "in_force"

    expected_states = {
        "none",
        "historical_terminated",
        "signed_not_in_force",
        "in_force",
    }
    unexpected = set(result["bit_year_end_state"].dropna().astype(str)) - expected_states
    if unexpected:
        raise ValueError(f"Unexpected BIT year-end states: {sorted(unexpected)}")

    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--trade",
        type=Path,
        default=Path(
            "data/processed/trade_agreement_ties_country_anchor_year.csv"
        ),
    )
    parser.add_argument(
        "--bit",
        type=Path,
        default=Path(
            "data/processed/"
            "bilateral_investment_treaties_country_anchor_year.csv"
        ),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(
            "data/processed/"
            "economic_institutional_ties_country_anchor_year.csv"
        ),
    )
    parser.add_argument(
        "--report-directory",
        type=Path,
        default=Path("outputs/tables/economic_institutional_ties"),
    )
    args = parser.parse_args()

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.report_directory.mkdir(parents=True, exist_ok=True)

    trade = pd.read_csv(args.trade, low_memory=False)
    bit = prepare_bit_panel(pd.read_csv(args.bit, low_memory=False))

    if trade.duplicated(KEYS).any() or bit.duplicated(KEYS).any():
        raise ValueError("Duplicate component keys")

    bit_fields = [
        "bit_year_end_state",
        "bit_structural_score_raw",
        "bit_structural_score_scaled",
        "bit_signed_not_in_force",
        "bit_in_force",
        "bit_terminated_history",
    ]

    panel = trade.merge(
        bit[KEYS + bit_fields],
        on=KEYS,
        how="left",
        validate="one_to_one",
    )

    if panel["bit_structural_score_raw"].isna().any():
        raise ValueError("BIT merge produced missing component rows")

    panel["economic_institutional_score_raw"] = (
        TRADE_WEIGHT * panel["trade_agreement_score_raw"]
        + BIT_WEIGHT * panel["bit_structural_score_raw"]
    )
    panel["economic_institutional_score_scaled"] = (
        100.0 * panel["economic_institutional_score_raw"]
    )
    panel["economic_institutional_method_version"] = METHOD_VERSION

    panel["economic_institutional_equal_blocks"] = (
        0.50 * panel["trade_agreement_score_raw"]
        + 0.50 * panel["bit_structural_score_raw"]
    )

    panel["economic_institutional_original_hierarchy"] = (
        0.45 * panel["bilateral_fta_active"].astype(int)
        + 0.2625 * panel["regional_fta_active"].astype(int)
        + 0.0375 * panel["sectoral_trade_agreement_active"].astype(int)
        + 0.25 * panel["bit_structural_score_raw"]
    )

    formula_gap = (
        panel["economic_institutional_score_raw"]
        - panel["economic_institutional_original_hierarchy"]
    ).abs()

    failures = {
        "duplicate_keys": int(panel.duplicated(KEYS).sum()),
        "blank_country_names": int(panel["country_name"].isna().sum()),
        "score_bound_failures": int(
            (~panel["economic_institutional_score_raw"].between(0, 1)).sum()
        ),
        "formula_identity_failures": int(formula_gap.gt(1e-12).sum()),
        "missing_bit_states": int(panel["bit_year_end_state"].isna().sum()),
    }

    nonzero = {key: value for key, value in failures.items() if value}
    if nonzero:
        raise AssertionError(
            f"Economic institutional validation failed: {nonzero}"
        )

    summary = {
        "rows": int(len(panel)),
        "countries_or_historical_entities": int(
            panel["country_iso3"].nunique()
        ),
        "study_years": [
            int(panel["year"].min()),
            int(panel["year"].max()),
        ],
        "component_weights": {
            "trade_agreement": TRADE_WEIGHT,
            "bit": BIT_WEIGHT,
        },
        "effective_family_weights": {
            "bilateral_fta": 0.45,
            "regional_trade_agreement": 0.2625,
            "sectoral_trade_agreement": 0.0375,
            "bit": 0.25,
        },
        "bit_state_counts": (
            panel["bit_year_end_state"].value_counts().to_dict()
        ),
        "score_distribution": (
            panel["economic_institutional_score_raw"]
            .describe()
            .to_dict()
        ),
        "validation_failures": failures,
    }

    sensitivity = (
        panel.groupby(["anchor", "year"])[
            [
                "economic_institutional_score_raw",
                "economic_institutional_equal_blocks",
            ]
        ]
        .mean()
        .reset_index()
    )

    panel.to_csv(args.output, index=False)
    sensitivity.to_csv(
        args.report_directory
        / "economic_institutional_sensitivity_by_year.csv",
        index=False,
    )
    (
        args.report_directory
        / "economic_institutional_summary.json"
    ).write_text(
        json.dumps(summary, indent=2),
        encoding="utf-8",
    )

    print("=" * 72)
    print("ECONOMIC INSTITUTIONAL TIES PANEL")
    print("=" * 72)
    print(json.dumps(summary, indent=2))
    print("\nProduction output:", args.output)


if __name__ == "__main__":
    main()
