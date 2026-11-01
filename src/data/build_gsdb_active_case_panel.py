"""Build corrected GSDB active-case and sanctions-family panels.

Run from the repository root:
    python -u src/data/build_gsdb_active_case_panel.py

This script:
- converts Stata datetime years to calendar years;
- explodes comma-separated active case-ID sets;
- validates every component ID against the case-level source;
- audits and excludes recognised non-state targets before country aggregation;
- stops on any other unresolved country-side entity;
- preserves sanctions-direction labels and trade-scope flags;
- calculates active, new, and ended case counts;
- excludes sender_mult and target_mult from substantive family breadth;
- treats GSDB-FS as nested detail within the R5 financial family;
- builds factual country-anchor-year panels for 2000-2025;
- compares provisional three-state and four-state sanctions specifications.

The candidate classifications are diagnostics, not final methodology.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

R5_FAMILIES = ["arms", "military", "trade", "financial", "travel", "other"]
FS_SUBCATEGORIES = [
    "fin_asset_freeze",
    "fin_services",
    "fin_aid",
    "fin_investment",
    "fin_other",
    "fin_payment_infra",
]
ANCHOR_ISO = {"USA": "United States", "CHN": "China"}
SEVERITY = {"normal": 0, "strained": 1, "severely_strained": 2}
INVALID_COUNTRY_TOKENS = {"", "NAN", "NONE", "<NA>"}
TRADE_SCOPE_FIELDS = [
    "trade_exp_partial", "trade_exp_complete",
    "trade_imp_partial", "trade_imp_complete",
]
NON_STATE_ENTITY_PATTERNS = (
    re.compile(r"^terrorist organizations?\b", flags=re.IGNORECASE),
)


def calendar_year(series: pd.Series) -> pd.Series:
    if pd.api.types.is_datetime64_any_dtype(series):
        return series.dt.year.astype("Int64")
    numeric = pd.to_numeric(series, errors="coerce")
    if numeric.dropna().between(1800, 2200).all():
        return numeric.astype("Int64")
    parsed = pd.to_datetime(series, errors="coerce")
    return parsed.dt.year.astype("Int64")


def parse_case_ids(value: Any) -> tuple[str, ...]:
    if pd.isna(value):
        return tuple()
    parts = []
    for token in str(value).split(","):
        token = re.sub(r"\.0$", "", token.strip())
        if not token:
            continue
        if not re.fullmatch(r"\d+", token):
            raise ValueError(f"Unexpected case-ID token: {token!r} from {value!r}")
        parts.append(token)
    return tuple(sorted(set(parts), key=int))


def classify_anchor(row: pd.Series) -> tuple[str | None, str | None, str | None]:
    sender = str(row["sanctioning_state_iso3"]).upper().strip()
    target = str(row["sanctioned_state_iso3"]).upper().strip()
    sender_anchor = ANCHOR_ISO.get(sender)
    target_anchor = ANCHOR_ISO.get(target)
    if sender_anchor and target_anchor:
        # Keep the anchor readable and the opposite anchor as an ISO3 key.
        return sender_anchor, target, "anchor_to_anchor"
    if sender_anchor:
        return sender_anchor, target, "anchor_to_country"
    if target_anchor:
        return target_anchor, sender, "country_to_anchor"
    return None, None, None


def normalise_label(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(value).strip().lower()).strip("_")


def trade_scope_flags(value: Any) -> dict[str, bool]:
    text = normalise_label(value)
    return {
        "trade_exp_partial": "exp_part" in text,
        "trade_exp_complete": "exp_compl" in text,
        "trade_imp_partial": "imp_part" in text,
        "trade_imp_complete": "imp_compl" in text,
    }


def find_trade_description(columns: list[str]) -> str:
    candidates = {normalise_label(c): c for c in columns}
    for name in ["descr_trade", "trade_description", "trade_desc"]:
        key = normalise_label(name)
        if key in candidates:
            return candidates[key]
    raise KeyError(f"Could not identify trade-description field. Columns: {columns}")


def valid_iso3(series: pd.Series) -> pd.Series:
    cleaned = series.astype("string").str.strip().str.upper()
    return (
        cleaned.str.fullmatch(r"[A-Z]{3}", na=False)
        & ~cleaned.isin(INVALID_COUNTRY_TOKENS)
    )


def classify_excluded_entity(entity_name: Any) -> str:
    if pd.isna(entity_name):
        return "unresolved_country_side_entity"
    cleaned = str(entity_name).strip()
    if any(pattern.search(cleaned) for pattern in NON_STATE_ENTITY_PATTERNS):
        return "non_state_sanctions_target"
    return "unresolved_country_side_entity"


def audit_and_filter_country_dyads(
    case: pd.DataFrame,
    dyad: pd.DataFrame,
    dataset: str,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    country_valid = valid_iso3(dyad["country"])
    invalid = dyad.loc[~country_valid].copy()
    output_columns = [
        "dataset", "year", "anchor", "sanctions_direction",
        "sanctioning_state_iso3", "sanctioned_state_iso3",
        "underlying_case_id", "country_side_entity",
        "sanctioning_state", "sanctioned_state",
        "begin_year", "end_year", "exclusion_reason",
    ]
    if invalid.empty:
        return dyad.copy(), pd.DataFrame(columns=output_columns)

    audit = invalid[
        [
            "dataset", "year", "anchor", "sanctions_direction",
            "sanctioning_state_iso3", "sanctioned_state_iso3",
            "active_case_ids",
        ]
    ].explode("active_case_ids").rename(
        columns={"active_case_ids": "underlying_case_id"}
    )
    audit = audit[audit["underlying_case_id"].notna()].copy()
    audit["underlying_case_id"] = audit["underlying_case_id"].astype(str)

    metadata = [
        "case_id_scalar", "sanctioning_state", "sanctioned_state",
        "begin_year", "end_year",
    ]
    audit = audit.merge(
        case[metadata].drop_duplicates("case_id_scalar"),
        left_on="underlying_case_id",
        right_on="case_id_scalar",
        how="left",
        validate="many_to_one",
    ).drop(columns="case_id_scalar")
    audit["country_side_entity"] = np.where(
        audit["sanctions_direction"].eq("anchor_to_country"),
        audit["sanctioned_state"],
        audit["sanctioning_state"],
    )
    audit["exclusion_reason"] = audit["country_side_entity"].map(
        classify_excluded_entity
    )

    unresolved = audit[
        audit["exclusion_reason"].eq("unresolved_country_side_entity")
    ]
    if not unresolved.empty:
        examples = unresolved[
            [
                "underlying_case_id", "country_side_entity",
                "sanctioning_state_iso3", "sanctioned_state_iso3",
            ]
        ].drop_duplicates().head(10).to_dict("records")
        raise ValueError(
            f"{dataset}: anchor-relevant dyads contain unresolved country-side "
            f"entities. Examples: {examples}"
        )

    filtered = dyad.loc[country_valid].copy()
    filtered["country"] = (
        filtered["country"].astype("string").str.strip().str.upper()
    )
    return (
        filtered,
        audit[output_columns]
        .drop_duplicates()
        .sort_values(["dataset", "year", "anchor", "underlying_case_id"])
        .reset_index(drop=True),
    )


def load_dataset(case_path: Path, dyad_path: Path, name: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    case = pd.read_csv(case_path, low_memory=False)
    dyad = pd.read_stata(dyad_path, convert_categoricals=False)
    case.columns = [str(c).strip() for c in case.columns]
    dyad.columns = [str(c).strip() for c in dyad.columns]
    case["case_id_scalar"] = case["case_id"].map(lambda x: re.sub(r"\.0$", "", str(x).strip()))
    dyad["year"] = calendar_year(dyad["year"])
    dyad["active_case_ids"] = dyad["case_id"].map(parse_case_ids)
    anchors = dyad.apply(classify_anchor, axis=1, result_type="expand")
    anchors.columns = ["anchor", "country", "sanctions_direction"]
    dyad = pd.concat([dyad, anchors], axis=1)
    dyad = dyad[dyad["anchor"].notna()].copy()
    dyad["dataset"] = name
    if name == "R5":
        trade_description = find_trade_description(list(dyad.columns))
        trade_flags = dyad[trade_description].apply(trade_scope_flags).apply(pd.Series)
        dyad = pd.concat([dyad, trade_flags], axis=1)
    return case, dyad


def build_bridge(
    dyad: pd.DataFrame,
    master_valid_ids: set[str],
    dataset_subset_ids: set[str],
    dataset: str,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    base = dyad[
        [
            "dataset", "sanctioning_state_iso3", "sanctioned_state_iso3",
            "anchor", "country", "sanctions_direction", "year", "active_case_ids",
        ]
    ].copy()
    bridge = base.explode("active_case_ids").rename(columns={"active_case_ids": "underlying_case_id"})
    bridge = bridge[bridge["underlying_case_id"].notna()].copy()
    bridge["underlying_case_id"] = bridge["underlying_case_id"].astype(str)
    bridge["case_id_valid_in_r5_master"] = bridge["underlying_case_id"].isin(
        master_valid_ids
    )
    bridge["case_id_in_dataset_subset"] = bridge["underlying_case_id"].isin(
        dataset_subset_ids
    )
    duplicate_bridge_rows = int(
        bridge.duplicated(
            ["sanctioning_state_iso3", "sanctioned_state_iso3", "year", "underlying_case_id"]
        ).sum()
    )
    summary = {
        "dataset": dataset,
        "bridge_rows": int(len(bridge)),
        "bridge_unique_case_ids": int(bridge["underlying_case_id"].nunique()),
        "invalid_against_r5_master_rows": int(
            (~bridge["case_id_valid_in_r5_master"]).sum()
        ),
        "invalid_against_r5_master_unique_ids": int(
            bridge.loc[
                ~bridge["case_id_valid_in_r5_master"], "underlying_case_id"
            ].nunique()
        ),
        "rows_in_dataset_subset": int(bridge["case_id_in_dataset_subset"].sum()),
        "unique_ids_in_dataset_subset": int(
            bridge.loc[
                bridge["case_id_in_dataset_subset"], "underlying_case_id"
            ].nunique()
        ),
        "rows_outside_dataset_subset": int(
            (~bridge["case_id_in_dataset_subset"]).sum()
        ),
        "unique_ids_outside_dataset_subset": int(
            bridge.loc[
                ~bridge["case_id_in_dataset_subset"], "underlying_case_id"
            ].nunique()
        ),
        "duplicate_bridge_rows": duplicate_bridge_rows,
    }
    if summary["invalid_against_r5_master_rows"]:
        invalid = sorted(
            bridge.loc[
                ~bridge["case_id_valid_in_r5_master"], "underlying_case_id"
            ].unique()
        )[:20]
        raise ValueError(
            f"{dataset}: component IDs absent from the R5 master: {invalid}"
        )
    return bridge, summary


def retain_subset_case_ids(
    dyad: pd.DataFrame, subset_ids: set[str]
) -> pd.DataFrame:
    """Retain only IDs belonging to the dataset's case-level subset."""
    result = dyad.copy()
    result["active_case_ids"] = result["active_case_ids"].map(
        lambda values: tuple(case_id for case_id in values if case_id in subset_ids)
    )
    return result


