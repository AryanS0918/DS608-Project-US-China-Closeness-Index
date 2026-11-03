"""Build the verified Security Institutional ties production panel.

The builder expands the normalized security-arrangement membership register
into annual country-anchor-year evidence, applies the canonical country-master
eligibility policy, and scores each observation using the maximum verified
institutional depth divided by three.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

START_YEAR = 2004
END_YEAR = 2025
ANCHORS = ("China", "United States")
ANCHOR_ISO3 = {"China": "CHN", "United States": "USA"}
METHOD = "maximum_verified_security_institution_depth_divided_by_3"
SOURCE = "verified security arrangement membership register"

DEFAULT_REGISTER = Path("data/sources/relations/security_arrangement_membership_register.csv")
DEFAULT_MASTER = Path("outputs/tables/relations_condition/relationship_condition_country_master.csv")
DEFAULT_OUTPUT = Path("data/processed/security_institutional_ties_country_anchor_year.csv")
DEFAULT_SUMMARY = Path("outputs/tables/security_institutional_ties/security_institutional_ties_summary.json")
DEFAULT_EVIDENCE = Path("outputs/tables/security_institutional_ties/security_institutional_evidence_production.csv")

REGISTER_COLUMNS = {
    "arrangement_id",
    "arrangement_name",
    "country_iso3",
    "anchor",
    "start_year",
    "end_year",
    "depth",
    "relationship_type",
    "source_url",
    "source_note",
    "review_status",
}
MASTER_COLUMNS = {
    "iso3",
    "country_name",
    "preferred_country_name",
    "historical_entity",
    "first_valid_year",
    "last_valid_year",
    "baseline_index_eligible",
    "eligibility_rule",
}


def _join_unique(values: pd.Series) -> str:
    return " | ".join(sorted(set(values.dropna().astype(str))))


def _read_boolean(series: pd.Series, column: str) -> pd.Series:
    if pd.api.types.is_bool_dtype(series):
        return series
    lookup = {"true": True, "false": False}
    values = series.astype(str).str.strip().str.lower().map(lookup)
    if values.isna().any():
        bad = sorted(series.loc[values.isna()].astype(str).unique())
        raise ValueError(f"{column} contains non-boolean values: {bad}")
    return values.astype(bool)


def load_register(path: Path) -> pd.DataFrame:
    register = pd.read_csv(path)
    missing = REGISTER_COLUMNS - set(register.columns)
    if missing:
        raise ValueError(f"Membership register is missing columns: {sorted(missing)}")

    register = register.copy()
    register["start_year"] = pd.to_numeric(register["start_year"], errors="raise").astype(int)
    register["end_year"] = pd.to_numeric(register["end_year"], errors="raise").astype(int)
    register["depth"] = pd.to_numeric(register["depth"], errors="raise").astype(int)

    if not register["anchor"].isin(ANCHORS).all():
        raise ValueError("Membership register contains an unsupported anchor.")
    if not register["depth"].isin([1, 2, 3]).all():
        raise ValueError("Membership depth must be 1, 2, or 3.")
    if not register["start_year"].le(register["end_year"]).all():
        raise ValueError("Membership register contains start_year after end_year.")
    if not register["review_status"].eq("verified").all():
        raise ValueError("All baseline membership spells must be verified.")
    if register["source_url"].isna().any():
        raise ValueError("Every membership spell must have a source URL.")
    key = ["arrangement_id", "country_iso3", "anchor", "start_year", "end_year"]
    if register.duplicated(key).any():
        raise ValueError("Membership register contains duplicate spells.")
    return register


def load_country_master(path: Path) -> pd.DataFrame:
    master = pd.read_csv(path)
    missing = MASTER_COLUMNS - set(master.columns)
    if missing:
        raise ValueError(f"Country master is missing columns: {sorted(missing)}")
    if master["iso3"].duplicated().any():
        raise ValueError("Country master contains duplicate ISO3 codes.")
    master = master.copy()
    master["baseline_index_eligible"] = _read_boolean(
        master["baseline_index_eligible"], "baseline_index_eligible"
    )
    return master


def expand_membership_evidence(register: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for spell in register.itertuples(index=False):
        first = max(START_YEAR, int(spell.start_year))
        last = min(END_YEAR, int(spell.end_year))
        if first > last:
            continue
        for year in range(first, last + 1):
            rows.append({**spell._asdict(), "year": year})

    evidence = pd.DataFrame(rows)
    key = ["country_iso3", "anchor", "year", "arrangement_id"]
    if evidence.empty:
        raise ValueError("Membership register produced no evidence in the production window.")
    if evidence.duplicated(key).any():
        raise ValueError("Expanded evidence contains duplicate arrangement-year keys.")
    self_relation = evidence["country_iso3"].eq(evidence["anchor"].map(ANCHOR_ISO3))
    if self_relation.any():
        raise ValueError("Expanded evidence contains anchor self-relations.")
    maximum = evidence.groupby(["country_iso3", "anchor", "year"])["depth"].transform("max")
    evidence["controls_score"] = evidence["depth"].eq(maximum)
    return evidence


def build_eligible_grid(master: pd.DataFrame) -> pd.DataFrame:
    eligible = master.loc[
        master["baseline_index_eligible"],
        [
            "iso3",
            "country_name",
            "preferred_country_name",
            "first_valid_year",
            "last_valid_year",
            "eligibility_rule",
        ],
    ].copy()

    grid = pd.MultiIndex.from_product(
        [eligible["iso3"], ANCHORS, range(START_YEAR, END_YEAR + 1)],
        names=["country_iso3", "anchor", "year"],
    ).to_frame(index=False)
    grid = grid.merge(
        eligible.rename(columns={"iso3": "country_iso3"}),
        on="country_iso3",
        how="left",
        validate="many_to_one",
    )

    always = grid["eligibility_rule"].eq("eligible_all_project_years")
    conditioned = grid["eligibility_rule"].eq("eligible_only_within_validity_interval")
    within = (
        conditioned
        & grid["first_valid_year"].notna()
        & grid["last_valid_year"].notna()
        & grid["year"].between(grid["first_valid_year"], grid["last_valid_year"])
    )
    unsupported = ~(always | conditioned)
    if unsupported.any():
        rules = sorted(grid.loc[unsupported, "eligibility_rule"].dropna().unique())
        raise ValueError(f"Eligible master rows use unsupported eligibility rules: {rules}")

    grid = grid.loc[always | within].copy()
    grid = grid.loc[grid["country_iso3"] != grid["anchor"].map(ANCHOR_ISO3)]
    return grid.drop(columns=["first_valid_year", "last_valid_year", "eligibility_rule"])


def build_panel(register: pd.DataFrame, master: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    evidence = expand_membership_evidence(register)
    grid = build_eligible_grid(master)

    summary = evidence.groupby(["country_iso3", "anchor", "year"], as_index=False).agg(
        maximum_depth=("depth", "max"),
        active_arrangement_count=("arrangement_id", "nunique"),
        supporting_arrangements=("arrangement_name", _join_unique),
        relationship_types=("relationship_type", _join_unique),
    )
    controlling = (
        evidence.loc[evidence["controls_score"]]
        .groupby(["country_iso3", "anchor", "year"], as_index=False)
        .agg(controlling_arrangements=("arrangement_name", _join_unique))
    )
    summary = summary.merge(
        controlling,
        on=["country_iso3", "anchor", "year"],
        how="left",
        validate="one_to_one",
    )

    panel = grid.merge(
        summary,
        on=["country_iso3", "anchor", "year"],
        how="left",
        validate="one_to_one",
    )
    panel["maximum_depth"] = panel["maximum_depth"].fillna(0).astype(int)
    panel["active_arrangement_count"] = panel["active_arrangement_count"].fillna(0).astype(int)
    for column in ["controlling_arrangements", "supporting_arrangements", "relationship_types"]:
        panel[column] = panel[column].fillna("")

    panel["observed"] = True
    panel["status"] = np.where(
        panel["maximum_depth"].gt(0), "observed_active_tie", "observed_no_active_tie"
    )
    panel["security_institutional_score_raw"] = panel["maximum_depth"] / 3
    panel["source_completeness_status"] = "verified_baseline_scope"
    panel["method"] = METHOD
    panel["source"] = SOURCE

    columns = [
        "country_iso3",
        "country_name",
        "preferred_country_name",
        "anchor",
        "year",
        "observed",
        "status",
        "maximum_depth",
        "active_arrangement_count",
        "controlling_arrangements",
        "supporting_arrangements",
        "relationship_types",
        "security_institutional_score_raw",
        "source_completeness_status",
        "method",
        "source",
    ]
    panel = panel[columns].sort_values(["country_iso3", "anchor", "year"]).reset_index(drop=True)
    validate_panel(panel)
    return panel, evidence


def validate_panel(panel: pd.DataFrame) -> None:
    key = ["country_iso3", "anchor", "year"]
    if panel.duplicated(key).any():
        raise ValueError("Production panel contains duplicate country-anchor-year keys.")
    if not panel["year"].between(START_YEAR, END_YEAR).all():
        raise ValueError("Production panel contains years outside the supported window.")
    if not panel["security_institutional_score_raw"].between(0, 1).all():
        raise ValueError("Production score falls outside [0, 1].")
    permitted = {0.0, 1 / 3, 2 / 3, 1.0}
    if not set(panel["security_institutional_score_raw"].unique()).issubset(permitted):
        raise ValueError("Production panel contains an unsupported score value.")
    no_tie = panel["status"].eq("observed_no_active_tie")
    if not panel.loc[no_tie, "security_institutional_score_raw"].eq(0).all():
        raise ValueError("Observed no-tie rows must score zero.")
    self_relation = panel["country_iso3"].eq(panel["anchor"].map(ANCHOR_ISO3))
    if self_relation.any():
        raise ValueError("Production panel contains anchor self-relations.")


def build_summary(panel: pd.DataFrame, evidence: pd.DataFrame) -> dict[str, object]:
    active = panel["status"].eq("observed_active_tie")
    return {
        "method": METHOD,
        "source": SOURCE,
        "start_year": START_YEAR,
        "end_year": END_YEAR,
        "rows": int(len(panel)),
        "rows_by_anchor": {k: int(v) for k, v in panel.groupby("anchor").size().items()},
        "active_rows_by_anchor": {
            k: int(v) for k, v in panel.loc[active].groupby("anchor").size().items()
        },
        "verified_evidence_rows": int(len(evidence)),
        "arrangements": int(evidence["arrangement_id"].nunique()),
        "membership_spells": int(
            evidence[["arrangement_id", "country_iso3", "anchor", "start_year", "end_year"]]
            .drop_duplicates()
            .shape[0]
        ),
        "score_values": sorted(float(x) for x in panel["security_institutional_score_raw"].unique()),
        "historical_overlap": {
            "SCG": sorted(int(x) for x in panel.loc[panel["country_iso3"].eq("SCG"), "year"].unique())
        },
    }


def run(
    register_path: Path = DEFAULT_REGISTER,
    master_path: Path = DEFAULT_MASTER,
    output_path: Path = DEFAULT_OUTPUT,
    summary_path: Path = DEFAULT_SUMMARY,
    evidence_path: Path = DEFAULT_EVIDENCE,
) -> tuple[pd.DataFrame, dict[str, object]]:
    register = load_register(register_path)
    master = load_country_master(master_path)
    panel, evidence = build_panel(register, master)
    summary = build_summary(panel, evidence)

    for path in [output_path, summary_path, evidence_path]:
        path.parent.mkdir(parents=True, exist_ok=True)
    panel.to_csv(output_path, index=False)
    evidence.to_csv(evidence_path, index=False)
    summary_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return panel, summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--register", type=Path, default=DEFAULT_REGISTER)
    parser.add_argument("--master", type=Path, default=DEFAULT_MASTER)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--summary", type=Path, default=DEFAULT_SUMMARY)
    parser.add_argument("--evidence", type=Path, default=DEFAULT_EVIDENCE)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    panel, summary = run(args.register, args.master, args.output, args.summary, args.evidence)
    print(f"Wrote {args.output} ({len(panel):,} rows)")
    print(f"Wrote {args.evidence}")
    print(f"Wrote {args.summary}")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
