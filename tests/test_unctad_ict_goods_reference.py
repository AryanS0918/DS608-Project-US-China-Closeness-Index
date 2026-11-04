from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
REFERENCE_PATH = ROOT / "data" / "reference" / "unctad_ict_goods_hs6.csv"
EXPECTED_HS_REVISIONS = {
    "HS1992",
    "HS1996",
    "HS2002",
    "HS2007",
    "HS2012",
    "HS2017",
    "HS2022",
}
EXPECTED_ICT_CATEGORIES = {"ICT01", "ICT02", "ICT03", "ICT04", "ICT05"}


def test_reference_has_all_editions_categories_and_unique_codes():
    reference = pd.read_csv(REFERENCE_PATH, dtype={"hs6_code": str})

    assert set(reference["hs_revision"]) == EXPECTED_HS_REVISIONS
    assert set(reference["ict_category_code"]) == EXPECTED_ICT_CATEGORIES
    assert reference["hs6_code"].str.fullmatch(r"\d{6}").all()
    assert not reference.duplicated(["hs_revision", "hs6_code"]).any()
    assert reference["include_broad_ict"].eq(True).all()
    assert not reference.loc[
        reference["ict_category_code"].eq("ICT03"), "include_baseline"
    ].any()