def set_union(series: pd.Series) -> tuple[str, ...]:
    values: set[str] = set()
    for item in series:
        values.update(item)
    return tuple(sorted(values, key=int))


def factual_panel(dyad: pd.DataFrame, families: list[str], prefix: str) -> pd.DataFrame:
    required = [c for c in families if c not in dyad.columns]
    if required:
        raise KeyError(f"Missing {prefix} category fields: {required}")
    aggregations: dict[str, tuple[str, Any]] = {
        "active_case_ids": ("active_case_ids", set_union),
        "active_dyadic_rows": ("year", "size"),
        "active_sanctions_directions": ("sanctions_direction", "nunique"),
        "sanctions_directions": (
            "sanctions_direction",
            lambda values: "|".join(sorted(set(values))),
        ),
    }
    for family in families:
        aggregations[family] = (family, "max")
    for field in TRADE_SCOPE_FIELDS:
        if field in dyad.columns:
            aggregations[field] = (field, "max")
    panel = (
        dyad.groupby(["country", "anchor", "year"], dropna=False)
        .agg(**aggregations)
        .reset_index()
        .sort_values(["country", "anchor", "year"])
    )
    panel["active_case_count"] = panel["active_case_ids"].map(len)
    panel["active_case_ids"] = panel["active_case_ids"].map(lambda x: ",".join(x))
    panel["distinct_category_count"] = panel[families].sum(axis=1).astype("Int64")

    keys = ["country", "anchor"]
    prior_sets: dict[tuple[str, str], set[str]] = {}
    new_counts, ended_counts, new_ids_col, ended_ids_col = [], [], [], []
    previous_year_col = []
    for row in panel.itertuples(index=False):
        group_key = (row.country, row.anchor)
        current = set(parse_case_ids(row.active_case_ids))
        previous = prior_sets.get(group_key, set())
        previous_year = previous_year_col[-1] if False else None
        new = current - previous
        ended = previous - current
        new_counts.append(len(new))
        ended_counts.append(len(ended))
        new_ids_col.append(",".join(sorted(new, key=int)))
        ended_ids_col.append(",".join(sorted(ended, key=int)))
        prior_sets[group_key] = current
    panel["new_case_count"] = new_counts
    panel["ended_case_count"] = ended_counts
    panel["new_case_ids"] = new_ids_col
    panel["ended_case_ids"] = ended_ids_col
    return panel


