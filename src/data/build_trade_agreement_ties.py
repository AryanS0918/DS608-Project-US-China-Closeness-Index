"""Build annual economic trade-agreement ties for China and the United States.

The source workbook contains Darren's original signed exploratory weights. This
builder preserves those weights as provenance, normalizes membership by
agreement family, reconstructs 2000-2003 from official effective dates, and
creates a bounded 0-1 trade-agreement score.
"""
from __future__ import annotations

import argparse
import json
import re
import unicodedata
from pathlib import Path
from typing import Any

import pandas as pd

KEYS = ["country_iso3", "anchor", "year"]
METHOD_VERSION = "trade_agreement_ties_v2_year_end_reconstructed"
SCORE_WEIGHTS = {
    "bilateral_comprehensive_fta": 0.60,
    "regional_trade_agreement": 0.35,
    "sectoral_trade_agreement": 0.05,
}
AGREEMENTS = {
    "Bilateral FTA with US": ("us_bilateral_fta", "United States", "bilateral_comprehensive_fta", 2),
    "USMCA/NAFTA": ("usmca_nafta", "United States", "regional_trade_agreement", 1),
    "CAFTA-DR": ("cafta_dr", "United States", "regional_trade_agreement", 1),
    "US-Japan critical minerals": ("us_japan_critical_minerals", "United States", "sectoral_trade_agreement", 2),
    "Bilateral FTA with China": ("china_bilateral_fta", "China", "bilateral_comprehensive_fta", -2),
    "China-ASEAN FTA": ("china_asean_fta", "China", "regional_trade_agreement", -1),
    "Regional Comprehensive Economic Partnership": ("rcep", "China", "regional_trade_agreement", -1),
    "Asia Pacific Trade Agreement": ("apta", "China", "regional_trade_agreement", -1),
}
NAME_ALIASES = {
    "bahamas": "BHS", "bolivia": "BOL", "brunei": "BRN", "cape verde": "CPV",
    "china": "CHN", "congo democratic republic": "COD", "congo republic": "COG",
    "cote d ivoire": "CIV", "east timor": "TLS", "iran": "IRN", "laos": "LAO",
    "malaysia": "MYS", "north korea": "PRK", "north macedonia": "MKD",
    "russia": "RUS", "south korea": "KOR", "sri lanka": "LKA", "syria": "SYR",
    "taiwan": "TWN", "tanzania": "TZA", "turkey": "TUR", "united states": "USA",
    "venezuela": "VEN", "vietnam": "VNM",
}
# Year-end states reconstructed from official effective dates.
# Israel-US FTA entered into force in 1985; NAFTA in 1994; Jordan-US FTA on
# 17 December 2001. China acceded to APTA in 2001, joining the five existing
# participating states listed below.
PRE2004_MEMBERSHIPS = [
    ("ISR", "United States", 2000, 2003, "us_bilateral_fta", "bilateral_comprehensive_fta", 2,
     "USTR Israel FTA; entered into force 1985"),
    ("CAN", "United States", 2000, 2003, "usmca_nafta", "regional_trade_agreement", 1,
     "USTR NAFTA; entered into force 1994"),
    ("MEX", "United States", 2000, 2003, "usmca_nafta", "regional_trade_agreement", 1,
     "USTR NAFTA; entered into force 1994"),
    ("JOR", "United States", 2001, 2003, "us_bilateral_fta", "bilateral_comprehensive_fta", 2,
     "USTR Jordan FTA; entered into force 17 December 2001"),
    ("BGD", "China", 2001, 2003, "apta", "regional_trade_agreement", -1,
     "UN ESCAP APTA; China acceded in 2001"),
    ("IND", "China", 2001, 2003, "apta", "regional_trade_agreement", -1,
     "UN ESCAP APTA; China acceded in 2001"),
    ("LAO", "China", 2001, 2003, "apta", "regional_trade_agreement", -1,
     "UN ESCAP APTA; China acceded in 2001"),
    ("KOR", "China", 2001, 2003, "apta", "regional_trade_agreement", -1,
     "UN ESCAP APTA; China acceded in 2001"),
    ("LKA", "China", 2001, 2003, "apta", "regional_trade_agreement", -1,
     "UN ESCAP APTA; China acceded in 2001"),
]


