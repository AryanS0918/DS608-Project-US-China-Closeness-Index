import importlib.util
from pathlib import Path
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("builder", ROOT / "src/data/build_economic_subindex.py")
b = importlib.util.module_from_spec(spec)
spec.loader.exec_module(b)

@pytest.fixture(scope="module")
def inputs():
    return (
        pd.read_csv(ROOT / "data/processed/trade_orientation_country_year.csv", low_memory=False),
        pd.read_csv(ROOT / "data/processed/fdi_structural_ties_country_anchor_year.csv", low_memory=False),
        pd.read_csv(ROOT / "data/processed/economic_institutional_ties_country_anchor_year.csv", low_memory=False),
    )

@pytest.fixture(scope="module")
def panel(inputs): return b.build_economic_subindex(*inputs)

def test_dimensions(panel):
    assert len(panel) == 4205
    assert panel.country_iso3.nunique() == 192
    assert (panel.year.min(), panel.year.max()) == (2004, 2025)

def test_unique_keys(panel):
    assert not panel.duplicated(["country_iso3", "year"]).any()

def test_component_counts(panel):
    assert panel.available_component_count.value_counts().sort_index().to_dict() == {1: 535, 2: 2041, 3: 1629}

def test_minimum_two_component_rule(panel):
    assert panel.loc[panel.available_component_count.eq(1), "economic_score"].isna().all()
    assert panel.loc[panel.available_component_count.ge(2), "economic_score"].notna().all()

def test_equal_weight_formula(panel):
    expected = panel[b.COMPONENTS].mean(axis=1, skipna=True)
    scored = panel.economic_score.notna()
    assert (panel.loc[scored, "economic_score"] - expected[scored]).abs().max() < 1e-12

def test_score_bounds(panel):
    assert panel.economic_score.dropna().between(-1, 1).all()

def test_availability_counts(panel):
    assert panel.economic_score.notna().sum() == 3670
    assert panel.economic_score.isna().sum() == 535

def test_fdi_regime_counts(panel):
    regimes = panel.drop_duplicates("country_iso3")
    assert regimes.loc[regimes.country_iso3.ne("SCG"), "fdi_reporting_regime"].value_counts().to_dict() == {
        "anchor_official_fixed_regime": 112,
        "host_official_fixed_regime": 79,
    }

def test_period_status_counts(panel):
    assert panel.economic_comparability_status.value_counts().to_dict() == {
        "fixed_regime_common_period_three_components": 971,
        "fixed_regime_historical_extension_two_components": 813,
        "pre_fdi_source_period_two_component_extension": 781,
        "fixed_regime_historical_extension_three_components": 658,
        "fixed_regime_common_period_two_components": 325,
        "fixed_regime_historical_extension_score_unavailable": 248,
        "pre_fdi_source_period_score_unavailable": 177,
        "provisional_latest_year_two_component_extension": 122,
        "provisional_latest_year_score_unavailable": 69,
        "fixed_regime_common_period_score_unavailable": 41,
    }

def test_2025_is_provisional_without_fdi(panel):
    x = panel[panel.year.eq(2025)]
    assert x.fdi_orientation_score.isna().all()
    assert x.economic_comparability_status.isin([
        "provisional_latest_year_two_component_extension",
        "provisional_latest_year_score_unavailable",
    ]).all()

def test_scg_window(panel):
    assert set(panel.loc[panel.country_iso3.eq("SCG"), "year"]) == {2004, 2005, 2006}

def test_validation(panel):
    assert all(value == 0 for value in b.validate_output(panel).values())
