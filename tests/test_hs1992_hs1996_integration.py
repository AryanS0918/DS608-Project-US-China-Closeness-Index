from pathlib import Path
import ast

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
COLLECTOR_PATH = ROOT / "src" / "data" / "collect_technology_trade.py"
REFERENCE_PATH = ROOT / "data" / "reference" / "unctad_ict_goods_hs6.csv"


def test_historical_classification_map():
    tree = ast.parse(COLLECTOR_PATH.read_text(encoding="utf-8"))
    mapping = None

    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == "CLASSIFICATION_MAP"
            for target in node.targets
        ):
            mapping = ast.literal_eval(node.value)
            break

    assert mapping is not None, "CLASSIFICATION_MAP was not found in the collector"
    assert mapping["H0"] == "HS1992"
    assert mapping["H1"] == "HS1996"


def test_reference_integrity():
    reference = pd.read_csv(REFERENCE_PATH, dtype={"hs6_code": str})

    assert {"HS1992", "HS1996"}.issubset(set(reference["hs_revision"]))
    assert not reference.duplicated(["hs_revision", "hs6_code"]).any()
    assert reference["hs6_code"].str.fullmatch(r"\d{6}").all()

    flags = [
        "include_baseline",
        "include_three_category",
        "include_broad_ict",
        "include_narrow_core",
    ]
    assert reference[flags].notna().all().all()

    counts = reference.groupby("hs_revision").size()
    assert counts.loc["HS1992"] == 90
    assert counts.loc["HS1996"] == 110


def test_category_basket_rules():
    reference = pd.read_csv(REFERENCE_PATH, dtype={"hs6_code": str})
    historical = reference.loc[
        reference["hs_revision"].isin(["HS1992", "HS1996"])
    ]

    assert historical.loc[
        historical["ict_category_code"].eq("ICT03"), "include_baseline"
    ].eq(False).all()
    assert historical.loc[
        historical["ict_category_code"].eq("ICT05"),
        "include_three_category",
    ].eq(False).all()
    assert historical["include_broad_ict"].eq(True).all()
