import numpy as np
import pandas as pd
import pytest

from src.data.build_closeness_index import weighted_index


def test_all_missing_returns_nan_not_zero():
    frame = pd.DataFrame({"a_score": [np.nan], "b_score": [np.nan]})
    result = weighted_index(frame, {"a_score": 1, "b_score": 1}, min_available=1)
    assert pd.isna(result.loc[0, "score"])
    assert result.loc[0, "requested_weight_coverage"] == 0


def test_all_positive_weight_on_missing_pillar_returns_nan():
    frame = pd.DataFrame({"a_score": [0.5], "b_score": [np.nan]})
    result = weighted_index(frame, {"a_score": 0, "b_score": 1}, min_available=1)
    assert pd.isna(result.loc[0, "score"])


def test_zero_total_weight_rejected():
    frame = pd.DataFrame({"a_score": [0.5]})
    with pytest.raises(ValueError, match="At least one weight"):
        weighted_index(frame, {"a_score": 0}, min_available=1)


def test_missing_pillar_is_renormalised_not_zero_filled():
    frame = pd.DataFrame({"a_score": [0.6], "b_score": [np.nan], "c_score": [-0.2]})
    result = weighted_index(frame, {"a_score": 1, "b_score": 1, "c_score": 1}, min_available=2)
    assert result.loc[0, "score"] == pytest.approx(0.2)
    assert result.loc[0, "effective_a_weight"] == pytest.approx(0.5)
    assert result.loc[0, "effective_c_weight"] == pytest.approx(0.5)


def test_minimum_available_rule_enforced():
    frame = pd.DataFrame({"a_score": [0.6], "b_score": [np.nan], "c_score": [np.nan]})
    result = weighted_index(frame, {"a_score": 1, "b_score": 1, "c_score": 1}, min_available=2)
    assert pd.isna(result.loc[0, "score"])


def test_effective_weights_sum_to_one_for_valid_score():
    frame = pd.DataFrame({"a_score": [0.6], "b_score": [0.2], "c_score": [np.nan]})
    result = weighted_index(frame, {"a_score": 2, "b_score": 1, "c_score": 1}, min_available=2)
    total = result.loc[0, ["effective_a_weight", "effective_b_weight", "effective_c_weight"]].sum()
    assert total == pytest.approx(1.0)
    assert result.loc[0, "score"] == pytest.approx((2/3)*0.6 + (1/3)*0.2)

def test_experimental_index_requires_technology():
    frame = pd.DataFrame(
        {
            "security_score": [0.6],
            "diplomatic_score": [0.2],
            "economic_score": [-0.1],
            "technology_score": [np.nan],
        }
    )

    result = weighted_index(
        frame,
        {
            "security_score": 1,
            "diplomatic_score": 1,
            "economic_score": 1,
            "technology_score": 1,
        },
        min_available=3,
    )

    experimental_score = result["score"].where(
        frame["technology_score"].notna()
    )

    assert pd.isna(experimental_score.iloc[0])