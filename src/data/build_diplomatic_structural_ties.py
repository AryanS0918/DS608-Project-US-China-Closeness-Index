"""Build annual diplomatic structural-ties scores for China and the United States.

Run from the repository root:
    python -u src/data/build_diplomatic_structural_ties.py

The baseline score combines mean directional Level of Representation (LOR)
with reciprocity depth:

    0.75 * mean_directional_depth + 0.25 * minimum_directional_depth

Missing directed records receive zero operational depth but remain explicitly
identified as unobserved. Observed LOR zero records remain identifiable as
adverse diplomatic observations. Relationship condition remains a separate
contextual layer and is not folded into this score.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

KEYS = ["country_iso3", "anchor", "year"]
DIRECTIONS = ["anchor_to_country", "country_to_anchor"]
METHOD_VERSION = "diplomatic_structural_ties_v1_mean75_reciprocity25"


def require_columns(frame: pd.DataFrame, columns: set[str], label: str) -> None:
    missing = columns.difference(frame.columns)
    if missing:
        raise KeyError(f"{label} is missing fields: {sorted(missing)}")


def load_universe(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path, low_memory=False)
    require_columns(
        frame,
        {
            "country_iso3",
            "country_name",
            "historical_entity",
            "anchor",
            "year",
        },
        "Relationship-condition production panel",
    )
    universe = frame[
        [
            "country_iso3",
            "country_name",
            "historical_entity",
            "anchor",
            "year",
        ]
    ].drop_duplicates()
    if universe.duplicated(KEYS).any():
        raise ValueError("Diplomatic score universe contains duplicate keys")
    return universe.sort_values(KEYS).reset_index(drop=True)


def load_country_mapping(path: Path) -> dict[str, str]:
    frame = pd.read_csv(path, low_memory=False)
    require_columns(
        frame,
        {"drd_country_name", "country"},
        "Relationship country crosswalk",
    )
    mapping = (
        frame[["drd_country_name", "country"]]
        .dropna()
        .drop_duplicates()
    )
    ambiguity = mapping.groupby("drd_country_name")["country"].nunique()
    ambiguous = ambiguity[ambiguity.gt(1)]
    if not ambiguous.empty:
        raise ValueError(
            "DRD source names map to multiple identifiers: "
            f"{ambiguous.to_dict()}"
        )
    return mapping.set_index("drd_country_name")["country"].to_dict()


def prepare_directed(path: Path, country_map: dict[str, str]) -> pd.DataFrame:
    if path.suffix.lower() == ".parquet":
        frame = pd.read_parquet(path)
    elif path.suffix.lower() == ".csv":
        frame = pd.read_csv(path, low_memory=False)
    else:
        raise ValueError(
            f"Unsupported directed-panel format: {path.suffix}"
        )
    require_columns(
        frame,
        {
            "country",
            "anchor",
            "year",
            "direction",
            "Embassy",
            "Focus",
            "EmbassyFocus",
            "LOR",
        },
        "Directed DRD panel",
    )
    frame = frame.copy()
    frame["drd_country_name"] = frame["country"].astype("string").str.strip()
    frame["country_iso3"] = frame["drd_country_name"].map(country_map)

    unresolved = frame[frame["country_iso3"].isna()][
        ["drd_country_name", "anchor", "year", "direction"]
    ].drop_duplicates()
    if not unresolved.empty:
        raise ValueError(
            "Unresolved DRD country names remain: "
            f"{unresolved.head(20).to_dict('records')}"
        )

    if not frame["direction"].isin(DIRECTIONS).all():
        invalid = sorted(set(frame["direction"]) - set(DIRECTIONS))
        raise ValueError(f"Unexpected direction labels: {invalid}")

    frame["LOR"] = pd.to_numeric(frame["LOR"], errors="raise")
    if not frame["LOR"].between(0, 1).all():
        raise ValueError("Directed LOR values fall outside [0, 1]")

    directed_keys = KEYS + ["direction"]
    if frame.duplicated(directed_keys).any():
        raise ValueError("Directed DRD panel contains duplicate analytical keys")
    return frame


def reshape_directions(directed: pd.DataFrame) -> pd.DataFrame:
    columns = ["LOR", "Embassy", "Focus", "EmbassyFocus"]
    wide = directed.pivot(
        index=KEYS,
        columns="direction",
        values=columns,
    )
    wide.columns = [
        f"{measure.lower()}__{direction}"
        for measure, direction in wide.columns
    ]
    return wide.reset_index()


def add_continuity_diagnostics(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.sort_values(KEYS).copy()
    group_keys = ["country_iso3", "anchor"]

    for direction in DIRECTIONS:
        observed = f"{direction}_observed"
        five_year = f"{direction}_five_year_presence_rate"
        streak = f"{direction}_presence_streak"

        result[five_year] = (
            result.groupby(group_keys, sort=False)[observed]
            .transform(
                lambda values: values.astype(float).rolling(
                    window=5,
                    min_periods=1,
                ).mean()
            )
        )

        def running_streak(values: pd.Series) -> pd.Series:
            output = []
            current = 0
            for value in values.astype(bool):
                current = current + 1 if value else 0
                output.append(current)
            return pd.Series(output, index=values.index, dtype="int64")

        result[streak] = (
            result.groupby(group_keys, sort=False)[observed]
            .transform(running_streak)
        )

    result["bilateral_observed"] = (
        result["anchor_to_country_observed"]
        & result["country_to_anchor_observed"]
    )
    result["bilateral_five_year_presence_rate"] = (
        result.groupby(group_keys, sort=False)["bilateral_observed"]
        .transform(
            lambda values: values.astype(float).rolling(
                window=5,
                min_periods=1,
            ).mean()
        )
    )

    def bilateral_streak(values: pd.Series) -> pd.Series:
        output = []
        current = 0
        for value in values.astype(bool):
            current = current + 1 if value else 0
            output.append(current)
        return pd.Series(output, index=values.index, dtype="int64")

    result["bilateral_presence_streak"] = (
        result.groupby(group_keys, sort=False)["bilateral_observed"]
        .transform(bilateral_streak)
    )
    return result


def calculate_scores(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    a = result["anchor_to_country_lor"]
    b = result["country_to_anchor_lor"]

    result["mean_depth"] = (a + b) / 2
    result["reciprocity_depth"] = np.minimum(a, b)
    result["depth_gap"] = (a - b).abs()

    result["diplomatic_score_mean_only"] = result["mean_depth"]
    result["diplomatic_score_mean_reciprocity_75_25"] = (
        0.75 * result["mean_depth"]
        + 0.25 * result["reciprocity_depth"]
    )
    result["diplomatic_score_mean_reciprocity_50_50"] = (
        0.50 * result["mean_depth"]
        + 0.50 * result["reciprocity_depth"]
    )
    result["diplomatic_score_geometric"] = np.sqrt(a * b)

    result["diplomatic_structural_score_raw"] = result[
        "diplomatic_score_mean_reciprocity_75_25"
    ]
    result["diplomatic_structural_score_scaled"] = (
        100 * result["diplomatic_structural_score_raw"]
    )
    return result


def build_panel(
    directed_path: Path,
    universe_path: Path,
    crosswalk_path: Path,
) -> pd.DataFrame:
    universe = load_universe(universe_path)
    country_map = load_country_mapping(crosswalk_path)
    directed = prepare_directed(directed_path, country_map)
    wide = reshape_directions(directed)

    panel = universe.merge(
        wide,
        on=KEYS,
        how="left",
        validate="one_to_one",
        indicator="diplomatic_evidence_merge_status",
    )

    for direction in DIRECTIONS:
        lor_source = f"lor__{direction}"
        embassy_source = f"embassy__{direction}"
        focus_source = f"focus__{direction}"
        combined_source = f"embassyfocus__{direction}"

        panel[f"{direction}_observed"] = panel[lor_source].notna()
        panel[f"{direction}_lor"] = panel[lor_source].fillna(0.0)
        panel[f"{direction}_embassy_code"] = panel[embassy_source]
        panel[f"{direction}_focus_code"] = panel[focus_source]
        panel[f"{direction}_embassy_focus_code"] = panel[combined_source]
        panel[f"{direction}_adverse"] = (
            panel[f"{direction}_observed"]
            & panel[f"{direction}_lor"].eq(0)
        )

    panel["direction_count"] = (
        panel["anchor_to_country_observed"].astype(int)
        + panel["country_to_anchor_observed"].astype(int)
    )
    panel["bilateral_adverse"] = (
        panel["anchor_to_country_adverse"]
        & panel["country_to_anchor_adverse"]
    )
    panel["source_coverage_status"] = np.select(
        [
            panel["direction_count"].eq(2),
            panel["direction_count"].eq(1),
        ],
        ["bilateral_observed", "unilateral_observed"],
        default="no_directed_record",
    )

    panel = add_continuity_diagnostics(panel)
    panel = calculate_scores(panel)
    panel["method_version"] = METHOD_VERSION

    drop_columns = [
        column
        for column in panel.columns
        if "__" in column
    ]
    panel = panel.drop(columns=drop_columns)
    return panel.sort_values(KEYS).reset_index(drop=True)


def validate_panel(panel: pd.DataFrame) -> dict[str, Any]:
    score_columns = [
        "diplomatic_score_mean_only",
        "diplomatic_score_mean_reciprocity_75_25",
        "diplomatic_score_mean_reciprocity_50_50",
        "diplomatic_score_geometric",
        "diplomatic_structural_score_raw",
    ]
    failures: dict[str, int] = {}
    failures["duplicate_keys"] = int(panel.duplicated(KEYS).sum())
    failures["blank_country_names"] = int(panel["country_name"].isna().sum())
    failures["invalid_direction_counts"] = int(
        (~panel["direction_count"].isin([0, 1, 2])).sum()
    )
    failures["bilateral_flag_mismatches"] = int(
        (
            panel["bilateral_observed"]
            != panel["direction_count"].eq(2)
        ).sum()
    )
    for column in score_columns:
        failures[f"{column}_out_of_bounds"] = int(
            (~panel[column].between(0, 1)).sum()
        )
    failures["scaled_score_out_of_bounds"] = int(
        (~panel["diplomatic_structural_score_scaled"].between(0, 100)).sum()
    )
    nonzero_failures = {
        key: value
        for key, value in failures.items()
        if value != 0
    }
    if nonzero_failures:
        raise AssertionError(f"Diplomatic panel validation failed: {nonzero_failures}")

    return {
        "rows": int(len(panel)),
        "countries_or_historical_entities": int(panel["country_iso3"].nunique()),
        "years": [int(panel["year"].min()), int(panel["year"].max())],
        "coverage_status_counts": panel["source_coverage_status"].value_counts().to_dict(),
        "direction_count_distribution": panel["direction_count"].value_counts().sort_index().to_dict(),
        "baseline_score_summary": {
            key: float(value)
            for key, value in panel["diplomatic_structural_score_raw"].describe().to_dict().items()
        },
        "validation_failures": failures,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--directed-panel",
        type=Path,
        default=Path(
            "data/interim/relations/"
            "drd_anchor_directed_country_year.parquet"
        ),
    )
    parser.add_argument(
        "--universe",
        type=Path,
        default=Path(
            "data/processed/"
            "relationship_condition_country_anchor_year.csv"
        ),
    )
    parser.add_argument(
        "--crosswalk",
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
            "data/processed/"
            "diplomatic_structural_ties_country_anchor_year.csv"
        ),
    )
    parser.add_argument(
        "--report-directory",
        type=Path,
        default=Path(
            "outputs/tables/diplomatic_structural_ties"
        ),
    )
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.report_directory.mkdir(parents=True, exist_ok=True)

    panel = build_panel(
        args.directed_panel,
        args.universe,
        args.crosswalk,
    )
    summary = validate_panel(panel)

    sensitivity = (
        panel.groupby(["year", "anchor"])
        .agg(
            observations=("country_iso3", "size"),
            baseline_mean=("diplomatic_structural_score_raw", "mean"),
            mean_only_mean=("diplomatic_score_mean_only", "mean"),
            equal_weight_mean=(
                "diplomatic_score_mean_reciprocity_50_50",
                "mean",
            ),
            geometric_mean=("diplomatic_score_geometric", "mean"),
            bilateral_observed=("bilateral_observed", "sum"),
            unilateral_observed=(
                "direction_count",
                lambda values: int(values.eq(1).sum()),
            ),
            no_directed_record=(
                "direction_count",
                lambda values: int(values.eq(0).sum()),
            ),
        )
        .reset_index()
    )

    method_comparison = panel[
        [
            "country_iso3",
            "country_name",
            "anchor",
            "year",
            "direction_count",
            "anchor_to_country_lor",
            "country_to_anchor_lor",
            "mean_depth",
            "reciprocity_depth",
            "depth_gap",
            "diplomatic_score_mean_only",
            "diplomatic_score_mean_reciprocity_75_25",
            "diplomatic_score_mean_reciprocity_50_50",
            "diplomatic_score_geometric",
        ]
    ].copy()
    method_comparison["baseline_minus_mean_only"] = (
        method_comparison["diplomatic_score_mean_reciprocity_75_25"]
        - method_comparison["diplomatic_score_mean_only"]
    )
    method_comparison["baseline_minus_equal_weight"] = (
        method_comparison["diplomatic_score_mean_reciprocity_75_25"]
        - method_comparison["diplomatic_score_mean_reciprocity_50_50"]
    )

    panel.to_csv(args.output, index=False)
    sensitivity.to_csv(
        args.report_directory / "diplomatic_score_sensitivity_by_year.csv",
        index=False,
    )
    method_comparison.to_csv(
        args.report_directory / "diplomatic_score_method_comparison.csv",
        index=False,
    )
    (args.report_directory / "diplomatic_structural_ties_summary.json").write_text(
        json.dumps(summary, indent=2),
        encoding="utf-8",
    )

    print("=" * 72)
    print("DIPLOMATIC STRUCTURAL-TIES PANEL")
    print("=" * 72)
    print(json.dumps(summary, indent=2))
    print("\nProduction output:", args.output)
    print("Reports directory:", args.report_directory)


if __name__ == "__main__":
    main()
