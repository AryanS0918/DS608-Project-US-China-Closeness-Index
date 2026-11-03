"""Build the diplomatic subindex from structural ties and UNGA alignment.

Run from the repository root:
    python src/data/build_diplomatic_subindex.py

The complete-data baseline period is 2004-2024. Scores for 2025 are retained
only as a clearly flagged provisional extension because the diplomatic
structural source currently ends in 2024.
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

UNGA_NAME_ALIASES = {
    "Federated States of Micronesia": "FSM",
    "Gambia": "GMB",
    "Saint Vincent and the Grenadines": "VCT",
    "Côte d'Ivoire": "CIV",
    "São Tomé and Príncipe": "STP",
    "Türkiye": "TUR",
}

EXPECTED_LEFT_ONLY = {
    ("SCG", 2004),
    ("SCG", 2005),
    ("SCG", 2006),
    ("TUR", 2025),
}

EXPECTED_INTEGRATION_COUNTS = {
    "both_components_available": 3998,
    "structural_only_unga_no_participation": 13,
    "structural_only_unga_row_unavailable": 3,
    "unga_only_structural_source_year_unavailable": 188,
    "neither_unga_no_participation_and_structural_unavailable": 2,
    "neither_unga_row_missing_and_structural_unavailable": 1,
}


def require_columns(frame: pd.DataFrame, required: set[str], label: str) -> None:
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(f"{label} missing required columns: {missing}")


def build_name_map(country_master: pd.DataFrame) -> dict[str, str]:
    require_columns(
        country_master,
        {"iso3", "country_name", "preferred_country_name", "baseline_index_eligible"},
        "Country master",
    )
    eligible = country_master.loc[country_master["baseline_index_eligible"].eq(True)]
    mapping: dict[str, str] = {}
    for row in eligible.itertuples(index=False):
        for name in (row.country_name, row.preferred_country_name):
            if pd.notna(name):
                mapping[str(name)] = row.iso3
    mapping.update(UNGA_NAME_ALIASES)
    return mapping


def prepare_structural(diplomatic_raw: pd.DataFrame) -> pd.DataFrame:
    require_columns(
        diplomatic_raw,
        {
            "country_iso3",
            "preferred_country_name",
            "anchor",
            "year",
            "diplomatic_structural_score_raw",
            "source_coverage_status",
        },
        "Diplomatic structural panel",
    )
    if diplomatic_raw.duplicated(["country_iso3", "anchor", "year"]).any():
        raise ValueError("Duplicate diplomatic country-anchor-year keys detected.")
    observed = diplomatic_raw["diplomatic_structural_score_raw"].dropna()
    if not observed.between(0, 1).all():
        raise ValueError("Diplomatic structural scores fall outside [0, 1].")
    structural = diplomatic_raw.pivot(
        index=["country_iso3", "preferred_country_name", "year"],
        columns="anchor",
        values="diplomatic_structural_score_raw",
    ).reset_index()
    if not {"China", "United States"}.issubset(structural.columns):
        raise ValueError("Diplomatic panel must contain China and United States anchors.")
    structural["diplomatic_structural_signed_score"] = (
        structural["United States"] - structural["China"]
    )
    signed = structural["diplomatic_structural_signed_score"].dropna()
    if not signed.between(-1, 1).all():
        raise ValueError("Signed diplomatic structural scores fall outside [-1, 1].")
    return structural


def prepare_unga(unga_raw: pd.DataFrame, country_master: pd.DataFrame) -> pd.DataFrame:
    require_columns(
        unga_raw,
        {
            "country_name",
            "year",
            "unga_score_broad",
            "unga_score_strict_yn",
            "score_status",
            "broad_participation_rate",
            "broad_eligible_resolutions",
            "broad_participated_votes",
        },
        "UNGA panel",
    )
    unga = unga_raw.loc[unga_raw["year"].between(PROJECT_START, PROJECT_END)].copy()
    unga["iso3"] = unga["country_name"].map(build_name_map(country_master))
    unresolved = sorted(unga.loc[unga["iso3"].isna(), "country_name"].dropna().unique())
    if unresolved:
        raise ValueError(f"Unmapped UNGA countries: {unresolved}")
    if unga.duplicated(["iso3", "year"]).any():
        raise ValueError("Duplicate UNGA ISO3-year keys detected.")
    if not unga["unga_score_broad"].dropna().between(-1, 1).all():
        raise ValueError("Broad UNGA scores fall outside [-1, 1].")
    valid_statuses = {
        "available",
        "provisionally_insufficient_participation",
        "no_country_participation",
    }
    unexpected = sorted(set(unga["score_status"].dropna()) - valid_statuses)
    if unexpected:
        raise ValueError(f"Unexpected UNGA statuses: {unexpected}")
    return unga


def build_diplomatic_subindex(
    diplomatic_raw: pd.DataFrame,
    unga_raw: pd.DataFrame,
    country_master: pd.DataFrame,
) -> pd.DataFrame:
    structural = prepare_structural(diplomatic_raw)
    unga = prepare_unga(unga_raw, country_master)
    unga_keep = unga[
        [
            "iso3",
            "year",
            "unga_score_broad",
            "unga_score_strict_yn",
            "score_status",
            "broad_participation_rate",
            "broad_eligible_resolutions",
            "broad_participated_votes",
        ]
    ].copy()
    integrated = structural.merge(
        unga_keep,
        left_on=KEYS,
        right_on=["iso3", "year"],
        how="outer",
        validate="one_to_one",
        indicator="join_status",
    )
    if integrated["join_status"].eq("right_only").any():
        bad = integrated.loc[integrated["join_status"].eq("right_only"), ["iso3", "year"]]
        raise ValueError(f"UNGA rows outside production universe: {bad.to_dict('records')}")
    actual_left_only = set(
        integrated.loc[
            integrated["join_status"].eq("left_only"),
            ["country_iso3", "year"],
        ].itertuples(index=False, name=None)
    )
    if actual_left_only != EXPECTED_LEFT_ONLY:
        raise ValueError(
            "Unexpected diplomatic rows without UNGA matches: "
            f"expected {sorted(EXPECTED_LEFT_ONLY)}, found {sorted(actual_left_only)}"
        )

    structural_available = integrated["diplomatic_structural_signed_score"].notna()
    unga_available = integrated["unga_score_broad"].notna()
    both_available = structural_available & unga_available

    integrated["structural_availability_status"] = np.where(
        structural_available,
        "available",
        np.where(
            integrated["year"].eq(2025),
            "source_year_unavailable",
            "unavailable_other",
        ),
    )
    integrated["unga_availability_status"] = np.select(
        [
            unga_available,
            integrated["score_status"].eq("no_country_participation"),
            integrated["join_status"].eq("left_only"),
        ],
        ["available", "no_country_participation", "country_year_row_unavailable"],
        default="unavailable_other",
    )
    integrated["diplomatic_integration_status"] = np.select(
        [
            both_available,
            structural_available
            & ~unga_available
            & integrated["score_status"].eq("no_country_participation"),
            structural_available & integrated["join_status"].eq("left_only"),
            ~structural_available & unga_available,
            ~structural_available
            & ~unga_available
            & integrated["score_status"].eq("no_country_participation"),
            ~structural_available & integrated["join_status"].eq("left_only"),
        ],
        [
            "both_components_available",
            "structural_only_unga_no_participation",
            "structural_only_unga_row_unavailable",
            "unga_only_structural_source_year_unavailable",
            "neither_unga_no_participation_and_structural_unavailable",
            "neither_unga_row_missing_and_structural_unavailable",
        ],
        default="invalid",
    )
    integrated["diplomatic_score"] = np.select(
        [both_available, structural_available, unga_available],
        [
            0.5 * integrated["diplomatic_structural_signed_score"]
            + 0.5 * integrated["unga_score_broad"],
            integrated["diplomatic_structural_signed_score"],
            integrated["unga_score_broad"],
        ],
        default=np.nan,
    )
    integrated["diplomatic_comparability_status"] = np.select(
        [
            integrated["year"].eq(2025) & integrated["diplomatic_score"].notna(),
            integrated["year"].eq(2025) & integrated["diplomatic_score"].isna(),
            integrated["year"].le(COMPARABLE_END) & both_available,
            integrated["year"].le(COMPARABLE_END) & integrated["diplomatic_score"].notna(),
        ],
        [
            "provisional_latest_year_extension",
            "score_unavailable",
            "comparable_complete_component_period",
            "available_component_renormalised",
        ],
        default="invalid",
    )
    output = integrated[
        [
            "country_iso3",
            "preferred_country_name",
            "year",
            "diplomatic_structural_signed_score",
            "structural_availability_status",
            "unga_score_broad",
            "unga_score_strict_yn",
            "score_status",
            "unga_availability_status",
            "broad_participation_rate",
            "diplomatic_integration_status",
            "diplomatic_comparability_status",
            "diplomatic_score",
        ]
    ].sort_values(KEYS).reset_index(drop=True)
    validate_output(output)
    return output


def validate_output(output: pd.DataFrame) -> dict:
    actual_counts = output["diplomatic_integration_status"].value_counts().to_dict()
    if actual_counts != EXPECTED_INTEGRATION_COUNTS:
        raise ValueError(f"Unexpected integration counts: {actual_counts}")
    failures = {
        "rows": int(len(output) != 4205),
        "entities": int(output["country_iso3"].nunique() != 192),
        "duplicate_keys": int(output.duplicated(KEYS).sum()),
        "unexpected_missing_scores": int(output["diplomatic_score"].isna().sum() != 3),
        "score_out_of_bounds": int((~output["diplomatic_score"].dropna().between(-1, 1)).sum()),
        "2025_structural_scores_present": int(
            output.loc[output["year"].eq(2025), "diplomatic_structural_signed_score"].notna().sum()
        ),
        "unexpected_2025_unga_only_count": int(
            output.loc[output["year"].eq(2025), "diplomatic_integration_status"]
            .eq("unga_only_structural_source_year_unavailable")
            .sum()
            != 188
        ),
    }
    if any(failures.values()):
        raise ValueError(f"Diplomatic-subindex validation failed: {failures}")
    return failures


def write_audits(output: pd.DataFrame, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    summary = {
        "rows": int(len(output)),
        "entities": int(output["country_iso3"].nunique()),
        "years": [int(output["year"].min()), int(output["year"].max())],
        "comparable_baseline_period": [PROJECT_START, COMPARABLE_END],
        "provisional_extension_year": 2025,
        "non_missing_scores": int(output["diplomatic_score"].notna().sum()),
        "missing_scores": int(output["diplomatic_score"].isna().sum()),
        "score_min": float(output["diplomatic_score"].min()),
        "score_max": float(output["diplomatic_score"].max()),
        "integration_status_counts": {
            k: int(v) for k, v in output["diplomatic_integration_status"].value_counts().items()
        },
        "comparability_status_counts": {
            k: int(v) for k, v in output["diplomatic_comparability_status"].value_counts().items()
        },
        "validation_failures": validate_output(output),
    }
    (output_dir / "diplomatic_subindex_summary.json").write_text(
        json.dumps(summary, indent=2) + "\n"
    )

    structural_available = output["diplomatic_structural_signed_score"].notna()
    unga_available = output["unga_score_broad"].notna()
    both = structural_available & unga_available
    sensitivity = output[["country_iso3", "preferred_country_name", "year", "diplomatic_score"]].copy()
    sensitivity["diplomatic_score_zero_fill"] = 0.5 * (
        output["diplomatic_structural_signed_score"].fillna(0)
        + output["unga_score_broad"].fillna(0)
    )
    sensitivity["diplomatic_score_structural_emphasis"] = np.select(
        [both, structural_available, unga_available],
        [
            (2 / 3) * output["diplomatic_structural_signed_score"]
            + (1 / 3) * output["unga_score_broad"],
            output["diplomatic_structural_signed_score"],
            output["unga_score_broad"],
        ],
        default=np.nan,
    )
    sensitivity["diplomatic_score_unga_emphasis"] = np.select(
        [both, structural_available, unga_available],
        [
            (1 / 3) * output["diplomatic_structural_signed_score"]
            + (2 / 3) * output["unga_score_broad"],
            output["diplomatic_structural_signed_score"],
            output["unga_score_broad"],
        ],
        default=np.nan,
    )
    strict_available = output["unga_score_strict_yn"].notna()
    sensitivity["diplomatic_score_strict_unga"] = np.select(
        [structural_available & strict_available, structural_available, strict_available],
        [
            0.5 * output["diplomatic_structural_signed_score"]
            + 0.5 * output["unga_score_strict_yn"],
            output["diplomatic_structural_signed_score"],
            output["unga_score_strict_yn"],
        ],
        default=np.nan,
    )
    participation_ok = ~output["score_status"].eq("provisionally_insufficient_participation")
    eligible_unga = output["unga_score_broad"].where(participation_ok)
    eligible_unga_available = eligible_unga.notna()
    sensitivity["diplomatic_score_exclude_provisional_participation"] = np.select(
        [
            structural_available & eligible_unga_available,
            structural_available,
            eligible_unga_available,
        ],
        [
            0.5 * output["diplomatic_structural_signed_score"] + 0.5 * eligible_unga,
            output["diplomatic_structural_signed_score"],
            eligible_unga,
        ],
        default=np.nan,
    )
    sensitivity.to_csv(output_dir / "diplomatic_subindex_sensitivity.csv", index=False)

    disagreement = output.loc[both].copy()
    zero = disagreement["diplomatic_structural_signed_score"].eq(0) | disagreement[
        "unga_score_broad"
    ].eq(0)
    same = np.sign(disagreement["diplomatic_structural_signed_score"]) == np.sign(
        disagreement["unga_score_broad"]
    )
    disagreement["component_sign_agreement"] = np.select(
        [zero, same], ["at_least_one_zero", "same_sign"], default="opposite_sign"
    )
    disagreement["component_gap"] = (
        disagreement["diplomatic_structural_signed_score"] - disagreement["unga_score_broad"]
    ).abs()
    disagreement.sort_values("component_gap", ascending=False).to_csv(
        output_dir / "diplomatic_component_disagreement_cases.csv", index=False
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--diplomatic-structural",
        type=Path,
        default=Path("data/processed/diplomatic_structural_ties_country_anchor_year.csv"),
    )
    parser.add_argument(
        "--unga",
        type=Path,
        default=Path("data/processed/unga_country_year_scores.csv"),
    )
    parser.add_argument(
        "--country-master",
        type=Path,
        default=Path("outputs/tables/relations_condition/relationship_condition_country_master.csv"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/processed/diplomatic_subindex_country_year.csv"),
    )
    parser.add_argument(
        "--audit-directory",
        type=Path,
        default=Path("outputs/tables/diplomatic_subindex"),
    )
    args = parser.parse_args()
    output = build_diplomatic_subindex(
        pd.read_csv(args.diplomatic_structural, low_memory=False),
        pd.read_csv(args.unga, low_memory=False),
        pd.read_csv(args.country_master, low_memory=False),
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    output.to_csv(args.output, index=False)
    write_audits(output, args.audit_directory)
    print(f"Wrote {len(output):,} rows to {args.output}")


if __name__ == "__main__":
    main()
