"""Build canonical FDI structural-ties scores from IMF DIP positions.

Run from the repository root:
    python src/data/build_fdi_structural_ties.py

The canonical panel spans 2004-2025. Official comparable outward-position
scores are available only for 2018-2024; other years remain explicitly source
unavailable. Positive positions use log1p intensity scaled to the anchor-year
95th percentile. Observed zero and negative net positions receive zero
intensity, while unobserved positions remain missing.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

ANCHOR_ISO3 = {"China": "CHN", "United States": "USA"}
ANCHORS = tuple(ANCHOR_ISO3)
PROJECT_START = 2004
PROJECT_END = 2025
SOURCE_START = 2018
SOURCE_END = 2024
KEYS = ["country_iso3", "anchor", "year"]
METHOD = "official_outward_positive_log1p_scaled_to_anchor_year_p95"
SOURCE = "IMF Direct Investment Positions"

SOURCE_NAME_ALIASES = {
    "Afghanistan, Islamic Republic of": "AFG",
    "Andorra, Principality of": "AND",
    "Armenia, Republic of": "ARM",
    "Azerbaijan, Republic of": "AZE",
    "Bahrain, Kingdom of": "BHR",
    "Belarus, Republic of": "BLR",
    "Comoros, Union of the": "COM",
    "Congo, Republic of": "COG",
    "Croatia, Republic of": "HRV",
    "Equatorial Guinea, Republic of": "GNQ",
    "Estonia, Republic of": "EST",
    "Fiji, Republic of": "FJI",
    "Kazakhstan, Republic of": "KAZ",
    "Latvia, Republic of": "LVA",
    "Lesotho, Kingdom of": "LSO",
    "Liechtenstein, Principality of": "LIE",
    "Lithuania, Republic of": "LTU",
    "Madagascar, Republic of": "MDG",
    "Mauritania, Islamic Republic of": "MRT",
    "Mozambique, Republic of": "MOZ",
    "North Macedonia, Republic of": "MKD",
    "Palau, Republic of": "PLW",
    "Poland, Republic of": "POL",
    "San Marino, Republic of": "SMR",
    "Serbia, Republic of": "SRB",
    "Slovak Republic": "SVK",
    "Slovenia, Republic of": "SVN",
    "South Sudan, Republic of": "SSD",
    "São Tomé and Príncipe, Democratic Republic of": "STP",
    "Tajikistan, Republic of": "TJK",
    "Uzbekistan, Republic of": "UZB",
}


def require_columns(frame: pd.DataFrame, required: set[str], label: str) -> None:
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(f"{label} missing required columns: {missing}")


def build_universe(country_master: pd.DataFrame) -> pd.DataFrame:
    require_columns(
        country_master,
        {
            "iso3", "country_name", "preferred_country_name",
            "first_valid_year", "last_valid_year", "baseline_index_eligible",
        },
        "Country master",
    )
    rows = []
    for row in country_master.loc[
        country_master["baseline_index_eligible"].eq(True)
    ].itertuples(index=False):
        first = PROJECT_START if pd.isna(row.first_valid_year) else max(PROJECT_START, int(row.first_valid_year))
        last = PROJECT_END if pd.isna(row.last_valid_year) else min(PROJECT_END, int(row.last_valid_year))
        for year in range(first, last + 1):
            for anchor in ANCHORS:
                rows.append({
                    "country_iso3": row.iso3,
                    "country_name": row.country_name,
                    "preferred_country_name": row.preferred_country_name,
                    "anchor": anchor,
                    "year": year,
                })
    universe = pd.DataFrame(rows).sort_values(KEYS).reset_index(drop=True)
    if universe.duplicated(KEYS).any():
        raise ValueError("Canonical FDI universe contains duplicate keys.")
    return universe


def build_source_name_map(
    crosswalk: pd.DataFrame,
    country_master: pd.DataFrame,
) -> tuple[dict[str, str], pd.DataFrame]:
    require_columns(
        crosswalk,
        {"country_source_name", "country_iso3", "mapping_method", "entity_category"},
        "IMF DIP crosswalk",
    )
    if crosswalk["country_source_name"].duplicated().any():
        raise ValueError("IMF DIP crosswalk has duplicate source names.")
    valid_iso = set(country_master.loc[
        country_master["baseline_index_eligible"].eq(True), "iso3"
    ])
    mapping = {
        row.country_source_name: row.country_iso3
        for row in crosswalk.itertuples(index=False)
        if pd.notna(row.country_iso3) and row.country_iso3 in valid_iso
    }
    mapping.update({
        name: iso3 for name, iso3 in SOURCE_NAME_ALIASES.items() if iso3 in valid_iso
    })
    audit = crosswalk.copy()
    audit["canonical_country_iso3"] = audit["country_source_name"].map(mapping)
    audit["canonical_mapping_status"] = np.select(
        [
            audit["country_source_name"].isin(SOURCE_NAME_ALIASES),
            audit["canonical_country_iso3"].notna(),
            audit["entity_category"].eq("aggregate"),
        ],
        ["repaired_legal_form_alias", "retained_existing_mapping", "excluded_aggregate"],
        default="excluded_outside_baseline_or_unresolved",
    )
    return mapping, audit


def select_official_outward(
    candidates: pd.DataFrame,
    mapping: dict[str, str],
) -> pd.DataFrame:
    require_columns(
        candidates,
        {
            "country_source_name", "anchor", "reporting_perspective",
            "economic_direction", "DV_TYPE", "year",
            "fdi_position_usd_millions", "observed", "negative", "zero",
        },
        "IMF DIP candidates",
    )
    selected = candidates.loc[
        candidates["economic_direction"].eq("anchor_to_country")
        & candidates["reporting_perspective"].eq("anchor_report")
        & candidates["DV_TYPE"].eq("Reported official data")
        & candidates["anchor"].isin(ANCHORS)
        & candidates["year"].between(SOURCE_START, SOURCE_END)
    ].copy()
    selected["country_iso3"] = selected["country_source_name"].map(mapping)
    selected = selected.loc[selected["country_iso3"].notna()].copy()
    selected = selected.loc[
        selected["country_iso3"] != selected["anchor"].map(ANCHOR_ISO3)
    ]
    if selected.duplicated(KEYS).any():
        bad = selected.loc[selected.duplicated(KEYS, keep=False), KEYS]
        raise ValueError(
            "Official outward FDI selection has duplicate keys: "
            f"{bad.head().to_dict('records')}"
        )
    return selected


def score_anchor_year(group: pd.DataFrame) -> pd.DataFrame:
    result = group.copy()
    observed_positive = result["observed"] & result["fdi_outward_position_usd_mn"].gt(0)
    result["positive_position_usd_mn"] = result[
        "fdi_outward_position_usd_mn"
    ].where(observed_positive, 0.0)
    result["log_positive_position"] = np.log1p(result["positive_position_usd_mn"])
    positive_logs = result.loc[observed_positive, "log_positive_position"]
    cap = float(positive_logs.quantile(0.95)) if not positive_logs.empty else np.nan
    result["log_p95_cap"] = cap
    result["fdi_structural_score_raw"] = np.nan
    if pd.notna(cap) and cap > 0:
        result.loc[result["observed"], "fdi_structural_score_raw"] = (
            result.loc[result["observed"], "log_positive_position"] / cap
        ).clip(upper=1.0)
    elif result["observed"].any():
        result.loc[result["observed"], "fdi_structural_score_raw"] = 0.0
    return result


def build_panel(
    candidates: pd.DataFrame,
    crosswalk: pd.DataFrame,
    country_master: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    universe = build_universe(country_master)
    mapping, crosswalk_audit = build_source_name_map(crosswalk, country_master)
    selected = select_official_outward(candidates, mapping)
    evidence = selected[
        ["country_iso3", "anchor", "year", "country_source_name", "fdi_position_usd_millions", "observed", "negative", "zero"]
    ].rename(columns={
        "fdi_position_usd_millions": "fdi_outward_position_usd_mn",
        "negative": "observed_negative",
        "zero": "observed_zero",
    })
    panel = universe.merge(evidence, on=KEYS, how="left", validate="one_to_one", indicator="fdi_evidence_merge_status")
    source_period = panel["year"].between(SOURCE_START, SOURCE_END)
    panel["observed"] = panel["observed"].eq(True) & source_period
    panel["observed_negative"] = panel["observed_negative"].eq(True) & panel["observed"]
    panel["observed_zero"] = panel["observed_zero"].eq(True) & panel["observed"]
    panel.loc[~panel["observed"], "fdi_outward_position_usd_mn"] = np.nan

    panel["fdi_evidence_status"] = np.select(
        [
            ~source_period,
            source_period & panel["observed_negative"],
            source_period & panel["observed_zero"],
            source_period & panel["observed"] & panel["fdi_outward_position_usd_mn"].gt(0),
            source_period & ~panel["observed"],
        ],
        [
            "source_year_unavailable",
            "observed_negative_net_position",
            "observed_zero_position",
            "observed_positive_position",
            "official_position_unobserved",
        ],
        default="invalid",
    )

    panel["positive_position_usd_mn"] = np.nan
    panel["log_positive_position"] = np.nan
    panel["log_p95_cap"] = np.nan
    panel["fdi_structural_score_raw"] = np.nan
    scored_parts = []
    for (_, _), group in panel.loc[source_period].groupby(["anchor", "year"], sort=False):
        scored_parts.append(score_anchor_year(group))
    scored = pd.concat(scored_parts, ignore_index=True)
    score_cols = KEYS + ["positive_position_usd_mn", "log_positive_position", "log_p95_cap", "fdi_structural_score_raw"]
    panel = panel.drop(columns=score_cols[3:]).merge(scored[score_cols], on=KEYS, how="left", validate="one_to_one")

    panel["fdi_comparability_status"] = np.select(
        [
            panel["year"].between(SOURCE_START, SOURCE_END) & panel["fdi_structural_score_raw"].notna(),
            panel["year"].between(SOURCE_START, SOURCE_END) & panel["fdi_structural_score_raw"].isna(),
            panel["year"].eq(2025),
            panel["year"].lt(SOURCE_START),
        ],
        [
            "comparable_fdi_source_period_score_available",
            "comparable_fdi_source_period_score_unavailable",
            "provisional_latest_year_source_unavailable",
            "pre_fdi_source_period_unavailable",
        ],
        default="invalid",
    )
    panel["method"] = METHOD
    panel["source"] = SOURCE

    output_cols = [
        "country_iso3", "country_name", "preferred_country_name", "anchor", "year",
        "country_source_name", "fdi_outward_position_usd_mn", "observed",
        "observed_zero", "observed_negative", "fdi_evidence_status",
        "positive_position_usd_mn", "log_positive_position", "log_p95_cap",
        "fdi_structural_score_raw", "fdi_comparability_status", "method", "source",
    ]
    output = panel[output_cols].sort_values(KEYS).reset_index(drop=True)
    validate_panel(output)
    return output, crosswalk_audit


def validate_panel(panel: pd.DataFrame) -> dict[str, int]:
    source_period = panel["year"].between(SOURCE_START, SOURCE_END)
    failures = {
        "unexpected_rows": int(len(panel) != 8410),
        "unexpected_entities": int(panel["country_iso3"].nunique() != 192),
        "duplicate_keys": int(panel.duplicated(KEYS).sum()),
        "invalid_status": int((panel[["fdi_evidence_status", "fdi_comparability_status"]] == "invalid").any(axis=1).sum()),
        "score_out_of_bounds": int((~panel["fdi_structural_score_raw"].dropna().between(0, 1)).sum()),
        "score_outside_source_period": int(panel.loc[~source_period, "fdi_structural_score_raw"].notna().sum()),
        "score_without_observation": int((panel["fdi_structural_score_raw"].notna() & ~panel["observed"]).sum()),
        "missing_observed_score": int((source_period & panel["observed"] & panel["fdi_structural_score_raw"].isna()).sum()),
        "nonzero_negative_or_zero_score": int(((panel["observed_zero"] | panel["observed_negative"]) & panel["fdi_structural_score_raw"].ne(0)).sum()),
    }
    if any(failures.values()):
        raise ValueError(f"FDI panel validation failed: {failures}")
    return failures


def build_summary(panel: pd.DataFrame) -> dict:
    by_anchor = {}
    for anchor, group in panel.groupby("anchor"):
        source_group = group[group["year"].between(SOURCE_START, SOURCE_END)]
        by_anchor[anchor] = {
            "source_period_rows": int(len(source_group)),
            "observed_positions": int(source_group["observed"].sum()),
            "scored_rows": int(source_group["fdi_structural_score_raw"].notna().sum()),
            "missing_positions": int((~source_group["observed"]).sum()),
            "observed_zero": int(source_group["observed_zero"].sum()),
            "observed_negative": int(source_group["observed_negative"].sum()),
        }
    return {
        "method": METHOD,
        "source": SOURCE,
        "rows": int(len(panel)),
        "entities": int(panel["country_iso3"].nunique()),
        "years": [PROJECT_START, PROJECT_END],
        "comparable_fdi_source_period": [SOURCE_START, SOURCE_END],
        "provisional_extension_year": 2025,
        "evidence_status_counts": {k: int(v) for k, v in panel["fdi_evidence_status"].value_counts().items()},
        "comparability_status_counts": {k: int(v) for k, v in panel["fdi_comparability_status"].value_counts().items()},
        "by_anchor": by_anchor,
        "validation_failures": validate_panel(panel),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidates", type=Path, default=Path("data/interim/fdi/imf_dip_primary_candidates.csv"))
    parser.add_argument("--crosswalk", type=Path, default=Path("outputs/tables/fdi/imf_dip_country_crosswalk_audit.csv"))
    parser.add_argument("--country-master", type=Path, default=Path("outputs/tables/relations_condition/relationship_condition_country_master.csv"))
    parser.add_argument("--output", type=Path, default=Path("data/processed/fdi_structural_ties_country_anchor_year.csv"))
    parser.add_argument("--audit-directory", type=Path, default=Path("outputs/tables/fdi"))
    args = parser.parse_args()
    candidates = pd.read_csv(args.candidates, low_memory=False)
    crosswalk = pd.read_csv(args.crosswalk, low_memory=False)
    master = pd.read_csv(args.country_master, low_memory=False)
    panel, repaired_crosswalk = build_panel(candidates, crosswalk, master)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.audit_directory.mkdir(parents=True, exist_ok=True)
    panel.to_csv(args.output, index=False)
    repaired_crosswalk.to_csv(args.audit_directory / "fdi_country_crosswalk_production_audit.csv", index=False)
    (args.audit_directory / "fdi_structural_ties_summary.json").write_text(json.dumps(build_summary(panel), indent=2) + "\n")
    print(f"Wrote {len(panel):,} rows to {args.output}")


if __name__ == "__main__":
    main()