def normalize_name(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value))
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = text.lower().replace("&", " and ")
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", text)).strip()


def load_universe(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path, low_memory=False)
    fields = ["country_iso3", "country_name", "historical_entity", "anchor", "year"]
    missing = set(fields).difference(frame.columns)
    if missing:
        raise KeyError(f"Production universe is missing: {sorted(missing)}")
    universe = frame[fields].drop_duplicates().sort_values(KEYS).reset_index(drop=True)
    if universe.duplicated(KEYS).any():
        raise ValueError("Duplicate production-universe keys")
    return universe


def build_name_map(universe: pd.DataFrame) -> dict[str, str]:
    names = universe[["country_iso3", "country_name"]].drop_duplicates()
    mapping = {normalize_name(row.country_name): row.country_iso3 for row in names.itertuples(index=False)}
    mapping.update({normalize_name(code): code for code in names["country_iso3"].astype(str)})
    mapping.update(NAME_ALIASES)
    return mapping


def workbook_register(path: Path, name_map: dict[str, str], end_year: int) -> pd.DataFrame:
    raw = pd.read_excel(path, sheet_name="Treaties", header=None, engine="openpyxl")
    records: list[dict[str, Any]] = []
    for column in range(1, raw.shape[1]):
        agreement_name = raw.iloc[0, column]
        year_value = pd.to_numeric(pd.Series([raw.iloc[1, column]]), errors="coerce").iloc[0]
        if agreement_name not in AGREEMENTS or pd.isna(year_value):
            continue
        year = int(year_value)
        if year < 2004 or year > end_year:
            continue
        agreement_id, anchor, family, expected_weight = AGREEMENTS[str(agreement_name)]
        values = pd.to_numeric(raw.iloc[2:, column], errors="coerce")
        countries = raw.iloc[2:, 0].astype("string").str.strip()
        for country, value in zip(countries, values):
            if pd.isna(country) or pd.isna(value) or str(country).upper() == "TOTAL":
                continue
            iso3 = name_map.get(normalize_name(country))
            records.append({
                "country_source_name": str(country), "country_iso3": iso3, "anchor": anchor,
                "year": year, "agreement_name": str(agreement_name), "agreement_id": agreement_id,
                "agreement_family": family, "member": True,
                "original_signed_weight": float(value),
                "original_weight_magnitude": abs(float(value)),
                "expected_original_weight": expected_weight,
                "record_source": "annual_workbook",
                "source_note": "US-China Index Treaties workbook",
            })
    return pd.DataFrame(records)


def reconstructed_register(universe: pd.DataFrame, start_year: int) -> pd.DataFrame:
    valid = set(universe["country_iso3"].astype(str))
    records: list[dict[str, Any]] = []
    for iso3, anchor, first_year, last_year, agreement_id, family, weight, note in PRE2004_MEMBERSHIPS:
        if iso3 not in valid:
            raise ValueError(f"Reconstructed ISO3 is outside the universe: {iso3}")
        for year in range(max(start_year, first_year), last_year + 1):
            records.append({
                "country_source_name": iso3, "country_iso3": iso3, "anchor": anchor,
                "year": year, "agreement_name": agreement_id, "agreement_id": agreement_id,
                "agreement_family": family, "member": True,
                "original_signed_weight": float(weight),
                "original_weight_magnitude": abs(float(weight)),
                "expected_original_weight": weight,
                "record_source": "official_date_reconstruction",
                "source_note": note,
            })
    return pd.DataFrame(records)