def add_candidate_states(panel: pd.DataFrame) -> pd.DataFrame:
    result = panel.copy()
    family_count = result["r5_distinct_category_count"].fillna(0)
    financial_detail = result["fs_distinct_category_count"].fillna(0)
    active_any = result["r5_active_case_count"].fillna(0).gt(0)

    # Three-state diagnostic: no sanctions, sanctions, broad sanctions.
    result["sanctions_state_three"] = np.select(
        [
            ~active_any,
            family_count.ge(2) | financial_detail.ge(3),
        ],
        ["normal", "severely_strained"],
        default="strained",
    )

    # Four-state candidate retains the same three sanctions-identifiable levels.
    # Rupture is deliberately unavailable from sanctions alone.
    result["sanctions_state_four_candidate"] = result["sanctions_state_three"]
    result["sanctions_identifies_rupture"] = False
    result["sanctions_severity"] = result["sanctions_state_three"].map(SEVERITY)
    result["broad_combination_flag"] = (
        result.get("r5_trade", 0).fillna(0).eq(1)
        & result.get("r5_financial", 0).fillna(0).eq(1)
    )
    result["security_plus_other_flag"] = (
        (
            result.get("r5_arms", 0).fillna(0).eq(1)
            | result.get("r5_military", 0).fillna(0).eq(1)
        )
        & family_count.ge(2)
    )
    return result


