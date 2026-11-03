import importlib.util
from pathlib import Path
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("builder", ROOT / "src/data/build_fdi_structural_ties.py")
b = importlib.util.module_from_spec(spec)
spec.loader.exec_module(b)

@pytest.fixture(scope="module")
def inputs():
    return (
        pd.read_csv(ROOT / "data/interim/fdi/imf_dip_primary_candidates.csv", low_memory=False),
        pd.read_csv(ROOT / "outputs/tables/fdi/imf_dip_country_crosswalk_audit.csv", low_memory=False),
        pd.read_csv(ROOT / "outputs/tables/relations_condition/relationship_condition_country_master.csv", low_memory=False),
    )

@pytest.fixture(scope="module")
def result(inputs):
    return b.build_panel(*inputs)

@pytest.fixture(scope="module")
def panel(result): return result[0]

@pytest.fixture(scope="module")
def crosswalk_audit(result): return result[1]

def test_dimensions(panel):
    assert len(panel) == 8410
    assert panel.country_iso3.nunique() == 192
    assert (panel.year.min(), panel.year.max()) == (2004, 2025)

def test_unique_keys(panel):
    assert not panel.duplicated(["country_iso3", "anchor", "year"]).any()

def test_scg_window_and_exclusions(panel):
    assert set(panel.loc[panel.country_iso3.eq("SCG"), "year"]) == {2004, 2005, 2006}
    assert {"CHN", "USA", "TWN", "HKG", "PSE", "VAT"}.isdisjoint(set(panel.country_iso3))

def test_preferred_names(panel):
    expected = {"LKA":"Sri Lanka", "MKD":"North Macedonia", "MYS":"Malaysia", "SWZ":"Eswatini", "TLS":"Timor-Leste", "TUR":"Turkiye"}
    actual = panel.drop_duplicates("country_iso3").set_index("country_iso3").preferred_country_name.to_dict()
    for iso3, name in expected.items(): assert actual[iso3] == name

def test_source_period_only(panel):
    outside = ~panel.year.between(2018, 2024)
    assert panel.loc[outside, "fdi_structural_score_raw"].isna().all()
    assert panel.loc[panel.year.lt(2018), "fdi_comparability_status"].eq("pre_fdi_source_period_unavailable").all()
    assert panel.loc[panel.year.eq(2025), "fdi_comparability_status"].eq("provisional_latest_year_source_unavailable").all()

def test_observed_positions_are_scored(panel):
    source = panel.year.between(2018, 2024)
    assert panel.loc[source & panel.observed, "fdi_structural_score_raw"].notna().all()
    assert panel.loc[source & ~panel.observed, "fdi_structural_score_raw"].isna().all()

def test_zero_and_negative_score_zero(panel):
    x = panel[panel.observed_zero | panel.observed_negative]
    assert len(x) > 0
    assert x.fdi_structural_score_raw.eq(0).all()

def test_positive_scores_and_bounds(panel):
    x = panel[panel.fdi_evidence_status.eq("observed_positive_position")]
    assert x.fdi_structural_score_raw.gt(0).all()
    assert panel.fdi_structural_score_raw.dropna().between(0, 1).all()

def test_formula_exact(panel):
    x = panel[panel.observed & panel.fdi_outward_position_usd_mn.gt(0)]
    expected = (x.log_positive_position / x.log_p95_cap).clip(upper=1.0)
    assert (x.fdi_structural_score_raw - expected).abs().max() < 1e-12

def test_repaired_aliases(crosswalk_audit):
    repaired = crosswalk_audit[crosswalk_audit.canonical_mapping_status.eq("repaired_legal_form_alias")]
    assert len(repaired) == len(b.SOURCE_NAME_ALIASES)
    assert {"ARM", "EST", "MKD", "POL", "SRB", "SSD", "STP"}.issubset(set(repaired.canonical_country_iso3))

def test_summary_reconciles(panel):
    summary = b.build_summary(panel)
    assert summary["rows"] == 8410
    assert sum(summary["evidence_status_counts"].values()) == 8410
    assert all(value == 0 for value in summary["validation_failures"].values())
