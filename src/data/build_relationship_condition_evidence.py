"""Build the harmonised sanctions and diplomatic relationship-evidence panel.

Run from the repository root:
    python -u src/data/build_relationship_condition_evidence.py

The script consumes the corrected GSDB country-anchor-year panel rather than
reconstructing sanctions from raw dyads. It harmonises DRD country names,
retains the historical Serbia and Montenegro entity for 2000-2006, preserves
all severe-trigger components, and stops on unresolved evidence-bearing rows.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

R5_FAMILIES = ["arms", "military", "trade", "financial", "travel", "other"]
FS_FIELDS = [
    "fin_asset_freeze", "fin_services", "fin_aid", "fin_investment",
    "fin_other", "fin_payment_infra",
]
TRADE_SCOPE_FIELDS = [
    "trade_exp_partial", "trade_exp_complete",
    "trade_imp_partial", "trade_imp_complete",
]
HISTORICAL_ENTITY_RULES = {
    "serbia_and_montenegro": {
        "iso3": "SCG", "country_name": "Serbia and Montenegro",
        "first_year": 2000, "last_year": 2006,
    }
}
COUNTRY_ALIASES = {
    "cabo_verde": "CPV",
    "cape_verde": "CPV",
    "congo_brazzaville": "COG",
    "congo_kinshasa": "COD",
    "cote_d_ivoire": "CIV",
    "c_te_d_ivoire": "CIV",
    "egypt": "EGY",
    "ethiopia": "ETH",
    "jordan": "JOR",
    "holy_see_vatican": "VAT",
    "korea_democratic_people_s_republic_of": "PRK",
    "korea_republic_of": "KOR",
    "lao_people_s_democratic_republic": "LAO",
    "madagascar": "MDG",
    "malaysia": "MYS",
    "oman": "OMN",
    "saint_vincent_and_the_grenadines": "VCT",
    "samoa": "WSM",
    "sri_lanka": "LKA",
    "timor_leste": "TLS",
    "yemen": "YEM",
    "viet_nam": "VNM",
    "china": "CHN",
    "united_states": "USA",
}


def normalise_name(value: Any) -> str:
    if pd.isna(value):
        return ""
    text = str(value).strip().lower()
    text = text.replace("\x92", "'").replace("’", "'")
    text = re.sub(r"[^a-z0-9]+", "_", text)
    return text.strip("_")


def load_country_map(path: Path) -> tuple[dict[str, str], pd.DataFrame]:
    crosswalk = pd.read_csv(path, low_memory=False)
    required = {"source_name", "normalized_name", "iso3"}
    missing = required.difference(crosswalk.columns)
    if missing:
        raise KeyError(f"Country crosswalk missing fields: {sorted(missing)}")

    clean = crosswalk.copy()
    clean["iso3"] = clean["iso3"].astype("string").str.strip().str.upper()
    clean["normalized_name"] = clean["source_name"].map(normalise_name)
    clean = clean[clean["iso3"].str.fullmatch(r"[A-Z]{3}", na=False)].copy()

    ambiguity = clean.groupby("normalized_name")["iso3"].nunique()
    ambiguous = set(ambiguity[ambiguity.gt(1)].index)
    usable = clean[~clean["normalized_name"].isin(ambiguous)]
    mapping = (
        usable.drop_duplicates("normalized_name")
        .set_index("normalized_name")["iso3"]
        .to_dict()
    )
    mapping.update(COUNTRY_ALIASES)
    mapping.update({name: rule["iso3"] for name, rule in HISTORICAL_ENTITY_RULES.items()})
    clean["ambiguous_normalized_name"] = clean["normalized_name"].isin(ambiguous)
    return mapping, clean


def prepare_sanctions(path: Path, start_year: int, end_year: int) -> pd.DataFrame:
    source = pd.read_csv(path, low_memory=False)
    required = {
        "country", "anchor", "year", "r5_sanctions_directions",
        "r5_active_sanctions_directions", "r5_active_dyadic_rows",
        "r5_distinct_category_count", "fs_distinct_category_count",
        *{f"r5_{name}" for name in R5_FAMILIES},
        *{f"r5_{name}" for name in TRADE_SCOPE_FIELDS},
        *{f"fs_{name}" for name in FS_FIELDS},
    }
    missing = required.difference(source.columns)
    if missing:
        raise KeyError(
            "Corrected GSDB panel is missing the new production fields. "
            f"Rerun the revised GSDB builder. Missing: {sorted(missing)}"
        )

    panel = source[source["year"].between(start_year, end_year)].copy()
    panel["country"] = panel["country"].astype("string").str.strip().str.upper()
    invalid_country = ~panel["country"].str.fullmatch(r"[A-Z]{3}", na=False)
    if invalid_country.any():
        raise ValueError("Corrected GSDB panel contains invalid country keys")
    if panel.duplicated(["country", "anchor", "year"]).any():
        raise ValueError("Corrected GSDB panel contains duplicate production keys")

    rename = {
        "r5_sanctions_directions": "sanctions_directions",
        "r5_active_sanctions_directions": "direction_count",
        "r5_active_dyadic_rows": "r5_dyadic_rows",
        "r5_distinct_category_count": "r5_family_count",
        "fs_distinct_category_count": "fs_subcategory_count",
    }
    rename.update({f"r5_{name}": name for name in R5_FAMILIES + TRADE_SCOPE_FIELDS})
    rename.update({f"fs_{name}": name for name in FS_FIELDS})
    panel = panel.rename(columns=rename)

    numeric_flags = R5_FAMILIES + TRADE_SCOPE_FIELDS + FS_FIELDS
    for column in numeric_flags:
        panel[column] = pd.to_numeric(panel[column], errors="coerce").fillna(0)

    panel["active_sanctions"] = panel["r5_family_count"].fillna(0).gt(0)
    panel["reciprocal_sanctions"] = panel["direction_count"].fillna(0).ge(2)
    panel["complete_trade_any"] = (
        panel["trade_exp_complete"].eq(1) | panel["trade_imp_complete"].eq(1)
    )
    panel["complete_trade_both"] = (
        panel["trade_exp_complete"].eq(1) & panel["trade_imp_complete"].eq(1)
    )
    panel["partial_trade_any"] = (
        panel["trade_exp_partial"].eq(1) | panel["trade_imp_partial"].eq(1)
    )
    return panel


def prepare_drd(
    path: Path,
    country_map: dict[str, str],
    start_year: int,
    end_year: int,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    drd = pd.read_csv(path, low_memory=False)
    required = {
        "country", "anchor", "year", "directed_observations",
        "explicit_adverse_directions",
    }
    missing = required.difference(drd.columns)
    if missing:
        raise KeyError(f"DRD comparison file missing fields: {sorted(missing)}")

    keep = drd[list(required)].copy()
    keep = keep[keep["year"].between(start_year, end_year)].copy()
    keep["drd_country_name"] = keep["country"].astype("string").str.strip()
    keep["normalized_country_name"] = keep["drd_country_name"].map(normalise_name)
    keep["country"] = keep["normalized_country_name"].map(country_map)
    keep["historical_entity"] = keep["normalized_country_name"].isin(
        HISTORICAL_ENTITY_RULES
    )

    for normalized, rule in HISTORICAL_ENTITY_RULES.items():
        mask = keep["normalized_country_name"].eq(normalized)
        outside = mask & ~keep["year"].between(rule["first_year"], rule["last_year"])
        if outside.any():
            examples = keep.loc[outside, ["drd_country_name", "anchor", "year"]]
            raise ValueError(
                f"Historical entity {rule['country_name']} appears outside its "
                f"permitted period: {examples.head(10).to_dict('records')}"
            )

    keep["drd_unilateral_disruption"] = keep["explicit_adverse_directions"].eq(1)
    keep["drd_bilateral_disruption"] = keep["explicit_adverse_directions"].ge(2)

    unresolved = keep[keep["country"].isna()].copy()
    if not unresolved.empty:
        evidence_bearing = unresolved["explicit_adverse_directions"].fillna(0).gt(0)
        detail = unresolved[
            [
                "drd_country_name", "normalized_country_name", "anchor", "year",
                "explicit_adverse_directions",
            ]
        ].drop_duplicates()
        if evidence_bearing.any():
            raise ValueError(
                "Unresolved DRD names carry adverse evidence: "
                f"{detail[evidence_bearing].head(20).to_dict('records')}"
            )
        raise ValueError(
            "Unresolved DRD country names remain. Resolve them before production: "
            f"{detail[['drd_country_name', 'normalized_country_name']].drop_duplicates().to_dict('records')}"
        )

    audit = keep[
        [
            "drd_country_name", "normalized_country_name", "country",
            "historical_entity",
        ]
    ].drop_duplicates().sort_values(["country", "drd_country_name"])

    resolved = keep.drop(columns="historical_entity")
    if resolved.duplicated(["country", "anchor", "year"]).any():
        raise ValueError("Resolved DRD panel contains duplicate production keys")
    return resolved, unresolved, audit


def family_combination(row: pd.Series) -> str:
    active = [name for name in R5_FAMILIES if bool(row[name])]
    return "+".join(active) if active else "none"


def trade_scope_label(row: pd.Series) -> str:
    labels = []
    if row["trade_exp_complete"]:
        labels.append("export_complete")
    if row["trade_imp_complete"]:
        labels.append("import_complete")
    if row["trade_exp_partial"]:
        labels.append("export_partial")
    if row["trade_imp_partial"]:
        labels.append("import_partial")
    return "+".join(labels) if labels else "none"


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


def add_candidate_fields(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    payment_combo = result["fin_payment_infra"].eq(1) & (
        result["trade"].eq(1) | result["fin_services"].eq(1)
    )
    reciprocal_qualified = result["reciprocal_sanctions"] & (
        result["complete_trade_any"]
        | payment_combo
        | result["r5_family_count"].fillna(0).ge(2)
    )
    sanctions_drd = result["active_sanctions"] & (
        result["drd_unilateral_disruption"]
        | result["drd_bilateral_disruption"]
    )

    result["payment_infrastructure_combination"] = payment_combo
    result["reciprocal_severe_qualifier"] = reciprocal_qualified
    result["sanctions_plus_drd_disruption"] = sanctions_drd

    def trigger_list(row: pd.Series) -> str:
        triggers = []
        if bool(row["complete_trade_any"]):
            triggers.append("complete_trade")
        if bool(row["payment_infrastructure_combination"]):
            triggers.append("payment_infrastructure_combination")
        if bool(row["sanctions_plus_drd_disruption"]):
            triggers.append("sanctions_plus_diplomatic_disruption")
        if bool(row["reciprocal_severe_qualifier"]):
            triggers.append("qualified_reciprocal_sanctions")
        if bool(row["drd_bilateral_disruption"]):
            triggers.append("bilateral_operational_diplomatic_rupture")
        return "|".join(triggers)

    result["all_condition_triggers"] = result.apply(trigger_list, axis=1)
    result["severe_trigger_count"] = result["all_condition_triggers"].map(
        lambda value: 0 if not value else len(value.split("|"))
    )

    adverse = (
        result["active_sanctions"]
        | result["drd_unilateral_disruption"]
        | result["drd_bilateral_disruption"]
    )
    severe = (
        result["complete_trade_any"]
        | payment_combo
        | reciprocal_qualified
        | sanctions_drd
    )
    result["condition_three_candidate"] = np.where(adverse, "strained", "normal")
    result["condition_four_candidate"] = np.select(
        [result["drd_bilateral_disruption"], severe, adverse],
        ["ruptured", "severely_strained", "strained"],
        default="normal",
    )
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--gsdb",
        type=Path,
        default=Path("outputs/tables/gsdb/gsdb_country_anchor_year_corrected.csv"),
    )
    parser.add_argument(
        "--drd",
        type=Path,
        default=Path(
            "outputs/tables/diplomatic_representation/"
            "drd_extended_condition_comparison.csv"
        ),
    )
    parser.add_argument(
        "--country-crosswalk",
        type=Path,
        default=Path("outputs/tables/relations_condition/country_crosswalk_audit.csv"),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("outputs/tables/relations_condition"),
    )
    parser.add_argument("--start-year", type=int, default=2000)
    parser.add_argument("--end-year", type=int, default=2024)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    country_map, source_crosswalk = load_country_map(args.country_crosswalk)
    sanctions = prepare_sanctions(args.gsdb, args.start_year, args.end_year)
    drd, unresolved_drd, relationship_crosswalk = prepare_drd(
        args.drd, country_map, args.start_year, args.end_year
    )

    evidence = sanctions.merge(
        drd,
        on=["country", "anchor", "year"],
        how="outer",
        validate="one_to_one",
    )

    numeric_fields = R5_FAMILIES + TRADE_SCOPE_FIELDS + FS_FIELDS + [
        "r5_family_count", "fs_subcategory_count", "r5_dyadic_rows",
        "direction_count", "directed_observations", "explicit_adverse_directions",
    ]
    for column in numeric_fields:
        if column not in evidence:
            evidence[column] = 0
        evidence[column] = pd.to_numeric(evidence[column], errors="coerce").fillna(0)

    boolean_fields = [
        "active_sanctions", "reciprocal_sanctions", "complete_trade_any",
        "complete_trade_both", "partial_trade_any",
        "drd_unilateral_disruption", "drd_bilateral_disruption",
    ]
    for column in boolean_fields:
        if column not in evidence:
            evidence[column] = False
        evidence[column] = evidence[column].map(
            lambda value: False if pd.isna(value) else bool(value)
        ).astype(bool)

    evidence["family_combination"] = evidence.apply(family_combination, axis=1)
    evidence["trade_scope_profile"] = evidence.apply(trade_scope_label, axis=1)
    evidence["combined_evidence_profile"] = evidence.apply(
        combined_evidence_label, axis=1
    )
    evidence = add_candidate_fields(evidence)
    evidence = evidence.sort_values(["year", "anchor", "country"]).reset_index(drop=True)

    invalid_country = ~evidence["country"].astype("string").str.fullmatch(
        r"[A-Z]{3}", na=False
    )
    if invalid_country.any():
        raise ValueError("Harmonised evidence contains invalid country keys")
    if evidence.duplicated(["country", "anchor", "year"]).any():
        raise ValueError("Harmonised evidence contains duplicate production keys")

    severe_cases = evidence[
        evidence["condition_four_candidate"].isin(["severely_strained", "ruptured"])
    ][
        [
            "country", "anchor", "year", "sanctions_directions",
            "family_combination", "trade_scope_profile",
            "drd_unilateral_disruption", "drd_bilateral_disruption",
            "all_condition_triggers", "condition_four_candidate",
        ]
    ]
    trigger_profile = (
        evidence[evidence["all_condition_triggers"].ne("")]
        .groupby(["anchor", "all_condition_triggers"], dropna=False)
        .size().rename("country_anchor_years").reset_index()
        .sort_values(["anchor", "country_anchor_years"], ascending=[True, False])
    )
    state_frequency = (
        evidence.groupby(["year", "anchor", "condition_four_candidate"])
        .size().rename("country_anchor_years").reset_index()
    )

    evidence.to_csv(
        args.output_dir / "condition_evidence_panel_harmonized.csv", index=False
    )
    relationship_crosswalk.to_csv(
        args.output_dir / "relationship_country_crosswalk_audit.csv", index=False
    )
    unresolved_drd.to_csv(
        args.output_dir / "unresolved_drd_country_names.csv", index=False
    )
    severe_cases.to_csv(
        args.output_dir / "severe_candidate_cases.csv", index=False
    )
    trigger_profile.to_csv(
        args.output_dir / "severe_rule_trigger_profile.csv", index=False
    )
    state_frequency.to_csv(
        args.output_dir / "candidate_condition_frequency.csv", index=False
    )

    summary = {
        "study_period": [args.start_year, args.end_year],
        "rows": int(len(evidence)),
        "countries": int(evidence["country"].nunique()),
        "duplicate_keys": int(
            evidence.duplicated(["country", "anchor", "year"]).sum()
        ),
        "invalid_country_keys": int(invalid_country.sum()),
        "resolved_drd_names": int(relationship_crosswalk["drd_country_name"].nunique()),
        "unresolved_drd_names": int(len(unresolved_drd)),
        "historical_entities": (
            relationship_crosswalk[relationship_crosswalk["historical_entity"]]
            ["drd_country_name"].drop_duplicates().tolist()
        ),
        "condition_counts": evidence["condition_four_candidate"].value_counts().to_dict(),
        "rupture_rows": int(evidence["drd_bilateral_disruption"].sum()),
        "source_crosswalk_rows": int(len(source_crosswalk)),
    }
    (args.output_dir / "relationship_condition_evidence_summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )

    print("=" * 72)
    print("RELATIONSHIP CONDITION EVIDENCE PANEL")
    print("=" * 72)
    print(json.dumps(summary, indent=2))
    print("\nOutputs written to:", args.output_dir)


if __name__ == "__main__":
    main()
