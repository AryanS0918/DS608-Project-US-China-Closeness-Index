"""Generate auditable Jenks diagnostics and apply the fixed production classes.

Run from the repository root with:
    python -m src.data.build_orientation_classification

The command reads the canonical continuous index and regenerates every table used
by the classification notebook. No analysis output needs to be copied manually.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

SCORE_FIELD = "core_index_available"
PILLARS = ["security_score", "diplomatic_score", "economic_score"]
CANDIDATE_NEUTRAL_HALF_WIDTHS = [0.025, 0.05, 0.075, 0.10, 0.125, 0.15]
NEUTRAL_HALF_WIDTH = 0.05
CHINA_STRONG_BREAK = -0.25508739255555046
US_STRONG_BREAK = 0.27088622739504103


def jenks_two_break(values: np.ndarray) -> float:
    """Return the exact optimal boundary for a one-dimensional two-class split."""
    x = np.sort(np.asarray(values, dtype=float))
    x = x[np.isfinite(x)]
    if len(x) < 4:
        raise ValueError("At least four observations are required for Jenks")

    cumulative = np.cumsum(x)
    cumulative_sq = np.cumsum(x * x)
    n = np.arange(1, len(x) + 1)

    left_sse = cumulative_sq[:-1] - cumulative[:-1] ** 2 / n[:-1]
    right_n = len(x) - n[:-1]
    right_sum = cumulative[-1] - cumulative[:-1]
    right_sse = (
        cumulative_sq[-1] - cumulative_sq[:-1]
        - right_sum**2 / right_n
    )

    valid_split = x[:-1] < x[1:]
    objective = np.where(valid_split, left_sse + right_sse, np.inf)
    split = int(np.argmin(objective))
    return float((x[split] + x[split + 1]) / 2)


def breaks_for_band(frame: pd.DataFrame, half_width: float) -> tuple[float, float]:
    scores = frame[SCORE_FIELD].dropna()
    china_magnitudes = (-scores[scores < -half_width]).to_numpy()
    us_scores = scores[scores > half_width].to_numpy()
    return jenks_two_break(china_magnitudes), jenks_two_break(us_scores)


def classify_with_breaks(
    score: float,
    half_width: float,
    china_break_magnitude: float,
    us_break: float,
) -> str:
    if pd.isna(score):
        return "no_score"
    if abs(score) < half_width:
        return "neutral_or_hedging"
    if score <= -china_break_magnitude:
        return "strongly_china_oriented"
    if score <= -half_width:
        return "moderately_china_oriented"
    if score >= us_break:
        return "strongly_us_oriented"
    return "moderately_us_oriented"


def classify_score(score: float) -> str:
    return classify_with_breaks(
        score,
        NEUTRAL_HALF_WIDTH,
        abs(CHINA_STRONG_BREAK),
        US_STRONG_BREAK,
    )


def neutral_type(row: pd.Series, half_width: float = NEUTRAL_HALF_WIDTH) -> str:
    score = row[SCORE_FIELD]
    if pd.isna(score) or abs(score) >= half_width:
        return ""
    values = row[PILLARS].dropna().to_numpy(float)
    points_us = np.any(values >= half_width)
    points_china = np.any(values <= -half_width)
    return "hedging" if points_us and points_china else "neutral"


def apply_classification(frame: pd.DataFrame) -> pd.DataFrame:
    required = {SCORE_FIELD, *PILLARS}
    missing = required - set(frame.columns)
    if missing:
        raise KeyError(f"Missing required columns: {sorted(missing)}")

    result = frame.copy()
    result["orientation_class"] = result[SCORE_FIELD].map(classify_score)
    result["neutral_type"] = result.apply(neutral_type, axis=1)
    result["classification_score_field"] = SCORE_FIELD
    result["neutral_half_width"] = NEUTRAL_HALF_WIDTH
    result["china_strong_break"] = CHINA_STRONG_BREAK
    result["us_strong_break"] = US_STRONG_BREAK
    return result


def evaluate_neutral_bands(
    frame: pd.DataFrame,
    candidates: list[float] = CANDIDATE_NEUTRAL_HALF_WIDTHS,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return candidate metrics and country-year classifications for every band."""
    metric_rows: list[dict] = []
    classification_rows: list[pd.DataFrame] = []

    for half_width in candidates:
        china_break, us_break = breaks_for_band(frame, half_width)
        labels = frame[SCORE_FIELD].map(
            lambda score: classify_with_breaks(
                score, half_width, china_break, us_break
            )
        )
        candidate = frame[["country_iso3", "year", SCORE_FIELD, *PILLARS]].copy()
        candidate["neutral_half_width"] = half_width
        candidate["class"] = labels
        candidate["neutral_type"] = candidate.apply(
            lambda row: neutral_type(row, half_width), axis=1
        )

        ordered = candidate.sort_values(["country_iso3", "year"])
        previous_class = ordered.groupby("country_iso3")["class"].shift()
        previous_year = ordered.groupby("country_iso3")["year"].shift()
        previous_score = ordered.groupby("country_iso3")[SCORE_FIELD].shift()
        consecutive = ordered["year"].eq(previous_year + 1)
        category_changes = ordered["class"].ne(previous_class) & consecutive
        full_reversals = consecutive & (
            ((previous_score < -half_width) & (ordered[SCORE_FIELD] > half_width))
            | ((previous_score > half_width) & (ordered[SCORE_FIELD] < -half_width))
        )

        counts = labels.value_counts()
        directional_counts = [
            counts.get("moderately_china_oriented", 0),
            counts.get("strongly_china_oriented", 0),
            counts.get("moderately_us_oriented", 0),
            counts.get("strongly_us_oriented", 0),
        ]
        n = len(candidate)
        pairs = int(consecutive.sum())
        metric_rows.append(
            {
                "neutral_half_width": half_width,
                "china_strong_break_magnitude": china_break,
                "us_strong_break": us_break,
                "neutral_or_hedging_n": int(counts.get("neutral_or_hedging", 0)),
                "neutral_or_hedging_pct": 100 * counts.get("neutral_or_hedging", 0) / n,
                "moderately_china_n": int(counts.get("moderately_china_oriented", 0)),
                "strongly_china_n": int(counts.get("strongly_china_oriented", 0)),
                "moderately_us_n": int(counts.get("moderately_us_oriented", 0)),
                "strongly_us_n": int(counts.get("strongly_us_oriented", 0)),
                "smallest_directional_class_pct": 100 * min(directional_counts) / n,
                "consecutive_year_pairs": pairs,
                "category_changes": int(category_changes.sum()),
                "category_change_pct": 100 * category_changes.sum() / pairs,
                "full_orientation_reversals": int(full_reversals.sum()),
                "full_reversal_pct": 100 * full_reversals.sum() / pairs,
                "neutral_n": int(candidate["neutral_type"].eq("neutral").sum()),
                "hedging_n": int(candidate["neutral_type"].eq("hedging").sum()),
            }
        )
        classification_rows.append(candidate)

    return pd.DataFrame(metric_rows), pd.concat(classification_rows, ignore_index=True)


