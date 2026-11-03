"""Build diplomatic structural-ties scores using source-aware zero treatment.

Run from the repository root:
    python src/data/build_diplomatic_structural_ties.py

Within source-covered years, an absent directed dyad is assigned zero recorded
structural depth while retaining an explicit unobserved flag. Observed LOR=0
remains a distinct adverse source observation. Source-unavailable years and
invalid entity-years remain missing.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

ANCHORS = ("China", "United States")
PROJECT_START = 2004
PROJECT_END = 2025
SOURCE_END = 2024
METHOD_VERSION = "diplomatic_structural_ties_v2_source_aware_zero_mean75_reciprocity25"
KEYS = ["country_iso3", "anchor", "year"]

SOURCE_NAME_ALIASES = {
    "Congo-Brazzaville": "COG",
    "Congo-Kinshasa": "COD",
    "Czech Republic": "CZE",
    "Côte d'\x92Ivoire": "CIV",
    "Holy See (Vatican)": "VAT",
    "Korea, Democratic People's Republic of": "PRK",
    "Korea, Republic of": "KOR",
    "Lao People's Democratic Republic": "LAO",
    "Micronesia, Federated States of": "FSM",
    "Saint Vincent and the Grenadines": "VCT",
    "Viet Nam": "VNM",
}


def require_columns(frame: pd.DataFrame, columns: set[str], label: str) -> None:
    missing = sorted(columns - set(frame.columns))
    if missing:
        raise ValueError(f"{label} missing required columns: {missing}")


def read_wide_source(path: Path) -> pd.DataFrame:
    if path.suffix.lower() == ".parquet":
        return pd.read_parquet(path)
    return pd.read_csv(path, low_memory=False)


def build_universe(master: pd.DataFrame) -> pd.DataFrame:
    require_columns(master, {"iso3", "country_name", "preferred_country_name", "first_valid_year", "last_valid_year", "baseline_index_eligible"}, "Country master")
    eligible = master.loc[master["baseline_index_eligible"].eq(True)].copy()
    rows = []
    for row in eligible.itertuples(index=False):
        first = PROJECT_START if pd.isna(row.first_valid_year) else max(PROJECT_START, int(row.first_valid_year))
        last = PROJECT_END if pd.isna(row.last_valid_year) else min(PROJECT_END, int(row.last_valid_year))
        for year in range(first, last + 1):
            for anchor in ANCHORS:
                rows.append({"country_iso3": row.iso3, "country_name": row.country_name, "preferred_country_name": row.preferred_country_name, "anchor": anchor, "year": year})
    universe = pd.DataFrame(rows).sort_values(KEYS).reset_index(drop=True)
    if universe.duplicated(KEYS).any():
        raise ValueError("Production universe contains duplicate keys")
    return universe


def make_name_map(master: pd.DataFrame) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for row in master.itertuples(index=False):
        for name in (row.country_name, row.preferred_country_name):
            if pd.notna(name):
                if name in mapping and mapping[name] != row.iso3:
                    raise ValueError(f"Ambiguous country name in master: {name}")
                mapping[str(name)] = row.iso3
    mapping.update(SOURCE_NAME_ALIASES)
    return mapping


def prepare_source(source: pd.DataFrame, master: pd.DataFrame) -> pd.DataFrame:
    required = {"country", "anchor", "year", "LOR__anchor_to_country", "LOR__country_to_anchor", "Embassy__anchor_to_country", "Embassy__country_to_anchor", "Focus__anchor_to_country", "Focus__country_to_anchor", "EmbassyFocus__anchor_to_country", "EmbassyFocus__country_to_anchor"}
    require_columns(source, required, "Diplomatic wide source")
    result = source.copy()
    result["country_iso3"] = result["country"].map(make_name_map(master))
    unresolved = sorted(result.loc[result["country_iso3"].isna(), "country"].dropna().unique())
    if unresolved:
        raise ValueError(f"Unresolved diplomatic source countries: {unresolved}")
    if result.duplicated(["country_iso3", "anchor", "year"]).any():
        raise ValueError("Diplomatic source has duplicate country-anchor-year keys")
    return result


def build_panel(source: pd.DataFrame, master: pd.DataFrame) -> pd.DataFrame:
    universe = build_universe(master)
    evidence = prepare_source(source, master)
    keep = [
        "country_iso3", "anchor", "year",
        "LOR__anchor_to_country", "LOR__country_to_anchor",
        "Embassy__anchor_to_country", "Embassy__country_to_anchor",
        "Focus__anchor_to_country", "Focus__country_to_anchor",
        "EmbassyFocus__anchor_to_country", "EmbassyFocus__country_to_anchor",
    ]
    panel = universe.merge(evidence[keep], on=KEYS, how="left", validate="one_to_one", indicator="evidence_merge_status")
    source_available = panel["year"].between(PROJECT_START, SOURCE_END)
    for direction in ("anchor_to_country", "country_to_anchor"):
        lor_source = f"LOR__{direction}"
        panel[f"{direction}_observed"] = source_available & panel[lor_source].notna()
        panel[f"{direction}_lor_recorded"] = panel[lor_source]
        panel[f"{direction}_depth"] = np.where(source_available, panel[lor_source].fillna(0.0), np.nan)
        panel[f"{direction}_adverse"] = panel[f"{direction}_observed"] & panel[lor_source].eq(0)
        panel[f"{direction}_embassy_code"] = panel[f"Embassy__{direction}"]
        panel[f"{direction}_focus_code"] = panel[f"Focus__{direction}"]
        panel[f"{direction}_embassy_focus_code"] = panel[f"EmbassyFocus__{direction}"]
    panel["direction_count"] = panel["anchor_to_country_observed"].astype(int) + panel["country_to_anchor_observed"].astype(int)
    panel["bilateral_observed"] = panel["direction_count"].eq(2)
    panel["bilateral_adverse"] = panel["anchor_to_country_adverse"] | panel["country_to_anchor_adverse"]
    panel["source_coverage_status"] = np.select(
        [~source_available, panel["direction_count"].eq(2), panel["direction_count"].eq(1), panel["direction_count"].eq(0)],
        ["source_year_unavailable", "bilateral_observed", "unilateral_recorded_representation", "no_recorded_representation"],
        default="invalid",
    )
    a = panel["anchor_to_country_depth"]
    b = panel["country_to_anchor_depth"]
    panel["mean_depth"] = (a + b) / 2
    panel["reciprocity_depth"] = np.minimum(a, b)
    panel["depth_gap"] = (a - b).abs()
    panel["diplomatic_score_mean_only"] = panel["mean_depth"]
    panel["diplomatic_score_mean_reciprocity_75_25"] = 0.75 * panel["mean_depth"] + 0.25 * panel["reciprocity_depth"]
    panel["diplomatic_score_mean_reciprocity_50_50"] = 0.50 * panel["mean_depth"] + 0.50 * panel["reciprocity_depth"]
    panel["diplomatic_score_geometric"] = np.sqrt(a * b)
    panel["diplomatic_structural_score_raw"] = panel["diplomatic_score_mean_reciprocity_75_25"]
    panel["method_version"] = METHOD_VERSION
    drop_source = [c for c in panel.columns if c.startswith(("LOR__", "Embassy__", "Focus__", "EmbassyFocus__"))]
    return panel.drop(columns=drop_source).sort_values(KEYS).reset_index(drop=True)


def validate_panel(panel: pd.DataFrame) -> dict:
    failures = {
        "duplicate_keys": int(panel.duplicated(KEYS).sum()),
        "unexpected_rows": int(len(panel) != 8410),
        "unexpected_entities": int(panel["country_iso3"].nunique() != 192),
        "invalid_status": int((panel["source_coverage_status"] == "invalid").sum()),
        "source_unavailable_with_score": int(panel.loc[panel["source_coverage_status"].eq("source_year_unavailable"), "diplomatic_structural_score_raw"].notna().sum()),
        "covered_missing_score": int(panel.loc[panel["year"].le(SOURCE_END), "diplomatic_structural_score_raw"].isna().sum()),
        "score_out_of_bounds": int((~panel["diplomatic_structural_score_raw"].dropna().between(0, 1)).sum()),
    }
    if any(failures.values()):
        raise ValueError(f"Diplomatic panel validation failed: {failures}")
    return {
        "rows": int(len(panel)),
        "entities": int(panel["country_iso3"].nunique()),
        "years": [int(panel["year"].min()), int(panel["year"].max())],
        "scored_rows": int(panel["diplomatic_structural_score_raw"].notna().sum()),
        "missing_score_rows": int(panel["diplomatic_structural_score_raw"].isna().sum()),
        "coverage_status_counts": {k: int(v) for k, v in panel["source_coverage_status"].value_counts().items()},
        "score_summary": {k: float(v) for k, v in panel["diplomatic_structural_score_raw"].describe().items()},
        "validation_failures": failures,
    }


def write_outputs(panel: pd.DataFrame, output: Path, report_directory: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    report_directory.mkdir(parents=True, exist_ok=True)
    panel.to_csv(output, index=False)
    summary = validate_panel(panel)
    (report_directory / "diplomatic_structural_ties_summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    methods = ["diplomatic_score_mean_only", "diplomatic_score_mean_reciprocity_75_25", "diplomatic_score_mean_reciprocity_50_50", "diplomatic_score_geometric"]
    panel.loc[panel["year"].le(SOURCE_END), KEYS + methods].to_csv(report_directory / "diplomatic_score_method_comparison.csv", index=False)
    panel.loc[panel["year"].le(SOURCE_END)].groupby(["year", "anchor"])[methods].mean().reset_index().to_csv(report_directory / "diplomatic_score_sensitivity_by_year.csv", index=False)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=Path("data/interim/relations/drd_anchor_country_year.csv"))
    parser.add_argument("--country-master", type=Path, default=Path("outputs/tables/relations_condition/relationship_condition_country_master.csv"))
    parser.add_argument("--output", type=Path, default=Path("data/processed/diplomatic_structural_ties_country_anchor_year.csv"))
    parser.add_argument("--report-directory", type=Path, default=Path("outputs/tables/diplomatic_structural_ties"))
    args = parser.parse_args()
    source = read_wide_source(args.source)
    master = pd.read_csv(args.country_master, low_memory=False)
    panel = build_panel(source, master)
    write_outputs(panel, args.output, args.report_directory)
    print(f"Wrote {len(panel):,} rows to {args.output}")


if __name__ == "__main__":
    main()
