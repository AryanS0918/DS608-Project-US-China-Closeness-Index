import importlib.util
from pathlib import Path
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("builder", ROOT / "src/data/build_economic_institutional_ties.py")
b = importlib.util.module_from_spec(spec)
spec.loader.exec_module(b)

@pytest.fixture(scope="module")
def inputs():
    return (
        pd.read_csv(ROOT / "data/processed/trade_agreement_ties_country_anchor_year.csv", low_memory=False),
        pd.read_csv(ROOT / "data/processed/bilateral_investment_treaties_country_anchor_year.csv", low_memory=False),
        pd.read_csv(ROOT / "outputs/tables/relations_condition/relationship_condition_country_master.csv", low_memory=False),
    )

@pytest.fixture(scope="module")
def panel(inputs): return b.build_panel(*inputs)

def test_dimensions(panel):
    assert len(panel) == 8410
    assert panel.country_iso3.nunique() == 192
    assert (panel.year.min(), panel.year.max()) == (2004, 2025)

def test_unique_keys(panel):
    assert not panel.duplicated(["country_iso3", "anchor", "year"]).any()

def test_scg_window_and_exclusions(panel):
    assert set(panel.loc[panel.country_iso3.eq("SCG"), "year"]) == {2004, 2005, 2006}
    assert {"CHN", "USA", "HKG", "PSE", "TWN", "VAT"}.isdisjoint(set(panel.country_iso3))

def test_preferred_names(panel):
    expected = {"LKA":"Sri Lanka", "MKD":"North Macedonia", "MYS":"Malaysia", "SWZ":"Eswatini", "TLS":"Timor-Leste", "TUR":"Turkiye"}
    actual = panel.drop_duplicates("country_iso3").set_index("country_iso3").preferred_country_name.to_dict()
    for iso3, name in expected.items(): assert actual[iso3] == name

def test_formula_and_bounds(panel):
    expected = 0.75 * panel.trade_agreement_score_raw + 0.25 * panel.bit_structural_score_raw
    assert (panel.economic_institutional_score_raw - expected).abs().max() < 1e-12
    assert panel.economic_institutional_score_raw.between(0, 1).all()

def test_component_scores_and_bit_states_complete(panel):
    assert panel[["trade_agreement_score_raw", "bit_structural_score_raw"]].notna().all().all()
    assert panel.bit_year_end_state.notna().all()

def test_2025_verified_carry_forward(panel):
    assert len(panel[panel.year.eq(2025)]) == 382
    assert panel.loc[panel.year.eq(2025), "economic_institutional_evidence_status"].eq("verified_unchanged_carry_forward").all()

def test_2025_values_equal_2024(panel):
    fields = ["trade_agreement_score_raw", "bit_structural_score_raw", "economic_institutional_score_raw", "bit_year_end_state"]
    x = panel[panel.year.isin([2024, 2025])].pivot(index=["country_iso3", "anchor"], columns="year", values=fields)
    for field in fields:
        left, right = x[(field, 2024)], x[(field, 2025)]
        assert (left.eq(right) | (left.isna() & right.isna())).all()

def test_trade_family_weights(panel):
    # The upstream trade-agreement score uses 60/35/5 family weights.
    expected = (
        0.60 * panel.bilateral_fta_active.astype(float)
        + 0.35 * panel.regional_fta_active.astype(float)
        + 0.05 * panel.sectoral_trade_agreement_active.astype(float)
    ).clip(upper=1.0)
    assert (panel.trade_agreement_score_raw - expected).abs().max() < 1e-12

def test_summary_reconciles(panel):
    summary = b.build_summary(panel)
    assert summary["rows"] == 8410
    assert summary["evidence_status_counts"] == {"directly_reconstructed": 8028, "verified_unchanged_carry_forward": 382}
    assert all(value == 0 for value in summary["validation_failures"].values())
