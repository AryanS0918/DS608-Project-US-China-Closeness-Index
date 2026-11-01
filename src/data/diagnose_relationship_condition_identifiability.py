"""Test whether a four-state relationship condition is mechanically identifiable.

Complete runnable example.

Run from the repository root:
    python -u src/data/diagnose_relationship_condition_identifiability.py

Inputs:
    data/raw/relations/gsdb/r5/GSDB-R5_Dyadic.dta
    data/raw/relations/gsdb/financial/GSDB-FS_Dyadic.dta
    outputs/tables/diplomatic_representation/drd_extended_condition_comparison.csv

Outputs:
    outputs/tables/relations_condition/condition_evidence_panel.csv
    outputs/tables/relations_condition/trade_scope_profile.csv
    outputs/tables/relations_condition/sanctions_combination_profile.csv
    outputs/tables/relations_condition/sanctions_direction_profile.csv
    outputs/tables/relations_condition/drd_sanctions_combination_profile.csv
    outputs/tables/relations_condition/severe_rule_trigger_profile.csv
    outputs/tables/relations_condition/candidate_condition_frequency.csv
    outputs/tables/relations_condition/condition_identifiability_summary.json

This script compares a three-state and a four-state candidate specification.
It does not finalise the project methodology.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

ANCHOR_ISO = {"USA": "United States", "CHN": "China"}
R5_FAMILIES = ["arms", "military", "trade", "financial", "travel", "other"]
FS_FIELDS = [
    "fin_asset_freeze", "fin_services", "fin_aid", "fin_investment",
    "fin_other", "fin_payment_infra",
]


def calendar_year(series: pd.Series) -> pd.Series:
    if pd.api.types.is_datetime64_any_dtype(series):
        return series.dt.year.astype("Int64")
    numeric = pd.to_numeric(series, errors="coerce")
    if numeric.dropna().between(1800, 2200).all():
        return numeric.astype("Int64")
    return pd.to_datetime(series, errors="coerce").dt.year.astype("Int64")


def norm(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(value).strip().lower()).strip("_")


def split_tokens(value: Any) -> set[str]:
    if pd.isna(value):
        return set()
    text = norm(value)
    tokens = {token for token in re.split(r"[_;,|/+\s]+", text) if token}
    # Preserve known compound labels when encoded as full strings.
    for label in ["exp_part", "exp_compl", "imp_part", "imp_compl"]:
        if label in text:
            tokens.add(label)
    return tokens


def trade_scope_flags(value: Any) -> dict[str, bool]:
    text = norm(value)
    return {
        "trade_exp_partial": "exp_part" in text,
        "trade_exp_complete": "exp_compl" in text,
        "trade_imp_partial": "imp_part" in text,
        "trade_imp_complete": "imp_compl" in text,
    }


def classify_anchor(row: pd.Series) -> tuple[str | None, str | None, str | None]:
    sender = str(row["sanctioning_state_iso3"]).upper().strip()
    target = str(row["sanctioned_state_iso3"]).upper().strip()
    sender_anchor = ANCHOR_ISO.get(sender)
    target_anchor = ANCHOR_ISO.get(target)
    if sender_anchor and target_anchor:
        return sender_anchor, target_anchor, "anchor_to_anchor"
    if sender_anchor:
        return sender_anchor, target, "anchor_to_country"
    if target_anchor:
        return target_anchor, sender, "country_to_anchor"
    return None, None, None


def load_dyad(path: Path) -> pd.DataFrame:
    frame = pd.read_stata(path, convert_categoricals=False)
    frame.columns = [str(c).strip() for c in frame.columns]
    frame["year"] = calendar_year(frame["year"])
    anchors = frame.apply(classify_anchor, axis=1, result_type="expand")
    anchors.columns = ["anchor", "country", "sanctions_direction"]
    frame = pd.concat([frame, anchors], axis=1)
    return frame[frame["anchor"].notna()].copy()


def find_trade_description(columns: list[str]) -> str:
    candidates = ["descr_trade", "trade_description", "trade_desc"]
    lookup = {norm(column): column for column in columns}
    for candidate in candidates:
        if norm(candidate) in lookup:
            return lookup[norm(candidate)]
    raise KeyError(f"Could not identify trade-description field. Columns: {columns}")


def aggregate_r5(frame: pd.DataFrame) -> pd.DataFrame:
    trade_col = find_trade_description(list(frame.columns))
    flags = frame[trade_col].apply(trade_scope_flags).apply(pd.Series)
    frame = pd.concat([frame, flags], axis=1)

    aggregations = {
        "sanctions_directions": ("sanctions_direction", lambda s: "|".join(sorted(set(s)))),
        "direction_count": ("sanctions_direction", "nunique"),
        "r5_dyadic_rows": ("year", "size"),
    }
    for family in R5_FAMILIES:
        aggregations[family] = (family, "max")
    for flag in flags.columns:
        aggregations[flag] = (flag, "max")

    result = (
        frame.groupby(["country", "anchor", "year"], dropna=False)
        .agg(**aggregations)
        .reset_index()
    )
    result["r5_family_count"] = result[R5_FAMILIES].sum(axis=1).astype("Int64")
    result["reciprocal_sanctions"] = result["direction_count"].ge(2)
    result["complete_trade_any"] = (
        result["trade_exp_complete"] | result["trade_imp_complete"]
    )
    result["complete_trade_both"] = (
        result["trade_exp_complete"] & result["trade_imp_complete"]
    )
    result["partial_trade_any"] = (
        result["trade_exp_partial"] | result["trade_imp_partial"]
    )
    return result


def aggregate_fs(frame: pd.DataFrame) -> pd.DataFrame:
    missing = [column for column in FS_FIELDS if column not in frame.columns]
    if missing:
        raise KeyError(f"Missing FS fields: {missing}")
    aggregations = {field: (field, "max") for field in FS_FIELDS}
    result = (
        frame.groupby(["country", "anchor", "year"], dropna=False)
        .agg(**aggregations)
        .reset_index()
    )
    result["fs_subcategory_count"] = result[FS_FIELDS].sum(axis=1).astype("Int64")
    return result


def family_combination(row: pd.Series) -> str:
    active = [family for family in R5_FAMILIES if row.get(family, 0) == 1]
    return "+".join(active) if active else "none"


def trade_scope_label(row: pd.Series) -> str:
    complete = []
    partial = []
    if row["trade_exp_complete"]:
        complete.append("export_complete")
    if row["trade_imp_complete"]:
        complete.append("import_complete")
    if row["trade_exp_partial"]:
        partial.append("export_partial")
    if row["trade_imp_partial"]:
        partial.append("import_partial")
    labels = complete + partial
    if not labels:
        return "no_described_trade_scope" if row.get("trade", 0) == 1 else "no_trade"
    return "+".join(labels)


def prepare_drd(path: Path) -> pd.DataFrame:
    drd = pd.read_csv(path, low_memory=False)
    required = {
        "country", "anchor", "year", "explicit_adverse_directions",
        "directed_observations",
    }
    missing = required.difference(drd.columns)
    if missing:
        raise KeyError(f"DRD comparison file missing fields: {sorted(missing)}")
    keep = drd[list(required)].copy()
    keep["drd_unilateral_disruption"] = keep["explicit_adverse_directions"].eq(1)
    keep["drd_bilateral_disruption"] = keep["explicit_adverse_directions"].ge(2)
    return keep


def combined_evidence_label(row: pd.Series) -> str:
    sanctions = bool(row["active_sanctions"])
    unilateral = bool(row["drd_unilateral_disruption"])
    bilateral = bool(row["drd_bilateral_disruption"])
    if sanctions and bilateral:
        return "sanctions_plus_bilateral_drd_disruption"
    if sanctions and unilateral:
        return "sanctions_plus_unilateral_drd_disruption"
    if bilateral:
        return "bilateral_drd_disruption_only"
    if unilateral:
        return "unilateral_drd_disruption_only"
    if sanctions:
        return "sanctions_only"
    return "no_adverse_evidence"


def classify_candidates(row: pd.Series) -> pd.Series:
    active = bool(row["active_sanctions"])
    drd_uni = bool(row["drd_unilateral_disruption"])
    drd_bi = bool(row["drd_bilateral_disruption"])

    severe_complete_trade = bool(row["complete_trade_any"])
    severe_reciprocal = bool(row["reciprocal_sanctions"])
    severe_payment_combo = bool(row["fin_payment_infra"] and (row["trade"] or row["fin_services"]))
    severe_cross_source = bool(active and (drd_uni or drd_bi))

    if not active and not drd_uni and not drd_bi:
        four_state = "normal"
        three_state = "normal"
    else:
        three_state = "strained"
        if severe_complete_trade or severe_reciprocal or severe_payment_combo or severe_cross_source:
            four_state = "severely_strained"
        else:
            four_state = "strained"

    triggers = []
    if severe_complete_trade:
        triggers.append("complete_trade")
    if severe_reciprocal:
        triggers.append("reciprocal_sanctions")
    if severe_payment_combo:
        triggers.append("payment_infrastructure_combination")
    if severe_cross_source:
        triggers.append("sanctions_plus_drd_disruption")

    return pd.Series(
        {
            "condition_three_candidate": three_state,
            "condition_four_candidate": four_state,
            "severe_trigger_count": len(triggers),
            "severe_triggers": "|".join(triggers),
        }
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--r5", type=Path, default=Path("data/raw/relations/gsdb/r5/GSDB-R5_Dyadic.dta"))
    parser.add_argument("--fs", type=Path, default=Path("data/raw/relations/gsdb/financial/GSDB-FS_Dyadic.dta"))
    parser.add_argument(
        "--drd",
        type=Path,
        default=Path(
            "outputs/tables/diplomatic_representation/"
            "drd_extended_condition_comparison.csv"
        ),
    )
    parser.add_argument("--output-dir", type=Path, default=Path("outputs/tables/relations_condition"))
    parser.add_argument("--start-year", type=int, default=2000)
    parser.add_argument("--end-year", type=int, default=2024)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    r5 = load_dyad(args.r5)
    fs = load_dyad(args.fs)
    r5 = r5[r5["year"].between(args.start_year, args.end_year)].copy()
    fs = fs[fs["year"].between(args.start_year, args.end_year)].copy()

    r5_panel = aggregate_r5(r5)
    fs_panel = aggregate_fs(fs)
    drd_panel = prepare_drd(args.drd)
    drd_panel = drd_panel[drd_panel["year"].between(args.start_year, args.end_year)]

    evidence = r5_panel.merge(
        fs_panel, on=["country", "anchor", "year"], how="left", validate="one_to_one"
    )
    for column in FS_FIELDS + ["fs_subcategory_count"]:
        evidence[column] = evidence[column].fillna(0)
    evidence = evidence.merge(
        drd_panel,
        on=["country", "anchor", "year"],
        how="outer",
        validate="one_to_one",
    )

    for column in R5_FAMILIES + list(trade_scope_flags("").keys()) + [
        "complete_trade_any", "complete_trade_both", "partial_trade_any",
        "reciprocal_sanctions",
    ]:
        if column not in evidence:
            evidence[column] = False
        evidence[column] = evidence[column].fillna(0)
    for column in FS_FIELDS + ["fs_subcategory_count", "r5_family_count"]:
        evidence[column] = evidence[column].fillna(0)
    for column in ["drd_unilateral_disruption", "drd_bilateral_disruption"]:
        evidence[column] = evidence[column].fillna(False).astype(bool)

    evidence["active_sanctions"] = evidence["r5_family_count"].gt(0)
    evidence["family_combination"] = evidence.apply(family_combination, axis=1)
    evidence["trade_scope_profile"] = evidence.apply(trade_scope_label, axis=1)
    evidence["combined_evidence_profile"] = evidence.apply(combined_evidence_label, axis=1)
    candidate = evidence.apply(classify_candidates, axis=1)
    evidence = pd.concat([evidence, candidate], axis=1)
    evidence = evidence.sort_values(["year", "anchor", "country"])

    trade_profile = (
        evidence[evidence["trade"].eq(1)]
        .groupby(["anchor", "trade_scope_profile"], dropna=False)
        .size().rename("country_anchor_years").reset_index()
    )
    combination_profile = (
        evidence[evidence["active_sanctions"]]
        .groupby(["anchor", "family_combination"], dropna=False)
        .size().rename("country_anchor_years").reset_index()
        .sort_values(["anchor", "country_anchor_years"], ascending=[True, False])
    )
    direction_profile = (
        evidence[evidence["active_sanctions"]]
        .groupby(["anchor", "sanctions_directions", "reciprocal_sanctions"], dropna=False)
        .size().rename("country_anchor_years").reset_index()
    )
    cross_source_profile = (
        evidence.groupby(["anchor", "combined_evidence_profile"], dropna=False)
        .size().rename("country_anchor_years").reset_index()
    )
    trigger_profile = (
        evidence[evidence["condition_four_candidate"].eq("severely_strained")]
        .groupby(["anchor", "severe_triggers"], dropna=False)
        .size().rename("country_anchor_years").reset_index()
        .sort_values(["anchor", "country_anchor_years"], ascending=[True, False])
    )
    state_frequency = (
        evidence.groupby(
            ["year", "anchor", "condition_three_candidate", "condition_four_candidate"],
            dropna=False,
        )
        .size().rename("country_anchor_years").reset_index()
    )

    evidence.to_csv(args.output_dir / "condition_evidence_panel.csv", index=False)
    trade_profile.to_csv(args.output_dir / "trade_scope_profile.csv", index=False)
    combination_profile.to_csv(args.output_dir / "sanctions_combination_profile.csv", index=False)
    direction_profile.to_csv(args.output_dir / "sanctions_direction_profile.csv", index=False)
    cross_source_profile.to_csv(args.output_dir / "drd_sanctions_combination_profile.csv", index=False)
    trigger_profile.to_csv(args.output_dir / "severe_rule_trigger_profile.csv", index=False)
    state_frequency.to_csv(args.output_dir / "candidate_condition_frequency.csv", index=False)

    summary = {
        "study_period": [args.start_year, args.end_year],
        "evidence_country_anchor_years": int(len(evidence)),
        "sanctions_positive_country_anchor_years": int(evidence["active_sanctions"].sum()),
        "drd_unilateral_disruption_country_anchor_years": int(evidence["drd_unilateral_disruption"].sum()),
        "drd_bilateral_disruption_country_anchor_years": int(evidence["drd_bilateral_disruption"].sum()),
        "complete_trade_country_anchor_years": int(evidence["complete_trade_any"].sum()),
        "complete_trade_both_directions_country_anchor_years": int(evidence["complete_trade_both"].sum()),
        "reciprocal_sanctions_country_anchor_years": int(evidence["reciprocal_sanctions"].sum()),
        "payment_infrastructure_combination_country_anchor_years": int(
            (evidence["fin_payment_infra"].eq(1) & (evidence["trade"].eq(1) | evidence["fin_services"].eq(1))).sum()
        ),
        "sanctions_plus_drd_disruption_country_anchor_years": int(
            (evidence["active_sanctions"] & (evidence["drd_unilateral_disruption"] | evidence["drd_bilateral_disruption"])).sum()
        ),
        "three_state_counts_within_evidence_universe": evidence["condition_three_candidate"].value_counts().to_dict(),
        "four_state_counts_within_evidence_universe": evidence["condition_four_candidate"].value_counts().to_dict(),
        "rupture_identified": False,
        "note": "Normal counts are limited to the union of GSDB-positive and DRD-observed country-anchor-years, not the final master country universe.",
    }
    (args.output_dir / "condition_identifiability_summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )

    print("=" * 72)
    print("RELATIONSHIP CONDITION IDENTIFIABILITY DIAGNOSTIC")
    print("=" * 72)
    print(json.dumps(summary, indent=2))
    print("\nSevere-trigger profile:")
    print(trigger_profile.to_string(index=False))
    print("\nRecent candidate frequencies:")
    print(state_frequency[state_frequency["year"] >= args.end_year - 4].to_string(index=False))
    print("\nOutputs written to:", args.output_dir.resolve())


if __name__ == "__main__":
    main()
