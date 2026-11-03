import importlib.util
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "builder", ROOT / "src/data/build_trade_orientation.py"
)
b = importlib.util.module_from_spec(spec)
spec.loader.exec_module(b)

@pytest.fixture(scope="module")
def inputs():
    return (
        pd.read_csv(
            ROOT / "data/processed/trade_total_country_year.csv",
            low_memory=False,
        ),
        pd.read_csv(
            ROOT
            / "outputs/tables/relations_condition/relationship_condition_country_master.csv",
            low_memory=False,
        ),
    )

@pytest.fixture(scope="module")
def output(inputs):
    return b.build_trade_orientation(*inputs)


def test_expected_dimensions(output):
    assert len(output) == 4205
    assert output.country_iso3.nunique() == 192
    assert (output.year.min(), output.year.max()) == (2004, 2025)


def test_unique_keys(output):
    assert not output.duplicated(["country_iso3", "year"]).any()


def test_year_counts_and_scg_window(output):
    counts = output.groupby("year").size().to_dict()
    assert all(counts[year] == 192 for year in (2004, 2005, 2006))
    assert all(counts[year] == 191 for year in range(2007, 2026))
    assert set(output.loc[output.country_iso3.eq("SCG"), "year"]) == {
        2004,
        2005,
        2006,
    }


def test_excluded_entities_absent(output):
    excluded = {"CHN", "USA", "COK", "HKG", "MSR", "PSE", "TWN", "VAT"}
    assert excluded.isdisjoint(set(output.country_iso3))


def test_preferred_names_present(output):
    expected = {
        "LKA": "Sri Lanka",
        "MKD": "North Macedonia",
        "MYS": "Malaysia",
        "SWZ": "Eswatini",
        "TLS": "Timor-Leste",
        "TUR": "Turkiye",
    }
    actual = (
        output.drop_duplicates("country_iso3")
        .set_index("country_iso3")
        .preferred_country_name
        .to_dict()
    )
    for iso3, name in expected.items():
        assert actual[iso3] == name


def test_score_requires_four_flows(output):
    scored = output.trade_orientation_score.notna()
    assert output.loc[scored, b.FLOW_COLUMNS].notna().all(axis=1).all()
    assert output.loc[scored, "complete_four_flow_record"].eq(True).all()


def test_missing_evidence_never_zero_filled(output):
    unavailable = output.trade_orientation_score.isna()
    assert output.loc[unavailable, "trade_evidence_status"].isin(
        ["source_row_incomplete_four_flows", "no_source_row"]
    ).all()


def test_formula_exact(output):
    scored = output[output.trade_orientation_score.notna()]
    expected = (
        scored.us_total_trade_usd - scored.china_total_trade_usd
    ) / (
        scored.us_total_trade_usd + scored.china_total_trade_usd
    )
    assert (scored.trade_orientation_score - expected).abs().max() < 1e-12


def test_score_bounds(output):
    assert output.trade_orientation_score.dropna().between(-1, 1).all()


def test_provenance_counts_reconcile(output):
    scored = output.trade_orientation_score.notna()
    assert (
        output.loc[scored, "mirror_flow_count"].astype(int)
        + output.loc[scored, "reporter_side_flow_count"].astype(int)
    ).eq(4).all()
    assert output.loc[scored, "trade_provenance_status"].isin(
        ["all_reporter_side", "includes_mirror_side_recovery"]
    ).all()


def test_recent_coverage_counts(output):
    counts = output.groupby("year").trade_orientation_score.count().to_dict()
    assert counts[2024] == 140
    assert counts[2025] == 122


def test_2025_is_provisional(output):
    x = output[output.year.eq(2025)]
    assert len(x) == 191
    assert x.loc[x.trade_orientation_score.notna(), "trade_comparability_status"].eq(
        "provisional_latest_year_extension"
    ).all()
    assert x.loc[x.trade_orientation_score.isna(), "trade_comparability_status"].eq(
        "provisional_latest_year_score_unavailable"
    ).all()
