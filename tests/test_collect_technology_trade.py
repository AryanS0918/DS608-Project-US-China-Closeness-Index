import json

import pandas as pd

from src.data.collect_technology_trade import (
    CLASSIFICATION_MAP,
    cache_is_compatible,
    metadata_file_path,
    product_batches,
    request_signature,
    load_reporters,
    write_reporter_cache,
)


def test_supported_comtrade_classifications_map_to_reference_editions():
    assert CLASSIFICATION_MAP == {
        "H0": "HS1992",
        "H1": "HS1996",
        "H2": "HS2002",
        "H3": "HS2007",
        "H4": "HS2012",
        "H5": "HS2017",
        "H6": "HS2022",
    }


def test_product_batches_preserve_all_codes():
    codes = [f"{value:06d}" for value in range(205)]
    batches = product_batches(codes, 100)
    assert [len(batch) for batch in batches] == [100, 100, 5]
    assert [code for batch in batches for code in batch] == codes


def test_request_signature_is_order_invariant_for_codes():
    first = request_signature(
        2022,
        "H6",
        "CHN",
        "include_broad_ict",
        ["111111", "222222"],
    )
    second = request_signature(
        2022,
        "H6",
        "CHN",
        "include_broad_ict",
        ["222222", "111111"],
    )
    assert first == second


def test_cache_requires_matching_metadata_signature(tmp_path):
    raw_path = tmp_path / "JPN_imports_from_chn.csv"
    pd.DataFrame({"cmdCode": ["847130"]}).to_csv(raw_path, index=False)
    metadata_file_path(raw_path).write_text(
        json.dumps({"request_signature": "expected"}),
        encoding="utf-8",
    )
    assert cache_is_compatible(raw_path, "expected")
    assert not cache_is_compatible(raw_path, "different")


def test_load_reporters_flags_missing_codes_without_dropping_country(tmp_path):
    master_path = tmp_path / "outputs" / "tables" / "relations_condition"
    trade_path = tmp_path / "data" / "processed"
    master_path.mkdir(parents=True)
    trade_path.mkdir(parents=True)
    pd.DataFrame({
        "iso3": ["AAA", "BBB"],
        "country_name": ["Available", "Missing"],
        "baseline_index_eligible": [True, True],
    }).to_csv(master_path / "relationship_condition_country_master.csv", index=False)
    pd.DataFrame({
        "reporter_iso": ["AAA"],
        "reporter_code": [1],
    }).to_csv(trade_path / "trade_total_country_year.csv", index=False)
    result = load_reporters(tmp_path, pilot=False).set_index("reporter_iso")
    assert bool(result.loc["AAA", "technology_trade_available"])
    assert not bool(result.loc["BBB", "technology_trade_available"])
    assert result.loc["BBB", "technology_trade_unavailable_reason"] == (
        "no_established_comtrade_reporter_code"
    )


def test_empty_cache_is_readable_csv(tmp_path):
    raw_path = tmp_path / "empty.csv"
    write_reporter_cache(
        pd.DataFrame(),
        raw_path,
        {"request_signature": "empty-test", "status": "downloaded_empty"},
    )
    cached = pd.read_csv(raw_path, dtype={"cmdCode": str})
    assert cached.empty
    assert {"reporterCode", "partnerCode", "period", "flowCode", "cmdCode", "primaryValue"}.issubset(cached.columns)
    assert cache_is_compatible(raw_path, "empty-test")
