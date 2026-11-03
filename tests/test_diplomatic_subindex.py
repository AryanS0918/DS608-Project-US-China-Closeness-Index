import importlib.util
from pathlib import Path
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "builder", ROOT / "src/data/build_diplomatic_subindex.py"
)
b = importlib.util.module_from_spec(spec)
spec.loader.exec_module(b)

@pytest.fixture(scope="module")
def inputs():
    return (
        pd.read_csv(ROOT / "data/processed/diplomatic_structural_ties_country_anchor_year.csv", low_memory=False),
        pd.read_csv(ROOT / "data/processed/unga_country_year_scores.csv", low_memory=False),
        pd.read_csv(ROOT / "outputs/tables/relations_condition/relationship_condition_country_master.csv", low_memory=False),
    )

@pytest.fixture(scope="module")
def output(inputs):
    return b.build_diplomatic_subindex(*inputs)

def test_dimensions_and_period(output):
    assert output.shape == (4205, 13)
    assert output.country_iso3.nunique() == 192
    assert (output.year.min(), output.year.max()) == (2004, 2025)

def test_unique_keys(output):
    assert not output.duplicated(["country_iso3", "year"]).any()

def test_expected_integration_counts(output):
    assert output.diplomatic_integration_status.value_counts().to_dict() == b.EXPECTED_INTEGRATION_COUNTS

def test_expected_comparability_counts(output):
    assert output.diplomatic_comparability_status.value_counts().to_dict() == {
        "comparable_complete_component_period": 3998,
        "provisional_latest_year_extension": 188,
        "available_component_renormalised": 16,
        "score_unavailable": 3,
    }

def test_complete_period_and_provisional_extension(output):
    assert output.loc[output.year.le(2024), "diplomatic_comparability_status"].ne(
        "provisional_latest_year_extension"
    ).all()
    assert output.loc[output.diplomatic_comparability_status.eq("provisional_latest_year_extension"), "year"].eq(2025).all()

def test_equal_weight_formula_on_common_support(output):
    x = output[output.diplomatic_integration_status.eq("both_components_available")]
    expected = 0.5 * x.diplomatic_structural_signed_score + 0.5 * x.unga_score_broad
    assert (x.diplomatic_score - expected).abs().max() < 1e-12

def test_available_component_renormalisation(output):
    x = output[output.diplomatic_integration_status.str.startswith("structural_only")]
    assert (x.diplomatic_score == x.diplomatic_structural_signed_score).all()
    y = output[output.diplomatic_integration_status.eq("unga_only_structural_source_year_unavailable")]
    assert (y.diplomatic_score == y.unga_score_broad).all()

def test_2025_is_provisional_and_structural_missing(output):
    x = output[output.year.eq(2025)]
    assert len(x) == 191
    assert x.diplomatic_structural_signed_score.isna().all()
    assert x.diplomatic_comparability_status.isin(
        ["provisional_latest_year_extension", "score_unavailable"]
    ).all()

def test_three_missing_scores_are_expected(output):
    x = output[output.diplomatic_score.isna()]
    assert set(x[["country_iso3", "year"]].itertuples(index=False, name=None)) == {
        ("AFG", 2025), ("TUR", 2025), ("VEN", 2025)
    }

def test_scg_rows_use_structural_only(output):
    x = output[output.country_iso3.eq("SCG")]
    assert set(x.year) == {2004, 2005, 2006}
    assert x.diplomatic_integration_status.eq("structural_only_unga_row_unavailable").all()
    assert (x.diplomatic_score == x.diplomatic_structural_signed_score).all()

def test_score_bounds(output):
    assert output.diplomatic_score.dropna().between(-1, 1).all()

def test_unga_aliases_resolve(inputs):
    _, unga, master = inputs
    prepared = b.prepare_unga(unga, master)
    assert prepared.iso3.notna().all()
    assert {"FSM", "GMB", "VCT", "CIV", "STP", "TUR"}.issubset(set(prepared.iso3))