def leave_one_year_out_stability(
    frame: pd.DataFrame,
    candidates: list[float] = CANDIDATE_NEUTRAL_HALF_WIDTHS,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    rows: list[dict] = []
    for half_width in candidates:
        full_china, full_us = breaks_for_band(frame, half_width)
        for year in sorted(frame["year"].unique()):
            china_break, us_break = breaks_for_band(
                frame.loc[frame["year"].ne(year)], half_width
            )
            rows.append(
                {
                    "neutral_half_width": half_width,
                    "year_left_out": year,
                    "china_break": china_break,
                    "us_break": us_break,
                    "china_break_abs_change": abs(china_break - full_china),
                    "us_break_abs_change": abs(us_break - full_us),
                }
            )
    detail = pd.DataFrame(rows)
    summary = (
        detail.groupby("neutral_half_width")
        .agg(
            max_china_break_change=("china_break_abs_change", "max"),
            mean_china_break_change=("china_break_abs_change", "mean"),
            max_us_break_change=("us_break_abs_change", "max"),
            mean_us_break_change=("us_break_abs_change", "mean"),
        )
        .reset_index()
    )
    return detail, summary


def country_average_reference_breaks(
    frame: pd.DataFrame,
    candidates: list[float] = CANDIDATE_NEUTRAL_HALF_WIDTHS,
) -> pd.DataFrame:
    averages = frame.groupby(["country_iso3", "preferred_country_name"], as_index=False)[
        SCORE_FIELD
    ].mean()
    rows = []
    for half_width in candidates:
        china_break, us_break = breaks_for_band(averages, half_width)
        rows.append(
            {
                "neutral_half_width": half_width,
                "country_average_china_break": china_break,
                "country_average_us_break": us_break,
            }
        )
    return pd.DataFrame(rows)


def generate_all_outputs(frame: pd.DataFrame, output_dir: Path) -> dict:
    """Regenerate every diagnostic and production classification artefact."""
    output_dir.mkdir(parents=True, exist_ok=True)

    metrics, candidates = evaluate_neutral_bands(frame)
    loo_detail, stability = leave_one_year_out_stability(frame)
    average_breaks = country_average_reference_breaks(frame)
    classified = apply_classification(frame)
    annual_counts = (
        classified.groupby(["year", "orientation_class"])
        .size()
        .unstack(fill_value=0)
        .reset_index()
    )

    metrics.to_csv(output_dir / "neutral_band_candidate_metrics.csv", index=False)
    candidates.to_csv(
        output_dir / "neutral_band_candidate_classifications.csv", index=False
    )
    loo_detail.to_csv(
        output_dir / "jenks_leave_one_year_out_stability.csv", index=False
    )
    stability.to_csv(output_dir / "jenks_stability_summary.csv", index=False)
    average_breaks.to_csv(
        output_dir / "country_average_reference_breaks.csv", index=False
    )
    classified.to_csv(
        output_dir / "us_china_relative_orientation_index_classified.csv",
        index=False,
    )
    annual_counts.to_csv(
        output_dir / "orientation_class_counts_by_year.csv", index=False
    )

    selected = metrics.loc[
        metrics["neutral_half_width"].eq(NEUTRAL_HALF_WIDTH)
    ].iloc[0]
    summary = {
        "score_field": SCORE_FIELD,
        "reference_sample": "pooled eligible country-years 2004-2024",
        "candidate_neutral_half_widths": CANDIDATE_NEUTRAL_HALF_WIDTHS,
        "neutral_rule": "absolute score below 0.05",
        "neutral_half_width": NEUTRAL_HALF_WIDTH,
        "china_strong_break": CHINA_STRONG_BREAK,
        "us_strong_break": US_STRONG_BREAK,
        "neutral_and_hedging_share_pct": float(
            selected["neutral_or_hedging_pct"]
        ),
        "category_change_pct_consecutive_years": float(
            selected["category_change_pct"]
        ),
        "full_orientation_reversal_pct_consecutive_years": float(
            selected["full_reversal_pct"]
        ),
        "class_counts": classified["orientation_class"].value_counts().to_dict(),
        "neutral_type_counts": classified.loc[
            classified["orientation_class"].eq("neutral_or_hedging"),
            "neutral_type",
        ].value_counts().to_dict(),
    }
    for name in ["orientation_classification_summary.json", "jenks_classification_summary.json"]:
        (output_dir / name).write_text(json.dumps(summary, indent=2) + "\n")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--input",
        type=Path,
        default=Path(
            "outputs/tables/closeness_index/"
            "us_china_relative_orientation_index_country_year.csv"
        ),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("outputs/tables/closeness_index"),
    )
    args = parser.parse_args()

    frame = pd.read_csv(args.input)
    summary = generate_all_outputs(frame, args.output_dir)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