def build_register(workbook: Path, universe: pd.DataFrame, start_year: int, end_year: int) -> pd.DataFrame:
    register = pd.concat(
        [workbook_register(workbook, build_name_map(universe), end_year),
         reconstructed_register(universe, start_year)],
        ignore_index=True,
    )
    unresolved = register[register["country_iso3"].isna()]["country_source_name"].drop_duplicates()
    if not unresolved.empty:
        raise ValueError(f"Unresolved treaty names: {unresolved.tolist()}")
    if register.duplicated(KEYS + ["agreement_id"]).any():
        rows = register[register.duplicated(KEYS + ["agreement_id"], keep=False)]
        raise ValueError(f"Duplicate agreement memberships: {rows.head().to_dict('records')}")
    return register.sort_values(KEYS + ["agreement_id"]).reset_index(drop=True)


def aggregate(register: pd.DataFrame, universe: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for keys, group in register.groupby(KEYS, sort=False):
        agreements = sorted(group["agreement_id"].unique())
        families = sorted(group["agreement_family"].unique())
        bilateral = int(group["agreement_family"].eq("bilateral_comprehensive_fta").sum())
        regional = int(group["agreement_family"].eq("regional_trade_agreement").sum())
        sectoral = int(group["agreement_family"].eq("sectoral_trade_agreement").sum())
        score = (
            SCORE_WEIGHTS["bilateral_comprehensive_fta"] * int(bilateral > 0)
            + SCORE_WEIGHTS["regional_trade_agreement"] * int(regional > 0)
            + SCORE_WEIGHTS["sectoral_trade_agreement"] * int(sectoral > 0)
        )
        rows.append({
            "country_iso3": keys[0], "anchor": keys[1], "year": keys[2],
            "bilateral_fta_active": bilateral > 0, "regional_fta_active": regional > 0,
            "sectoral_trade_agreement_active": sectoral > 0,
            "bilateral_fta_count": bilateral, "regional_fta_count": regional,
            "sectoral_trade_agreement_count": sectoral,
            "active_trade_agreement_count": len(agreements),
            "active_trade_agreement_family_count": len(families),
            "active_trade_agreement_ids": "|".join(agreements),
            "active_trade_agreement_families": "|".join(families),
            "original_signed_weight_sum": float(group["original_signed_weight"].sum()),
            "original_absolute_weight_sum": float(group["original_weight_magnitude"].sum()),
            "reconstructed_record_count": int(group["record_source"].eq("official_date_reconstruction").sum()),
            "trade_agreement_score_raw": score,
            "trade_agreement_score_scaled": 100.0 * score,
        })
    annual = pd.DataFrame(rows)
    panel = universe.merge(annual, on=KEYS, how="left", validate="one_to_one")
    bools = ["bilateral_fta_active", "regional_fta_active", "sectoral_trade_agreement_active"]
    counts = ["bilateral_fta_count", "regional_fta_count", "sectoral_trade_agreement_count",
              "active_trade_agreement_count", "active_trade_agreement_family_count", "reconstructed_record_count"]
    nums = ["original_signed_weight_sum", "original_absolute_weight_sum",
            "trade_agreement_score_raw", "trade_agreement_score_scaled"]
    texts = ["active_trade_agreement_ids", "active_trade_agreement_families"]
    for column in bools:
        panel[column] = panel[column].map(
            lambda value: False if pd.isna(value) else bool(value)
        ).astype(bool)
    for column in counts:
        panel[column] = pd.to_numeric(panel[column], errors="coerce").fillna(0).astype(int)
    for column in nums:
        panel[column] = pd.to_numeric(panel[column], errors="coerce").fillna(0.0)
    for column in texts:
        panel[column] = panel[column].fillna("")
    panel["trade_agreement_source_available"] = True
    panel["any_trade_agreement_active"] = panel["active_trade_agreement_count"].gt(0)
    panel["bilateral_plus_regional"] = panel["bilateral_fta_active"] & panel["regional_fta_active"]
    panel["multiple_regional_agreements"] = panel["regional_fta_count"].gt(1)
    panel["method_version"] = METHOD_VERSION
    return panel.sort_values(KEYS).reset_index(drop=True)


def validate(panel: pd.DataFrame, register: pd.DataFrame) -> dict[str, Any]:
    recomputed = (
        0.60 * panel["bilateral_fta_active"].astype(int)
        + 0.35 * panel["regional_fta_active"].astype(int)
        + 0.05 * panel["sectoral_trade_agreement_active"].astype(int)
    )
    failures = {
        "duplicate_keys": int(panel.duplicated(KEYS).sum()),
        "blank_country_names": int(panel["country_name"].isna().sum()),
        "unresolved_register_countries": int(register["country_iso3"].isna().sum()),
        "original_weight_mismatches": int((register["original_signed_weight"] != register["expected_original_weight"]).sum()),
        "score_formula_mismatches": int((panel["trade_agreement_score_raw"] - recomputed).abs().gt(1e-12).sum()),
        "score_bound_failures": int((~panel["trade_agreement_score_raw"].between(0, 1)).sum()),
        "source_unavailable_rows": int((~panel["trade_agreement_source_available"]).sum()),
    }
    nonzero = {k: v for k, v in failures.items() if v}
    if nonzero:
        raise AssertionError(f"Trade-agreement validation failed: {nonzero}")
    return {
        "rows": len(panel),
        "countries_or_historical_entities": int(panel["country_iso3"].nunique()),
        "study_years": [int(panel["year"].min()), int(panel["year"].max())],
        "normalized_membership_records": len(register),
        "officially_reconstructed_records": int(register["record_source"].eq("official_date_reconstruction").sum()),
        "score_weights": SCORE_WEIGHTS,
        "score_distribution": panel["trade_agreement_score_raw"].value_counts().sort_index().to_dict(),
        "validation_failures": failures,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workbook", type=Path, default=Path("data/sources/relations/US-China Index Treaties.xlsx"))
    parser.add_argument("--universe", type=Path, default=Path("data/processed/relationship_condition_country_anchor_year.csv"))
    parser.add_argument("--output", type=Path, default=Path("data/processed/trade_agreement_ties_country_anchor_year.csv"))
    parser.add_argument("--report-directory", type=Path, default=Path("outputs/tables/trade_agreement_ties"))
    parser.add_argument("--start-year", type=int, default=2000)
    parser.add_argument("--end-year", type=int, default=2024)
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.report_directory.mkdir(parents=True, exist_ok=True)

    universe = load_universe(args.universe)
    register = build_register(args.workbook, universe, args.start_year, args.end_year)
    panel = aggregate(register, universe)
    summary = validate(panel, register)
    overlap = (
        panel.groupby(["anchor", "bilateral_fta_active", "regional_fta_count",
                       "sectoral_trade_agreement_active", "active_trade_agreement_family_count"], dropna=False)
        .size().rename("country_anchor_years").reset_index()
        .sort_values(["anchor", "country_anchor_years"], ascending=[True, False])
    )
    mismatches = register[register["original_signed_weight"] != register["expected_original_weight"]]

    panel.to_csv(args.output, index=False)
    register.to_csv(args.report_directory / "trade_agreement_membership_normalized.csv", index=False)
    overlap.to_csv(args.report_directory / "trade_agreement_overlap_profile.csv", index=False)
    mismatches.to_csv(args.report_directory / "trade_agreement_weight_mismatches.csv", index=False)
    (args.report_directory / "trade_agreement_panel_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print("=" * 72)
    print("ECONOMIC TRADE-AGREEMENT PRODUCTION PANEL")
    print("=" * 72)
    print(json.dumps(summary, indent=2))
    print("\nProduction output:", args.output)
    print("Reports directory:", args.report_directory)


if __name__ == "__main__":
    main()
