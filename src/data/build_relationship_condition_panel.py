"""Build the final country-anchor-year relationship-condition panel.

Run from the repository root:
    python -u src/data/build_relationship_condition_panel.py

The classifier consumes the harmonised relationship-evidence panel, builds a
symmetric year-specific country universe across the China and United States
anchors, supplies canonical display names, preserves historical entities,
separates controlling from contributing triggers, and validates the four-state
hierarchy before writing production outputs.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

ANCHORS = ("China", "United States")
CONDITION_ORDER = {
    "normal": 0,
    "strained": 1,
    "severely_strained": 2,
    "ruptured": 3,
}
SELF_RELATIONS = {("CHN", "China"), ("USA", "United States")}
HISTORICAL_ENTITIES = {
    "SCG": {
        "country_name": "Serbia and Montenegro",
        "first_year": 2000,
        "last_year": 2006,
    }
}
NAME_OVERRIDES = {
    "BHS": "Bahamas",
    "BOL": "Bolivia",
    "BRN": "Brunei",
    "CHN": "China",
    "COD": "Democratic Republic of the Congo",
    "COG": "Republic of the Congo",
    "CIV": "Cote d'Ivoire",
    "CPV": "Cabo Verde",
    "CZE": "Czechia",
    "FSM": "Micronesia",
    "IRN": "Iran",
    "KOR": "South Korea",
    "KSV": "Kosovo",
    "LAO": "Laos",
    "MDA": "Moldova",
    "MMR": "Myanmar",
    "PRK": "North Korea",
    "PSE": "Palestine",
    "RUS": "Russia",
    "SCG": "Serbia and Montenegro",
    "SYR": "Syria",
    "TZA": "Tanzania",
    "USA": "United States",
    "VAT": "Holy See",
    "VEN": "Venezuela",
    "VNM": "Vietnam",
}


def require_columns(frame: pd.DataFrame, columns: set[str], label: str) -> None:
    missing = columns.difference(frame.columns)
    if missing:
        raise KeyError(f"{label} is missing fields: {sorted(missing)}")


def to_bool(series: pd.Series) -> pd.Series:
    truthy = {"1", "true", "t", "yes", "y"}
    falsy = {"0", "false", "f", "no", "n", "", "nan", "none", "<na>"}

    def convert(value: Any) -> bool:
        if pd.isna(value):
            return False
        if isinstance(value, (bool, np.bool_)):
            return bool(value)
        if isinstance(value, (int, float, np.integer, np.floating)):
            return bool(value)
        text = str(value).strip().lower()
        if text in truthy:
            return True
        if text in falsy:
            return False
        raise ValueError(f"Unexpected boolean token: {value!r}")

    return series.map(convert).astype(bool)


def preferred_country_name(values: pd.Series) -> str:
    names = sorted({str(value).strip() for value in values.dropna() if str(value).strip()})
    if not names:
        return ""

    def score(name: str) -> tuple[int, int, str]:
        lowered = name.lower()
        penalty = 0
        penalty += 8 if "," in name else 0
        penalty += 6 if any(token in lowered for token in ["former", "democratic people's", "republic of"]) else 0
        penalty += 4 if name.endswith(", The") else 0
        penalty += 2 if " and " in lowered and len(name) > 28 else 0
        return penalty, len(name), name

    return min(names, key=score)


def build_country_master(
    source_crosswalk_path: Path,
    relationship_crosswalk_path: Path,
    evidence: pd.DataFrame,
) -> pd.DataFrame:
    source = pd.read_csv(source_crosswalk_path, low_memory=False)
    require_columns(source, {"source_name", "iso3"}, "Source country crosswalk")

    candidates = source[["iso3", "source_name"]].rename(
        columns={"source_name": "candidate_name"}
    )

    if relationship_crosswalk_path.exists():
        relationship = pd.read_csv(relationship_crosswalk_path, low_memory=False)
        require_columns(
            relationship,
            {"country", "drd_country_name"},
            "Relationship country crosswalk",
        )
        relationship_candidates = relationship[["country", "drd_country_name"]].rename(
            columns={"country": "iso3", "drd_country_name": "candidate_name"}
        )
        candidates = pd.concat(
            [candidates, relationship_candidates], ignore_index=True
        )

    candidates["iso3"] = candidates["iso3"].astype("string").str.strip().str.upper()
    candidates = candidates[
        candidates["iso3"].str.fullmatch(r"[A-Z]{3}", na=False)
    ].copy()

    names = (
        candidates.groupby("iso3")["candidate_name"]
        .agg(preferred_country_name)
        .rename("country_name")
        .reset_index()
    )
    names["country_name"] = names.apply(
        lambda row: NAME_OVERRIDES.get(row["iso3"], row["country_name"]),
        axis=1,
    )

    missing_iso = sorted(set(evidence["country"]) - set(names["iso3"]))
    if missing_iso:
        raise ValueError(
            "Canonical country names are missing for evidence identifiers: "
            f"{missing_iso}"
        )

    names["historical_entity"] = names["iso3"].isin(HISTORICAL_ENTITIES)
    names["first_valid_year"] = names["iso3"].map(
        {iso3: rule["first_year"] for iso3, rule in HISTORICAL_ENTITIES.items()}
    )
    names["last_valid_year"] = names["iso3"].map(
        {iso3: rule["last_year"] for iso3, rule in HISTORICAL_ENTITIES.items()}
    )
    return names.sort_values("iso3").reset_index(drop=True)


def build_production_universe(evidence: pd.DataFrame) -> pd.DataFrame:
    """Create both anchor comparisons for every country observed in a year.

    A country enters the universe in a given year if it appears for either
    anchor in the harmonised evidence. The opposite anchor-year is then added
    and filled as normal when no adverse evidence exists. Anchor self-relations
    are excluded. Historical entities are restricted to their documented span.
    """

    country_years = evidence[["country", "year"]].drop_duplicates()
    anchors = pd.DataFrame({"anchor": ANCHORS})
    country_years["_join"] = 1
    anchors["_join"] = 1
    universe = country_years.merge(anchors, on="_join").drop(columns="_join")

    self_relation = pd.Series(False, index=universe.index)
    for iso3, anchor in SELF_RELATIONS:
        self_relation |= universe["country"].eq(iso3) & universe["anchor"].eq(anchor)
    universe = universe.loc[~self_relation].copy()

    for iso3, rule in HISTORICAL_ENTITIES.items():
        invalid = universe["country"].eq(iso3) & ~universe["year"].between(
            rule["first_year"], rule["last_year"]
        )
        universe = universe.loc[~invalid].copy()

    if universe.duplicated(["country", "anchor", "year"]).any():
        raise ValueError("Production universe contains duplicate keys")
    return universe.sort_values(["year", "country", "anchor"]).reset_index(drop=True)


def fill_evidence_defaults(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    boolean_columns = [
        "active_sanctions",
        "drd_unilateral_disruption",
        "drd_bilateral_disruption",
        "complete_trade_any",
        "complete_trade_both",
        "partial_trade_any",
        "reciprocal_sanctions",
        "payment_infrastructure_combination",
        "reciprocal_severe_qualifier",
        "sanctions_plus_drd_disruption",
    ]
    for column in boolean_columns:
        if column not in result:
            result[column] = False
        result[column] = to_bool(result[column])

    numeric_columns = [
        "r5_family_count",
        "fs_subcategory_count",
        "directed_observations",
        "explicit_adverse_directions",
    ]
    for column in numeric_columns:
        if column not in result:
            result[column] = 0
        result[column] = pd.to_numeric(result[column], errors="coerce").fillna(0)

    text_defaults = {
        "family_combination": "none",
        "trade_scope_profile": "none",
        "combined_evidence_profile": "no_adverse_evidence",
        "sanctions_directions": "none",
        "all_condition_triggers": "",
    }
    for column, default in text_defaults.items():
        if column not in result:
            result[column] = default
        result[column] = result[column].fillna(default).astype(str)
    return result


def construct_all_triggers(row: pd.Series) -> str:
    triggers = [
        token
        for token in str(row.get("all_condition_triggers", "")).split("|")
        if token
    ]
    if row["active_sanctions"] and not triggers:
        triggers.append("active_sanctions")
    if row["drd_unilateral_disruption"] and not row["active_sanctions"]:
        triggers.append("unilateral_operational_diplomatic_disruption")
    if not triggers:
        triggers.append("no_qualifying_adverse_evidence")
    return "|".join(dict.fromkeys(triggers))


def controlling_trigger(row: pd.Series) -> str:
    if row["drd_bilateral_disruption"]:
        return "bilateral_operational_diplomatic_rupture"
    if row["complete_trade_any"]:
        return "complete_trade"
    if row["payment_infrastructure_combination"]:
        return "payment_infrastructure_combination"
    if row["sanctions_plus_drd_disruption"]:
        return "sanctions_plus_diplomatic_disruption"
    if row["reciprocal_severe_qualifier"]:
        return "qualified_reciprocal_sanctions"
    if row["drd_unilateral_disruption"]:
        return "unilateral_operational_diplomatic_disruption"
    if row["active_sanctions"]:
        return "active_sanctions"
    return "no_qualifying_adverse_evidence"


def classify_condition(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    adverse = (
        result["active_sanctions"]
        | result["drd_unilateral_disruption"]
        | result["drd_bilateral_disruption"]
    )
    severe = (
        result["complete_trade_any"]
        | result["payment_infrastructure_combination"]
        | result["sanctions_plus_drd_disruption"]
        | result["reciprocal_severe_qualifier"]
    )
    result["relationship_condition"] = np.select(
        [result["drd_bilateral_disruption"], severe, adverse],
        ["ruptured", "severely_strained", "strained"],
        default="normal",
    )
    result["relationship_condition_severity"] = result[
        "relationship_condition"
    ].map(CONDITION_ORDER).astype("int8")
    result["all_condition_triggers"] = result.apply(
        construct_all_triggers, axis=1
    )
    result["controlling_condition_trigger"] = result.apply(
        controlling_trigger, axis=1
    )
    return result


def validate_production(production: pd.DataFrame) -> dict[str, Any]:
    keys = ["country_iso3", "anchor", "year"]
    duplicate_keys = int(production.duplicated(keys).sum())
    blank_names = int(
        production["country_name"].isna().sum()
        + production["country_name"].astype("string").str.strip().eq("").sum()
    )
    severity_mismatches = int(
        (
            production["relationship_condition"].map(CONDITION_ORDER)
            != production["relationship_condition_severity"]
        ).sum()
    )
    rupture_without_bilateral = int(
        (
            production["relationship_condition"].eq("ruptured")
            & ~production["drd_bilateral_disruption"]
        ).sum()
    )
    bilateral_without_rupture = int(
        (
            production["drd_bilateral_disruption"]
            & ~production["relationship_condition"].eq("ruptured")
        ).sum()
    )
    wrong_rupture_controller = int(
        (
            production["relationship_condition"].eq("ruptured")
            & ~production["controlling_condition_trigger"].eq(
                "bilateral_operational_diplomatic_rupture"
            )
        ).sum()
    )
    missing_trigger = int(
        production["all_condition_triggers"].astype("string").str.strip().eq("").sum()
    )

    historical_violations = 0
    for iso3, rule in HISTORICAL_ENTITIES.items():
        historical_violations += int(
            (
                production["country_iso3"].eq(iso3)
                & ~production["year"].between(
                    rule["first_year"], rule["last_year"]
                )
            ).sum()
        )

    metrics = {
        "rows": int(len(production)),
        "countries_or_historical_entities": int(
            production["country_iso3"].nunique()
        ),
        "duplicate_keys": duplicate_keys,
        "blank_country_names": blank_names,
        "severity_mismatches": severity_mismatches,
        "rupture_without_bilateral_disruption": rupture_without_bilateral,
        "bilateral_disruption_without_rupture": bilateral_without_rupture,
        "wrong_rupture_controller": wrong_rupture_controller,
        "missing_all_condition_triggers": missing_trigger,
        "historical_period_violations": historical_violations,
    }
    failures = {
        key: value
        for key, value in metrics.items()
        if key not in {"rows", "countries_or_historical_entities"} and value != 0
    }
    if failures:
        raise AssertionError(f"Production validation failed: {failures}")
    return metrics


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--evidence",
        type=Path,
        default=Path(
            "outputs/tables/relations_condition/"
            "condition_evidence_panel_harmonized.csv"
        ),
    )
    parser.add_argument(
        "--source-crosswalk",
        type=Path,
        default=Path(
            "outputs/tables/relations_condition/country_crosswalk_audit.csv"
        ),
    )
    parser.add_argument(
        "--relationship-crosswalk",
        type=Path,
        default=Path(
            "outputs/tables/relations_condition/"
            "relationship_country_crosswalk_audit.csv"
        ),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(
            "data/processed/relationship_condition_country_anchor_year.csv"
        ),
    )
    parser.add_argument(
        "--report-directory",
        type=Path,
        default=Path("outputs/tables/relations_condition"),
    )
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.report_directory.mkdir(parents=True, exist_ok=True)

    evidence = pd.read_csv(args.evidence, low_memory=False)
    require_columns(
        evidence,
        {
            "country", "anchor", "year", "active_sanctions",
            "drd_unilateral_disruption", "drd_bilateral_disruption",
            "all_condition_triggers",
        },
        "Harmonised relationship evidence",
    )
    evidence["country"] = evidence["country"].astype("string").str.strip().str.upper()
    if (~evidence["country"].str.fullmatch(r"[A-Z]{3}", na=False)).any():
        raise ValueError("Evidence contains invalid ISO3 identifiers")
    if evidence.duplicated(["country", "anchor", "year"]).any():
        raise ValueError("Evidence contains duplicate production keys")

    country_master = build_country_master(
        args.source_crosswalk,
        args.relationship_crosswalk,
        evidence,
    )
    universe = build_production_universe(evidence)
    merged = universe.merge(
        evidence,
        on=["country", "anchor", "year"],
        how="left",
        validate="one_to_one",
        indicator="evidence_merge_status",
    )
    merged = fill_evidence_defaults(merged)
    production = classify_condition(merged)
    production = production.rename(columns={"country": "country_iso3"})
    production = production.merge(
        country_master,
        left_on="country_iso3",
        right_on="iso3",
        how="left",
        validate="many_to_one",
    ).drop(columns="iso3")
    production["historical_entity"] = production[
        "historical_entity"
    ].fillna(False).astype(bool)

    metrics = validate_production(production)

    output_columns = [
        "country_iso3", "country_name", "historical_entity",
        "first_valid_year", "last_valid_year", "anchor", "year",
        "relationship_condition", "relationship_condition_severity",
        "controlling_condition_trigger", "all_condition_triggers",
        "active_sanctions", "drd_unilateral_disruption",
        "drd_bilateral_disruption", "complete_trade_any",
        "complete_trade_both", "reciprocal_sanctions",
        "payment_infrastructure_combination",
        "sanctions_plus_drd_disruption", "reciprocal_severe_qualifier",
        "family_combination", "trade_scope_profile",
        "combined_evidence_profile", "sanctions_directions",
        "evidence_merge_status",
    ]
    production = production[output_columns].sort_values(
        ["year", "country_iso3", "anchor"]
    ).reset_index(drop=True)

    condition_frequency = (
        production.groupby(["year", "anchor", "relationship_condition"])
        .size().rename("country_anchor_years").reset_index()
    )
    trigger_profile = (
        production.groupby(
            [
                "anchor", "relationship_condition",
                "controlling_condition_trigger", "all_condition_triggers",
            ],
            dropna=False,
        )
        .size().rename("country_anchor_years").reset_index()
        .sort_values(
            ["anchor", "relationship_condition", "country_anchor_years"],
            ascending=[True, True, False],
        )
    )
    ruptures = production[
        production["relationship_condition"].eq("ruptured")
    ].copy()
    coverage = (
        production.groupby(["year", "anchor"])
        .agg(
            country_anchor_years=("country_iso3", "size"),
            countries=("country_iso3", "nunique"),
            evidence_rows=(
                "evidence_merge_status",
                lambda values: int(values.eq("both").sum()),
            ),
            grid_filled_rows=(
                "evidence_merge_status",
                lambda values: int(values.eq("left_only").sum()),
            ),
        )
        .reset_index()
    )

    if len(ruptures) != 1:
        raise AssertionError(f"Expected one rupture row, found {len(ruptures)}")
    expected_rupture = ruptures.iloc[0]
    if not (
        expected_rupture["country_iso3"] == "AFG"
        and expected_rupture["anchor"] == "United States"
        and int(expected_rupture["year"]) == 2021
    ):
        raise AssertionError("The expected AFG-US 2021 rupture row changed")

    production.to_csv(args.output, index=False)
    country_master.to_csv(
        args.report_directory / "relationship_condition_country_master.csv",
        index=False,
    )
    universe.to_csv(
        args.report_directory / "relationship_condition_production_universe.csv",
        index=False,
    )
    condition_frequency.to_csv(
        args.report_directory / "relationship_condition_frequency.csv",
        index=False,
    )
    trigger_profile.to_csv(
        args.report_directory / "relationship_condition_trigger_profile.csv",
        index=False,
    )
    ruptures.to_csv(
        args.report_directory / "relationship_condition_rupture_cases.csv",
        index=False,
    )
    coverage.to_csv(
        args.report_directory / "relationship_condition_grid_coverage.csv",
        index=False,
    )
    (args.report_directory / "relationship_condition_production_summary.json").write_text(
        json.dumps(
            {
                **metrics,
                "study_period": [
                    int(production["year"].min()),
                    int(production["year"].max()),
                ],
                "condition_counts": production[
                    "relationship_condition"
                ].value_counts().to_dict(),
                "rupture_key": {
                    "country_iso3": "AFG",
                    "country_name": "Afghanistan",
                    "anchor": "United States",
                    "year": 2021,
                },
                "universe_rule": (
                    "For each year, include both anchor comparisons for every "
                    "country observed for either anchor, excluding anchor self-"
                    "relations and restricting historical entities to their "
                    "documented existence period."
                ),
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    print("=" * 72)
    print("RELATIONSHIP CONDITION PRODUCTION PANEL")
    print("=" * 72)
    print(
        json.dumps(
            {
                **metrics,
                "condition_counts": production[
                    "relationship_condition"
                ].value_counts().to_dict(),
            },
            indent=2,
        )
    )
    print("\nOutputs written to:", args.output)
    print("Reports written to:", args.report_directory)


if __name__ == "__main__":
    main()