def prefix_panel(panel: pd.DataFrame, prefix: str) -> pd.DataFrame:
    return panel.rename(
        columns={c: f"{prefix}_{c}" for c in panel.columns if c not in {"country", "anchor", "year"}}
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--r5-case", type=Path, default=Path("data/raw/relations/gsdb/r5/GSDB-R5.csv"))
    parser.add_argument("--r5-dyad", type=Path, default=Path("data/raw/relations/gsdb/r5/GSDB-R5_Dyadic.dta"))
    parser.add_argument("--fs-case", type=Path, default=Path("data/raw/relations/gsdb/financial/GSDB-FS.csv"))
    parser.add_argument("--fs-dyad", type=Path, default=Path("data/raw/relations/gsdb/financial/GSDB-FS_Dyadic.dta"))
    parser.add_argument("--output-dir", type=Path, default=Path("outputs/tables/gsdb"))
    parser.add_argument("--start-year", type=int, default=2000)
    parser.add_argument("--end-year", type=int, default=2025)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    r5_case, r5_dyad = load_dataset(args.r5_case, args.r5_dyad, "R5")
    fs_case, fs_dyad = load_dataset(args.fs_case, args.fs_dyad, "FS")
    r5_dyad = r5_dyad[r5_dyad["year"].between(args.start_year, args.end_year)].copy()
    fs_dyad = fs_dyad[fs_dyad["year"].between(args.start_year, args.end_year)].copy()

    r5_dyad, r5_non_country = audit_and_filter_country_dyads(
        r5_case, r5_dyad, "R5"
    )
    fs_dyad, fs_non_country = audit_and_filter_country_dyads(
        fs_case, fs_dyad, "FS"
    )
    non_country_entities = pd.concat(
        [r5_non_country, fs_non_country], ignore_index=True
    ).drop_duplicates()

    if not valid_iso3(r5_dyad["country"]).all():
        raise AssertionError("R5 input contains an invalid country key")
    if not valid_iso3(fs_dyad["country"]).all():
        raise AssertionError("FS input contains an invalid country key")

    r5_master_ids = set(r5_case["case_id_scalar"])
    fs_subset_ids = set(fs_case["case_id_scalar"])
    r5_bridge, r5_bridge_summary = build_bridge(
        r5_dyad, r5_master_ids, r5_master_ids, "R5"
    )
    fs_bridge, fs_bridge_summary = build_bridge(
        fs_dyad, r5_master_ids, fs_subset_ids, "FS"
    )

    # GSDB-FS dyadic case_id lists can include all simultaneously active R5
    # cases for the dyad-year. Restrict the FS active-case stock to IDs that
    # belong to the FS case-level subset before counting financial cases.
    fs_dyad_subset = retain_subset_case_ids(fs_dyad, fs_subset_ids)

    r5_panel = factual_panel(r5_dyad, R5_FAMILIES, "r5")
    fs_panel = factual_panel(fs_dyad_subset, FS_SUBCATEGORIES, "fs")
    combined = prefix_panel(r5_panel, "r5").merge(
        prefix_panel(fs_panel, "fs"),
        on=["country", "anchor", "year"],
        how="outer",
        validate="one_to_one",
    )
    combined = add_candidate_states(combined).sort_values(["year", "anchor", "country"])

    # Validate FS as a nested financial-detail layer for anchor country-years.
    fs_rows = combined[combined["fs_active_case_count"].fillna(0).gt(0)]
    fs_without_r5_financial = int(fs_rows["r5_financial"].fillna(0).ne(1).sum())

    state_frequency = (
        combined.groupby(["year", "anchor", "sanctions_state_three"])
        .size().rename("country_years").reset_index()
    )
    breadth_frequency = (
        combined.groupby(
            ["anchor", "r5_distinct_category_count", "fs_distinct_category_count"],
            dropna=False,
        )
        .size().rename("country_years").reset_index()
    )

    non_country_entities.to_csv(
        args.output_dir / "gsdb_non_country_entities_excluded.csv",
        index=False,
    )
    r5_bridge.to_csv(args.output_dir / "gsdb_r5_dyad_year_case_bridge.csv", index=False)
    fs_bridge.to_csv(args.output_dir / "gsdb_fs_dyad_year_case_bridge.csv", index=False)
    r5_panel.to_csv(args.output_dir / "gsdb_r5_country_anchor_year.csv", index=False)
    fs_panel.to_csv(args.output_dir / "gsdb_fs_country_anchor_year.csv", index=False)
    combined.to_csv(args.output_dir / "gsdb_country_anchor_year_corrected.csv", index=False)
    state_frequency.to_csv(args.output_dir / "gsdb_candidate_state_frequency.csv", index=False)
    breadth_frequency.to_csv(args.output_dir / "gsdb_breadth_frequency.csv", index=False)

    summary = {
        "study_period": [args.start_year, args.end_year],
        "r5": {
            "dyad_rows": int(len(r5_dyad)),
            "country_anchor_years": int(len(r5_panel)),
            "bridge": r5_bridge_summary,
            "active_case_count_max": int(r5_panel["active_case_count"].max()),
            "distinct_family_count_max": int(r5_panel["distinct_category_count"].max()),
        },
        "fs": {
            "dyad_rows": int(len(fs_dyad)),
            "country_anchor_years": int(len(fs_panel)),
            "bridge": fs_bridge_summary,
            "active_case_count_max": int(fs_panel["active_case_count"].max()),
            "distinct_subcategory_count_max": int(fs_panel["distinct_category_count"].max()),
        },
        "non_country_entities": {
            "audit_rows": int(len(non_country_entities)),
            "distinct_case_ids": int(
                non_country_entities["underlying_case_id"].nunique()
            ),
            "exclusion_reasons": (
                non_country_entities["exclusion_reason"].value_counts().to_dict()
            ),
        },
        "combined_country_anchor_years": int(len(combined)),
        "fs_country_years_without_r5_financial_flag": fs_without_r5_financial,
        "candidate_state_counts": combined["sanctions_state_three"].value_counts().to_dict(),
        "rupture_identifiable_from_sanctions_alone": False,
    }
    (args.output_dir / "gsdb_corrected_panel_summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )

    print("=" * 72)
    print("GSDB CORRECTED ACTIVE-CASE PANEL")
    print("=" * 72)
    print(json.dumps(summary, indent=2))
    print("\nCandidate state frequencies for 2021-2025:")
    print(state_frequency[state_frequency["year"] >= 2021].to_string(index=False))
    print("\nOutputs written to:", args.output_dir)


if __name__ == "__main__":
    main()
