"""Build the production economic subindex.

The subindex combines signed trade orientation, country-fixed-regime FDI
orientation, and signed economic institutional orientation. Equal conceptual
weights apply when all three components are available. When exactly two are
available, weights are renormalised equally. At least two components are
required; institutional-only rows remain unavailable.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

KEYS = ["country_iso3", "year"]
COMPONENTS = [
    "trade_orientation_score",
    "fdi_orientation_score",
    "economic_institutional_orientation_score",
]
MINIMUM_COMPONENTS = 2


def require_columns(frame: pd.DataFrame, required: set[str], label: str) -> None:
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(f"{label} missing required columns: {missing}")


def reshape_fdi(frame: pd.DataFrame) -> pd.DataFrame:
    require_columns(
        frame,
        {
            "country_iso3", "preferred_country_name", "anchor", "year",
            "fdi_structural_score_raw", "fdi_reporting_regime",
            "regime_assignment_rule", "host_signed_years_2009_2017",
            "host_signed_years_2018_2024",
        },
        "FDI panel",
    )
    if frame.duplicated(["country_iso3", "anchor", "year"]).any():
        raise ValueError("FDI panel contains duplicate country-anchor-year keys.")
    wide = frame.pivot(
        index=["country_iso3", "preferred_country_name", "year"],
        columns="anchor",
        values="fdi_structural_score_raw",
    ).reset_index()
    wide["fdi_orientation_score"] = wide["United States"] - wide["China"]
    audit = frame.drop_duplicates("country_iso3")[
        [
            "country_iso3", "fdi_reporting_regime", "regime_assignment_rule",
            "host_signed_years_2009_2017", "host_signed_years_2018_2024",
        ]
    ]
    return wide.merge(audit, on="country_iso3", how="left", validate="many_to_one")


def reshape_institutional(frame: pd.DataFrame) -> pd.DataFrame:
    require_columns(
        frame,
        {"country_iso3", "preferred_country_name", "anchor", "year", "economic_institutional_score_raw"},
        "Economic institutional panel",
    )
    if frame.duplicated(["country_iso3", "anchor", "year"]).any():
        raise ValueError("Institutional panel contains duplicate country-anchor-year keys.")
    wide = frame.pivot(
        index=["country_iso3", "preferred_country_name", "year"],
        columns="anchor",
        values="economic_institutional_score_raw",
    ).reset_index()
    wide["economic_institutional_orientation_score"] = wide["United States"] - wide["China"]
    return wide


def weighted_available_score(frame: pd.DataFrame, weights: dict[str, float]) -> pd.Series:
    values = frame[list(weights)]
    availability = values.notna()
    numerator = values.mul(pd.Series(weights)).sum(axis=1, skipna=True)
    denominator = availability.mul(pd.Series(weights)).sum(axis=1)
    return numerator.div(denominator).where(denominator.gt(0))


def build_economic_subindex(
    trade: pd.DataFrame,
    fdi: pd.DataFrame,
    institutional: pd.DataFrame,
) -> pd.DataFrame:
    require_columns(
        trade,
        {
            "country_iso3", "preferred_country_name", "year",
            "trade_orientation_score", "trade_evidence_status",
            "trade_provenance_status", "trade_comparability_status",
        },
        "Trade panel",
    )
    if trade.duplicated(KEYS).any():
        raise ValueError("Trade panel contains duplicate country-year keys.")

    fdi_wide = reshape_fdi(fdi)
    inst_wide = reshape_institutional(institutional)

    panel = trade[
        [
            "country_iso3", "preferred_country_name", "year",
            "trade_orientation_score", "trade_evidence_status",
            "trade_provenance_status", "trade_comparability_status",
        ]
    ].merge(
        fdi_wide[
            [
                "country_iso3", "year", "fdi_orientation_score",
                "fdi_reporting_regime", "regime_assignment_rule",
                "host_signed_years_2009_2017", "host_signed_years_2018_2024",
            ]
        ],
        on=KEYS, how="outer", validate="one_to_one", indicator="trade_fdi_join",
    ).merge(
        inst_wide[["country_iso3", "year", "economic_institutional_orientation_score"]],
        on=KEYS, how="outer", validate="one_to_one", indicator="institutional_join",
    )
    if not panel["trade_fdi_join"].eq("both").all():
        raise ValueError("Trade and FDI canonical grids do not align.")
    if not panel["institutional_join"].eq("both").all():
        raise ValueError("Institutional canonical grid does not align.")
    panel = panel.drop(columns=["trade_fdi_join", "institutional_join"])

    panel["available_component_count"] = panel[COMPONENTS].notna().sum(axis=1)
    trade_available = panel["trade_orientation_score"].notna()
    fdi_available = panel["fdi_orientation_score"].notna()
    institutional_available = panel["economic_institutional_orientation_score"].notna()
    all_three = panel["available_component_count"].eq(3)
    two = panel["available_component_count"].eq(2)
    one = panel["available_component_count"].eq(1)

    panel["economic_score"] = panel[COMPONENTS].mean(axis=1, skipna=True).where(
        panel["available_component_count"].ge(MINIMUM_COMPONENTS)
    )
    panel["economic_component_status"] = np.select(
        [
            all_three,
            trade_available & ~fdi_available & institutional_available,
            ~trade_available & fdi_available & institutional_available,
            one,
        ],
        [
            "trade_fdi_institutional_available",
            "trade_and_institutional_available_fdi_unavailable",
            "fdi_and_institutional_available_trade_unavailable",
            "institutional_only_score_unavailable",
        ],
        default="invalid",
    )
    panel["economic_comparability_status"] = np.select(
        [
            panel["year"].between(2004, 2008) & two,
            panel["year"].between(2004, 2008) & one,
            panel["year"].between(2009, 2017) & all_three,
            panel["year"].between(2009, 2017) & two,
            panel["year"].between(2009, 2017) & one,
            panel["year"].between(2018, 2024) & all_three,
            panel["year"].between(2018, 2024) & two,
            panel["year"].between(2018, 2024) & one,
            panel["year"].eq(2025) & two,
            panel["year"].eq(2025) & one,
        ],
        [
            "pre_fdi_source_period_two_component_extension",
            "pre_fdi_source_period_score_unavailable",
            "fixed_regime_historical_extension_three_components",
            "fixed_regime_historical_extension_two_components",
            "fixed_regime_historical_extension_score_unavailable",
            "fixed_regime_common_period_three_components",
            "fixed_regime_common_period_two_components",
            "fixed_regime_common_period_score_unavailable",
            "provisional_latest_year_two_component_extension",
            "provisional_latest_year_score_unavailable",
        ],
        default="invalid",
    )
    validate_output(panel)
    return panel.sort_values(KEYS).reset_index(drop=True)


def validate_output(panel: pd.DataFrame) -> dict[str, int]:
    component_counts = panel["available_component_count"].value_counts().sort_index().to_dict()
    expected_counts = {1: 535, 2: 2041, 3: 1629}
    failures = {
        "unexpected_rows": int(len(panel) != 4205),
        "unexpected_entities": int(panel["country_iso3"].nunique() != 192),
        "duplicate_keys": int(panel.duplicated(KEYS).sum()),
        "unexpected_component_counts": int(component_counts != expected_counts),
        "unexpected_available_scores": int(panel["economic_score"].notna().sum() != 3670),
        "unexpected_missing_scores": int(panel["economic_score"].isna().sum() != 535),
        "score_out_of_bounds": int((~panel["economic_score"].dropna().between(-1, 1)).sum()),
        "one_component_score_present": int(panel.loc[panel["available_component_count"].eq(1), "economic_score"].notna().sum()),
        "multi_component_score_missing": int(panel.loc[panel["available_component_count"].ge(2), "economic_score"].isna().sum()),
        "invalid_status": int((panel[["economic_component_status", "economic_comparability_status"]] == "invalid").any(axis=1).sum()),
        "2025_fdi_scores_present": int(panel.loc[panel["year"].eq(2025), "fdi_orientation_score"].notna().sum()),
    }
    if any(failures.values()):
        raise ValueError(f"Economic-subindex validation failed: {failures}")
    return failures


def write_audits(panel: pd.DataFrame, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    summary = {
        "rows": int(len(panel)),
        "entities": int(panel["country_iso3"].nunique()),
        "years": [int(panel["year"].min()), int(panel["year"].max())],
        "available_scores": int(panel["economic_score"].notna().sum()),
        "missing_scores": int(panel["economic_score"].isna().sum()),
        "score_min": float(panel["economic_score"].min()),
        "score_max": float(panel["economic_score"].max()),
        "minimum_required_components": MINIMUM_COMPONENTS,
        "component_count_distribution": {
            str(int(k)): int(v) for k, v in panel["available_component_count"].value_counts().sort_index().items()
        },
        "component_status_counts": {
            k: int(v) for k, v in panel["economic_component_status"].value_counts().items()
        },
        "comparability_status_counts": {
            k: int(v) for k, v in panel["economic_comparability_status"].value_counts().items()
        },
        "validation_failures": validate_output(panel),
    }
    (output_dir / "economic_subindex_summary.json").write_text(json.dumps(summary, indent=2) + "\n")

    sensitivity = panel[
        [
            "country_iso3", "preferred_country_name", "year",
            "economic_score", "available_component_count",
            "economic_component_status", "economic_comparability_status",
        ]
    ].copy()
    sensitivity["economic_score_zero_fill"] = panel[COMPONENTS].fillna(0).mean(axis=1)
    sensitivity["economic_score_real_economy_emphasis"] = weighted_available_score(
        panel,
        {
            "trade_orientation_score": 0.40,
            "fdi_orientation_score": 0.40,
            "economic_institutional_orientation_score": 0.20,
        },
    ).where(panel["available_component_count"].ge(MINIMUM_COMPONENTS))
    sensitivity["economic_score_institutional_emphasis"] = weighted_available_score(
        panel,
        {
            "trade_orientation_score": 0.25,
            "fdi_orientation_score": 0.25,
            "economic_institutional_orientation_score": 0.50,
        },
    ).where(panel["available_component_count"].ge(MINIMUM_COMPONENTS))
    sensitivity.to_csv(output_dir / "economic_subindex_sensitivity.csv", index=False)

    common = panel.loc[panel["available_component_count"].eq(3)].copy()
    common["component_sign_pattern"] = (
        np.sign(common["trade_orientation_score"]).astype(int).astype(str)
        + "|" + np.sign(common["fdi_orientation_score"]).astype(int).astype(str)
        + "|" + np.sign(common["economic_institutional_orientation_score"]).astype(int).astype(str)
    )
    common["maximum_component_gap"] = pd.concat(
        [(common[column] - common["economic_score"]).abs() for column in COMPONENTS], axis=1
    ).max(axis=1)
    common.sort_values("maximum_component_gap", ascending=False).to_csv(
        output_dir / "economic_component_disagreement_cases.csv", index=False
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trade", type=Path, default=Path("data/processed/trade_orientation_country_year.csv"))
    parser.add_argument("--fdi", type=Path, default=Path("data/processed/fdi_structural_ties_country_anchor_year.csv"))
    parser.add_argument("--institutional", type=Path, default=Path("data/processed/economic_institutional_ties_country_anchor_year.csv"))
    parser.add_argument("--output", type=Path, default=Path("data/processed/economic_subindex_country_year.csv"))
    parser.add_argument("--audit-directory", type=Path, default=Path("outputs/tables/economic_subindex"))
    args = parser.parse_args()
    panel = build_economic_subindex(
        pd.read_csv(args.trade, low_memory=False),
        pd.read_csv(args.fdi, low_memory=False),
        pd.read_csv(args.institutional, low_memory=False),
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    panel.to_csv(args.output, index=False)
    write_audits(panel, args.audit_directory)
    print(f"Wrote {len(panel):,} rows to {args.output}")


if __name__ == "__main__":
    main()
