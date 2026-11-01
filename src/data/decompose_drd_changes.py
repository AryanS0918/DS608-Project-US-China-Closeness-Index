"""Decompose DRD changes into rank, focus, and explicit-adversity events.

Complete runnable example.

Run from the repository root:
    python -u src/data/decompose_drd_changes.py

Input:
    data/interim/relations/drd_anchor_directed_country_year.parquet

Outputs:
    outputs/tables/diplomatic_representation/drd_change_events.csv
    outputs/tables/diplomatic_representation/drd_change_event_frequency.csv
    outputs/tables/diplomatic_representation/drd_rank_downgrade_candidates.csv
    outputs/tables/diplomatic_representation/drd_focus_only_changes.csv
    outputs/tables/diplomatic_representation/drd_explicit_adverse_events.csv
    outputs/tables/diplomatic_representation/drd_extended_condition_comparison.csv
    outputs/tables/diplomatic_representation/drd_change_summary.json

The script preserves the conservative DRD condition based only on explicit
adverse coding. Non-zero rank downgrades are retained separately as candidate
strain events for empirical review.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

DEFAULT_INPUT = Path(
    "data/interim/relations/drd_anchor_directed_country_year.parquet"
)
DEFAULT_OUTPUT_DIR = Path("outputs/tables/diplomatic_representation")

CONDITION_SEVERITY = {
    "missing": -1,
    "normal": 0,
    "strained": 1,
    "severely_strained": 2,
    "ruptured": 3,
}

# Embassy codes 2-6 are substantively ordered by the codebook. Code 1 means
# representation exists but the level is unknown, so rank comparisons involving
# code 1 are indeterminate rather than genuine upgrades or downgrades.
KNOWN_EMBASSY_CODES = {2, 3, 4, 5, 6}


def as_number(value: Any) -> float:
    return pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]


def classify_directed_change(row: pd.Series) -> str:
    """Classify one directed observation relative to the prior calendar year."""
    current_lor = row["LOR"]
    previous_lor = row["previous_lor"]
    current_embassy = row["Embassy"]
    previous_embassy = row["previous_embassy"]
    current_focus = row["Focus"]
    previous_focus = row["previous_focus"]

    if pd.isna(previous_lor):
        return "newly_observed"

    if current_lor == 0 or current_focus == 3:
        return "explicit_adverse_event"

    if previous_lor == 0 and current_lor > 0:
        return "restoration_from_adverse"

    if (
        pd.isna(current_embassy)
        or pd.isna(previous_embassy)
        or int(current_embassy) == 1
        or int(previous_embassy) == 1
    ):
        if current_lor == previous_lor and current_focus == previous_focus:
            return "stable"
        return "indeterminate_rank_change"

    rank_change = int(current_embassy) - int(previous_embassy)
    focus_change = int(current_focus) - int(previous_focus)

    if rank_change == 0 and focus_change == 0:
        return "stable"
    if rank_change == 0 and focus_change > 0:
        return "focus_only_reduction"
    if rank_change == 0 and focus_change < 0:
        return "focus_only_increase"
    if rank_change < 0 and focus_change == 0:
        return "rank_downgrade"
    if rank_change > 0 and focus_change == 0:
        return "rank_upgrade"
    if rank_change < 0 and focus_change > 0:
        return "rank_and_focus_downgrade"
    if rank_change > 0 and focus_change < 0:
        return "rank_and_focus_upgrade"

    # Mixed movements such as a lower rank but more dedicated focus should not
    # be given a directional interpretation without additional assumptions.
    return "mixed_rank_focus_change"


def conservative_condition(group: pd.DataFrame) -> str:
    """Use explicit adverse records only for the DRD condition signal."""
    observed = group[group["LOR"].notna()]
    if observed.empty:
        return "missing"
    adverse = observed["explicit_adverse"].sum()
    if len(observed) == 2 and adverse == 2:
        return "ruptured"
    if adverse >= 1:
        return "severely_strained"
    return "normal"


def extended_candidate_condition(group: pd.DataFrame) -> str:
    """Add selected non-zero rank downgrades as candidate strain events."""
    baseline = conservative_condition(group)
    if baseline in {"ruptured", "severely_strained", "missing"}:
        return baseline

    qualifying = group["candidate_strain_event"].fillna(False)
    if qualifying.sum() >= 1:
        return "strained"
    return "normal"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--start-year", type=int, default=2000)
    parser.add_argument("--end-year", type=int, default=2024)
    args = parser.parse_args()

    args.output_dir.mkdir(parents=True, exist_ok=True)

    directed = pd.read_parquet(args.input)
    required = {
        "country", "anchor", "year", "direction", "LOR", "Embassy", "Focus"
    }
    missing = required.difference(directed.columns)
    if missing:
        raise KeyError(f"Input is missing required columns: {sorted(missing)}")

    directed = directed[
        directed["year"].between(args.start_year, args.end_year, inclusive="both")
    ].copy()

    for column in ["LOR", "Embassy", "Focus"]:
        directed[column] = pd.to_numeric(directed[column], errors="coerce")

    directed = directed.sort_values(
        ["country", "anchor", "direction", "year"]
    ).reset_index(drop=True)

    key_columns = ["country", "anchor", "year", "direction"]
    duplicate_keys = int(directed.duplicated(key_columns).sum())
    if duplicate_keys:
        raise ValueError(f"Found {duplicate_keys} duplicate directed keys")

    groups = directed.groupby(["country", "anchor", "direction"], sort=False)
    directed["previous_year"] = groups["year"].shift(1)
    directed["previous_lor"] = groups["LOR"].shift(1)
    directed["previous_embassy"] = groups["Embassy"].shift(1)
    directed["previous_focus"] = groups["Focus"].shift(1)
    directed["consecutive_previous_year"] = directed["previous_year"].eq(
        directed["year"] - 1
    )

    previous_fields = ["previous_lor", "previous_embassy", "previous_focus"]
    directed.loc[~directed["consecutive_previous_year"], previous_fields] = np.nan

    directed["lor_change"] = directed["LOR"] - directed["previous_lor"]
    directed["embassy_change"] = (
        directed["Embassy"] - directed["previous_embassy"]
    )
    directed["focus_change"] = directed["Focus"] - directed["previous_focus"]
    directed["explicit_adverse"] = directed["LOR"].eq(0) | directed["Focus"].eq(3)
    directed["change_event"] = directed.apply(classify_directed_change, axis=1)

    directed["candidate_strain_event"] = directed["change_event"].isin(
        ["rank_downgrade", "rank_and_focus_downgrade"]
    ) & directed["LOR"].gt(0)

    # Mark reciprocal events where both directed relationships show the same
    # broad type of non-zero downgrade in the same country-anchor-year.
    directional_summary = (
        directed.groupby(["country", "anchor", "year"])
        .agg(
            directed_observations=("direction", "nunique"),
            explicit_adverse_directions=("explicit_adverse", "sum"),
            candidate_strain_directions=("candidate_strain_event", "sum"),
        )
        .reset_index()
    )
    directional_summary["reciprocal_candidate_strain"] = (
        directional_summary["directed_observations"].eq(2)
        & directional_summary["candidate_strain_directions"].eq(2)
    )

    country_anchor_groups = directed.groupby(
        ["country", "anchor", "year"], group_keys=False
    )
    conservative = (
        country_anchor_groups.apply(conservative_condition, include_groups=False)
        .rename("drd_condition_conservative")
        .reset_index()
    )
    extended = (
        country_anchor_groups.apply(
            extended_candidate_condition, include_groups=False
        )
        .rename("drd_condition_extended_candidate")
        .reset_index()
    )
    comparison = (
        conservative.merge(
            extended, on=["country", "anchor", "year"], validate="one_to_one"
        )
        .merge(
            directional_summary,
            on=["country", "anchor", "year"],
            validate="one_to_one",
        )
    )
    comparison["conservative_severity"] = comparison[
        "drd_condition_conservative"
    ].map(CONDITION_SEVERITY)
    comparison["extended_candidate_severity"] = comparison[
        "drd_condition_extended_candidate"
    ].map(CONDITION_SEVERITY)

    event_frequency = (
        directed.groupby(["year", "anchor", "direction", "change_event"])
        .size()
        .rename("events")
        .reset_index()
        .sort_values(["year", "anchor", "direction", "change_event"])
    )

    rank_candidates = directed[directed["candidate_strain_event"]].copy()
    focus_only = directed[
        directed["change_event"].isin(
            ["focus_only_reduction", "focus_only_increase"]
        )
    ].copy()
    explicit_adverse = directed[directed["explicit_adverse"]].copy()

    directed.to_csv(args.output_dir / "drd_change_events.csv", index=False)
    event_frequency.to_csv(
        args.output_dir / "drd_change_event_frequency.csv", index=False
    )
    rank_candidates.to_csv(
        args.output_dir / "drd_rank_downgrade_candidates.csv", index=False
    )
    focus_only.to_csv(
        args.output_dir / "drd_focus_only_changes.csv", index=False
    )
    explicit_adverse.to_csv(
        args.output_dir / "drd_explicit_adverse_events.csv", index=False
    )
    comparison.to_csv(
        args.output_dir / "drd_extended_condition_comparison.csv", index=False
    )

    summary = {
        "input": str(args.input),
        "study_period": [args.start_year, args.end_year],
        "directed_rows": int(len(directed)),
        "country_anchor_years": int(len(comparison)),
        "duplicate_directed_keys": duplicate_keys,
        "change_event_counts": directed["change_event"].value_counts().to_dict(),
        "candidate_strain_rows": int(directed["candidate_strain_event"].sum()),
        "reciprocal_candidate_strain_country_years": int(
            comparison["reciprocal_candidate_strain"].sum()
        ),
        "explicit_adverse_rows": int(directed["explicit_adverse"].sum()),
        "conservative_condition_counts": comparison[
            "drd_condition_conservative"
        ].value_counts().to_dict(),
        "extended_candidate_condition_counts": comparison[
            "drd_condition_extended_candidate"
        ].value_counts().to_dict(),
        "country_anchor_years_changed_by_extended_rule": int(
            (
                comparison["drd_condition_conservative"]
                != comparison["drd_condition_extended_candidate"]
            ).sum()
        ),
    }
    (args.output_dir / "drd_change_summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    print("=" * 72)
    print("DRD CHANGE DECOMPOSITION")
    print("=" * 72)
    print(json.dumps(summary, indent=2, ensure_ascii=False))

    print("\nCandidate non-zero rank downgrades:")
    display_columns = [
        "country", "anchor", "year", "direction", "change_event",
        "previous_embassy", "Embassy", "previous_focus", "Focus",
        "previous_lor", "LOR",
    ]
    print(
        rank_candidates.sort_values(["year", "country"], ascending=[False, True])
        .head(30)[display_columns]
        .to_string(index=False)
    )

    print("\nExplicit adverse records:")
    print(
        explicit_adverse.sort_values(["year", "country"], ascending=[False, True])
        [display_columns]
        .to_string(index=False)
    )

    print("\nOutputs written to:", args.output_dir.resolve())


if __name__ == "__main__":
    main()
