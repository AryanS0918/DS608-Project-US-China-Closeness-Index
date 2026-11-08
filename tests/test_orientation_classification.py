import numpy as np
import pandas as pd

from src.data.build_orientation_classification import (
    apply_classification,
    classify_score,
    evaluate_neutral_bands,
    generate_all_outputs,
)


def test_fixed_boundaries():
    assert classify_score(np.nan) == "no_score"
    assert classify_score(0.0) == "neutral_or_hedging"
    assert classify_score(-0.049999) == "neutral_or_hedging"
    assert classify_score(0.049999) == "neutral_or_hedging"
    assert classify_score(-0.05) == "moderately_china_oriented"
    assert classify_score(0.05) == "moderately_us_oriented"
    assert classify_score(-0.25508739255555046) == "strongly_china_oriented"
    assert classify_score(0.27088622739504103) == "strongly_us_oriented"


def test_neutral_and_hedging_are_distinguished():
    frame = pd.DataFrame(
        {
            "core_index_available": [0.01, 0.01],
            "security_score": [0.01, 0.4],
            "diplomatic_score": [0.02, -0.3],
            "economic_score": [0.00, -0.07],
        }
    )
    result = apply_classification(frame)
    assert result.loc[0, "neutral_type"] == "neutral"
    assert result.loc[1, "neutral_type"] == "hedging"


def test_non_neutral_rows_have_empty_neutral_type():
    frame = pd.DataFrame(
        {
            "core_index_available": [-0.4, 0.4],
            "security_score": [-0.4, 0.4],
            "diplomatic_score": [0.2, -0.2],
            "economic_score": [-0.5, 0.5],
        }
    )
    result = apply_classification(frame)
    assert result["neutral_type"].eq("").all()


def synthetic_panel():
    rows = []
    values = [-0.8, -0.5, -0.3, -0.2, -0.15, -0.02, 0.02, 0.12, 0.2, 0.3, 0.5, 0.8]
    for year in range(2004, 2008):
        for i, value in enumerate(values):
            rows.append(
                {
                    "country_iso3": f"X{i:02d}",
                    "preferred_country_name": f"Country {i}",
                    "year": year,
                    "core_index_available": value + 0.001 * (year - 2004),
                    "security_score": value,
                    "diplomatic_score": value,
                    "economic_score": value,
                }
            )
    return pd.DataFrame(rows)


def test_diagnostic_generation_returns_all_candidates():
    metrics, classifications = evaluate_neutral_bands(synthetic_panel())
    assert len(metrics) == 6
    assert set(metrics["neutral_half_width"]) == {
        0.025, 0.05, 0.075, 0.10, 0.125, 0.15
    }
    assert len(classifications) == 6 * len(synthetic_panel())


def test_generate_all_outputs_writes_auditable_tables(tmp_path):
    summary = generate_all_outputs(synthetic_panel(), tmp_path)
    expected = {
        "neutral_band_candidate_metrics.csv",
        "neutral_band_candidate_classifications.csv",
        "jenks_leave_one_year_out_stability.csv",
        "jenks_stability_summary.csv",
        "country_average_reference_breaks.csv",
        "us_china_relative_orientation_index_classified.csv",
        "orientation_class_counts_by_year.csv",
        "orientation_classification_summary.json",
        "jenks_classification_summary.json",
    }
    assert expected == {path.name for path in tmp_path.iterdir()}
    assert summary["neutral_half_width"] == 0.05
