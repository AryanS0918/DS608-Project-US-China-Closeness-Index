"""Dashboard tests: scenario rules on top of the production functions, and the canonical input."""

import numpy as np
import pandas as pd
import pytest

from dashboard.core.data import EXPECTED, load_panel
from dashboard.core.weighting import (
    ALL_PILLARS,
    CORE_PILLARS,
    DEFAULT_WEIGHTS,
    classify,
    is_experimental,
    neutral_type,
    required_minimum,
    scenario_scores,
)


def frame(rows):
    return pd.DataFrame(rows, columns=ALL_PILLARS, dtype=float)


def w(s, d, e, t):
    return dict(zip(ALL_PILLARS, [s, d, e, t]))


def test_default_weights_are_core_one_third_and_technology_zero():
    assert not is_experimental(DEFAULT_WEIGHTS)
    assert DEFAULT_WEIGHTS["technology_score"] == 0
    assert len({DEFAULT_WEIGHTS[c] for c in CORE_PILLARS}) == 1


def test_technology_weight_makes_scenario_experimental_with_minimum_three():
    assert required_minimum(w(1, 1, 1, 1)) == 3
    assert required_minimum(w(1, 1, 1, 0)) == 2
    df = frame([[0.5, -0.2, np.nan, 0.4]])  # two core + technology = 3 observed
    assert pd.notna(scenario_scores(df, w(1, 1, 1, 1)).loc[0, "score"])
    df = frame([[0.5, np.nan, np.nan, 0.4]])  # only 2 observed with technology weighted
    assert np.isnan(scenario_scores(df, w(1, 1, 1, 1)).loc[0, "score"])


def test_missing_weighted_pillar_never_becomes_zero():
    df = frame([[0.5, -0.2, 0.1, np.nan]])
    out = scenario_scores(df, w(0, 0, 0, 100))
    assert np.isnan(out.loc[0, "score"])


def test_two_core_pillars_renormalised():
    df = frame([[0.6, -0.2, np.nan, np.nan]])
    assert scenario_scores(df, DEFAULT_WEIGHTS).loc[0, "score"] == pytest.approx(0.2)


@pytest.fixture(scope="module")
def panel():
    return load_panel()


def test_canonical_counts(panel):
    p, meta = panel
    assert meta["matches_expected"], meta
    assert len(p) == EXPECTED["rows"]


def test_no_excluded_entities(panel):
    p, _ = panel
    excluded = {"TWN", "HKG", "PSE", "XKX", "VAT", "COK", "NIU", "MSR", "GIB", "ESH", "USA", "CHN"}
    assert not excluded & set(p["country_iso3"])
    assert set(p.loc[p["country_iso3"].eq("SCG"), "year"]) <= {2004, 2005, 2006}


def test_default_scenario_reproduces_official(panel):
    p, _ = panel
    s = scenario_scores(p, DEFAULT_WEIGHTS)["score"]
    assert np.allclose(s, p["core_index_available"], equal_nan=True)


def test_classes_and_hedging_match_production(panel):
    p, _ = panel
    assert (classify(p["core_index_available"]) == p["orientation_class"]).all()
    assert (neutral_type(p["core_index_available"], p, CORE_PILLARS) == p["neutral_type"]).all()
