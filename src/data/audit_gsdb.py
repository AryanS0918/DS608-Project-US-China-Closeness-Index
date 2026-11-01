"""Audit GSDB-R5 and GSDB-FS for reproducible US/China relationship analysis.

Complete runnable example.

Run from the repository root:
    python -u src/data/audit_gsdb.py

This audit does not assign relationship-condition states. It inventories schemas,
keys, case-to-dyad relationships, anchor coverage, category distributions, and a
factual country-anchor-year preview. It writes no source descriptions or raw rows.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

DEFAULT_R5_CASE = Path("data/raw/relations/gsdb/r5/GSDB-R5.csv")
DEFAULT_R5_DYAD = Path("data/raw/relations/gsdb/r5/GSDB-R5_Dyadic.dta")
DEFAULT_FS_CASE = Path("data/raw/relations/gsdb/financial/GSDB-FS.csv")
DEFAULT_FS_DYAD = Path("data/raw/relations/gsdb/financial/GSDB-FS_Dyadic.dta")
DEFAULT_OUTPUT = Path("outputs/tables/gsdb")

ANCHOR_ISO = {"USA": "United States", "CHN": "China"}
ANCHOR_NAMES = {
    "unitedstates": "United States",
    "unitedstatesofamerica": "United States",
    "usa": "United States",
    "us": "United States",
    "china": "China",
    "peoplesrepublicofchina": "China",
    "prc": "China",
}


def norm(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value).strip().lower())


def read_csv(path: Path) -> pd.DataFrame:
    try:
        return pd.read_csv(path, low_memory=False)
    except UnicodeDecodeError:
        return pd.read_csv(path, low_memory=False, encoding="latin-1")


def read_dta(path: Path) -> pd.DataFrame:
    return pd.read_stata(path, convert_categoricals=False)


def find_column(
    columns: list[str], candidates: list[str], *, required: bool = True
) -> str | None:
    lookup = {norm(c): c for c in columns}
    for candidate in candidates:
        if norm(candidate) in lookup:
            return lookup[norm(candidate)]
    if required:
        raise KeyError(
            f"Could not identify any of {candidates}. Available columns: {columns}"
        )
    return None


def identify_dyad_columns(frame: pd.DataFrame) -> dict[str, str | None]:
    columns = [str(c) for c in frame.columns]
    return {
        "case_id": find_column(columns, ["case_id", "caseid", "case"], required=False),
        "year": find_column(columns, ["year", "sanction_year"], required=False),
        "sender_iso": find_column(
            columns,
            [
                "sanctioning_state_iso3", "sender_iso3", "sender_iso", "sanctioner_iso3",
                "iso3_o", "iso_o", "origin_iso3",
            ],
            required=False,
        ),
        "target_iso": find_column(
            columns,
            [
                "sanctioned_state_iso3", "target_iso3", "target_iso", "sanctionee_iso3",
                "iso3_d", "iso_d", "destination_iso3",
            ],
            required=False,
        ),
        "sender_name": find_column(
            columns,
            ["sanctioning_state", "sender", "sanctioner", "origin", "sender_name"],
            required=False,
        ),
        "target_name": find_column(
            columns,
            ["sanctioned_state", "target", "sanctionee", "destination", "target_name"],
            required=False,
        ),
    }


def identify_case_columns(frame: pd.DataFrame) -> dict[str, str | None]:
    columns = [str(c) for c in frame.columns]
    return {
        "case_id": find_column(columns, ["case_id", "caseid", "case"], required=False),
        "begin_year": find_column(
            columns, ["begin_year", "start_year", "year_start", "beginyear"], required=False
        ),
        "end_year": find_column(
            columns, ["end_year", "termination_year", "year_end", "endyear"], required=False
        ),
        "sender": find_column(
            columns, ["sanctioning_state", "sender", "sanctioner"], required=False
        ),
        "target": find_column(
            columns, ["sanctioned_state", "target", "sanctionee"], required=False
        ),
    }


def schema_rows(frame: pd.DataFrame, dataset: str, level: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for column in frame.columns:
        series = frame[column]
        rows.append(
            {
                "dataset": dataset,
                "level": level,
                "column": str(column),
                "dtype": str(series.dtype),
                "rows": int(len(series)),
                "non_missing": int(series.notna().sum()),
                "missing": int(series.isna().sum()),
                "missing_pct": round(float(series.isna().mean() * 100), 4),
                "unique_non_missing": int(series.nunique(dropna=True)),
            }
        )
    return rows


def binary_columns(frame: pd.DataFrame, excluded: set[str]) -> list[str]:
    result: list[str] = []
    for column in frame.columns:
        if column in excluded:
            continue
        values = set(pd.to_numeric(frame[column], errors="coerce").dropna().unique().tolist())
        if values and values.issubset({0, 1}):
            result.append(str(column))
    return result


def anchor_from_row(row: pd.Series, columns: dict[str, str | None]) -> tuple[str | None, str | None, str | None]:
    sender_iso_col, target_iso_col = columns["sender_iso"], columns["target_iso"]
    sender_name_col, target_name_col = columns["sender_name"], columns["target_name"]

    sender_iso = str(row[sender_iso_col]).upper().strip() if sender_iso_col and pd.notna(row[sender_iso_col]) else None
    target_iso = str(row[target_iso_col]).upper().strip() if target_iso_col and pd.notna(row[target_iso_col]) else None
    sender_name = str(row[sender_name_col]).strip() if sender_name_col and pd.notna(row[sender_name_col]) else None
    target_name = str(row[target_name_col]).strip() if target_name_col and pd.notna(row[target_name_col]) else None

    sender_anchor = ANCHOR_ISO.get(sender_iso) or ANCHOR_NAMES.get(norm(sender_name))
    target_anchor = ANCHOR_ISO.get(target_iso) or ANCHOR_NAMES.get(norm(target_name))

    if sender_anchor and target_anchor:
        return sender_anchor, target_anchor, "anchor_to_anchor"
    if sender_anchor:
        country = target_iso or target_name
        return sender_anchor, country, "anchor_to_country"
    if target_anchor:
        country = sender_iso or sender_name
        return target_anchor, country, "country_to_anchor"
    return None, None, None


def key_audit(
    frame: pd.DataFrame,
    dataset: str,
    level: str,
    candidates: list[list[str]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for columns in candidates:
        valid = [c for c in columns if c and c in frame.columns]
        if len(valid) != len(columns) or not valid:
            continue
        subset = frame[valid]
        rows.append(
            {
                "dataset": dataset,
                "level": level,
                "candidate_key": " + ".join(valid),
                "rows": int(len(frame)),
                "missing_key_rows": int(subset.isna().any(axis=1).sum()),
                "duplicate_key_rows": int(subset.duplicated(keep=False).sum()),
                "unique_key_values": int(subset.drop_duplicates().shape[0]),
                "is_unique_complete_key": bool(
                    not subset.isna().any(axis=1).any() and not subset.duplicated().any()
                ),
            }
        )
    return rows


def audit_dataset(
    name: str,
    case_frame: pd.DataFrame,
    dyad_frame: pd.DataFrame,
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]], pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    case_frame = case_frame.copy()
    dyad_frame = dyad_frame.copy()
    case_frame.columns = [str(c).strip() for c in case_frame.columns]
    dyad_frame.columns = [str(c).strip() for c in dyad_frame.columns]

    case_cols = identify_case_columns(case_frame)
    dyad_cols = identify_dyad_columns(dyad_frame)
    if not dyad_cols["year"]:
        raise KeyError(f"{name} dyadic data has no identifiable year column")
    if not (dyad_cols["sender_iso"] or dyad_cols["sender_name"]):
        raise KeyError(f"{name} dyadic data has no identifiable sender field")
    if not (dyad_cols["target_iso"] or dyad_cols["target_name"]):
        raise KeyError(f"{name} dyadic data has no identifiable target field")

    year_col = dyad_cols["year"]
    dyad_frame[year_col] = pd.to_numeric(dyad_frame[year_col], errors="coerce").astype("Int64")

    anchors = dyad_frame.apply(lambda row: anchor_from_row(row, dyad_cols), axis=1, result_type="expand")
    anchors.columns = ["anchor", "country", "sanctions_direction"]
    anchor_rows = pd.concat([dyad_frame, anchors], axis=1)
    anchor_rows = anchor_rows[anchor_rows["anchor"].notna()].copy()

    id_exclusions = {c for c in dyad_cols.values() if c}
    categories = binary_columns(dyad_frame, id_exclusions)

    yearly_keys = ["country", "anchor", year_col]
    aggregate_spec: dict[str, tuple[str, str]] = {
        "active_dyadic_rows": (year_col, "size"),
    }
    if dyad_cols["case_id"]:
        aggregate_spec["active_case_count"] = (dyad_cols["case_id"], "nunique")
    for category in categories:
        aggregate_spec[f"category_{category}"] = (category, "max")

    country_year = (
        anchor_rows.groupby(yearly_keys, dropna=False)
        .agg(**aggregate_spec)
        .reset_index()
        .rename(columns={year_col: "year"})
    )
    category_cols = [c for c in country_year.columns if c.startswith("category_")]
    if category_cols:
        country_year["distinct_active_category_count"] = country_year[category_cols].sum(axis=1)
    else:
        country_year["distinct_active_category_count"] = 0

    coverage = (
        anchor_rows.groupby(["anchor", "sanctions_direction", year_col], dropna=False)
        .agg(
            dyadic_rows=(year_col, "size"),
            countries=("country", "nunique"),
            cases=(dyad_cols["case_id"], "nunique") if dyad_cols["case_id"] else (year_col, "size"),
        )
        .reset_index()
        .rename(columns={year_col: "year"})
    )

    category_profile_rows: list[dict[str, Any]] = []
    for category in categories:
        values = pd.to_numeric(anchor_rows[category], errors="coerce").fillna(0)
        category_profile_rows.append(
            {
                "dataset": name,
                "category": category,
                "anchor_rows_active": int(values.eq(1).sum()),
                "anchor_cases_active": int(
                    anchor_rows.loc[values.eq(1), dyad_cols["case_id"]].nunique()
                ) if dyad_cols["case_id"] else None,
                "country_anchor_years_active": int(
                    country_year[f"category_{category}"].eq(1).sum()
                ),
            }
        )
    category_profile = pd.DataFrame(category_profile_rows)

    case_id_case = case_cols["case_id"]
    case_id_dyad = dyad_cols["case_id"]
    merge_audit = {
        "dataset": name,
        "case_rows": int(len(case_frame)),
        "dyad_rows": int(len(dyad_frame)),
        "case_id_case_column": case_id_case,
        "case_id_dyad_column": case_id_dyad,
        "case_id_unique_case_level": bool(case_id_case and case_frame[case_id_case].is_unique),
        "case_ids_case_level": int(case_frame[case_id_case].nunique()) if case_id_case else None,
        "case_ids_dyad_level": int(dyad_frame[case_id_dyad].nunique()) if case_id_dyad else None,
        "dyad_case_ids_missing_from_case": int(
            len(set(dyad_frame[case_id_dyad].dropna()) - set(case_frame[case_id_case].dropna()))
        ) if case_id_case and case_id_dyad else None,
        "case_ids_without_dyad_rows": int(
            len(set(case_frame[case_id_case].dropna()) - set(dyad_frame[case_id_dyad].dropna()))
        ) if case_id_case and case_id_dyad else None,
    }

    keys: list[dict[str, Any]] = []
    keys.extend(key_audit(case_frame, name, "case", [[case_id_case]]))
    keys.extend(
        key_audit(
            dyad_frame,
            name,
            "dyadic",
            [
                [case_id_dyad],
                [case_id_dyad, dyad_cols["sender_iso"], dyad_cols["target_iso"], year_col],
                [case_id_dyad, dyad_cols["sender_name"], dyad_cols["target_name"], year_col],
                [dyad_cols["sender_iso"], dyad_cols["target_iso"], year_col],
            ],
        )
    )

    summary = {
        "dataset": name,
        "case_rows": int(len(case_frame)),
        "case_columns": int(len(case_frame.columns)),
        "dyad_rows": int(len(dyad_frame)),
        "dyad_columns": int(len(dyad_frame.columns)),
        "year_min": int(dyad_frame[year_col].min()),
        "year_max": int(dyad_frame[year_col].max()),
        "anchor_rows": int(len(anchor_rows)),
        "anchor_countries": int(anchor_rows["country"].nunique()),
        "country_anchor_years": int(len(country_year)),
        "binary_category_columns": categories,
        "identified_case_columns": case_cols,
        "identified_dyad_columns": dyad_cols,
        "merge_audit": merge_audit,
    }
    schemas = schema_rows(case_frame, name, "case") + schema_rows(dyad_frame, name, "dyadic")
    return summary, schemas, keys, coverage, category_profile, country_year


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--r5-case", type=Path, default=DEFAULT_R5_CASE)
    parser.add_argument("--r5-dyad", type=Path, default=DEFAULT_R5_DYAD)
    parser.add_argument("--fs-case", type=Path, default=DEFAULT_FS_CASE)
    parser.add_argument("--fs-dyad", type=Path, default=DEFAULT_FS_DYAD)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    inputs = {
        "R5": (read_csv(args.r5_case), read_dta(args.r5_dyad)),
        "FS": (read_csv(args.fs_case), read_dta(args.fs_dyad)),
    }

    summaries: dict[str, Any] = {}
    schemas: list[dict[str, Any]] = []
    keys: list[dict[str, Any]] = []
    coverages: list[pd.DataFrame] = []
    profiles: list[pd.DataFrame] = []
    panels: dict[str, pd.DataFrame] = {}

    for name, (case_frame, dyad_frame) in inputs.items():
        print(f"Auditing GSDB-{name}...")
        summary, schema, key_rows, coverage, profile, panel = audit_dataset(
            name, case_frame, dyad_frame
        )
        summaries[name] = summary
        schemas.extend(schema)
        keys.extend(key_rows)
        coverage.insert(0, "dataset", name)
        coverages.append(coverage)
        profiles.append(profile)
        panels[name] = panel

    # Test case-level one-to-one compatibility exactly as documented.
    r5_case, fs_case = inputs["R5"][0], inputs["FS"][0]
    r5_case_id = summaries["R5"]["identified_case_columns"]["case_id"]
    fs_case_id = summaries["FS"]["identified_case_columns"]["case_id"]
    r5_ids = set(r5_case[r5_case_id].dropna()) if r5_case_id else set()
    fs_ids = set(fs_case[fs_case_id].dropna()) if fs_case_id else set()
    compatibility = {
        "r5_case_ids": len(r5_ids),
        "fs_case_ids": len(fs_ids),
        "shared_case_ids": len(r5_ids & fs_ids),
        "fs_ids_not_in_r5": len(fs_ids - r5_ids),
        "r5_ids_not_in_fs": len(r5_ids - fs_ids),
        "fs_is_subset_of_r5": fs_ids.issubset(r5_ids),
    }

    # Merge factual country-anchor-year aggregates without assigning severity.
    r5_panel = panels["R5"].copy()
    fs_panel = panels["FS"].copy()
    r5_panel = r5_panel.rename(
        columns={c: f"r5_{c}" for c in r5_panel.columns if c not in {"country", "anchor", "year"}}
    )
    fs_panel = fs_panel.rename(
        columns={c: f"fs_{c}" for c in fs_panel.columns if c not in {"country", "anchor", "year"}}
    )
    combined = r5_panel.merge(
        fs_panel, on=["country", "anchor", "year"], how="outer", validate="one_to_one"
    ).sort_values(["year", "anchor", "country"])

    pd.DataFrame(schemas).to_csv(args.output_dir / "gsdb_schema.csv", index=False)
    pd.DataFrame(keys).to_csv(args.output_dir / "gsdb_key_audit.csv", index=False)
    pd.concat(coverages, ignore_index=True).to_csv(
        args.output_dir / "gsdb_anchor_coverage.csv", index=False
    )
    pd.concat(profiles, ignore_index=True).to_csv(
        args.output_dir / "gsdb_anchor_category_profiles.csv", index=False
    )
    pd.DataFrame(
        [summaries["R5"]["merge_audit"], summaries["FS"]["merge_audit"], {"dataset": "R5-FS compatibility", **compatibility}]
    ).to_csv(args.output_dir / "gsdb_case_dyad_merge_audit.csv", index=False)
    combined.to_csv(args.output_dir / "gsdb_country_anchor_year_preview.csv", index=False)

    final_summary = {"datasets": summaries, "case_level_compatibility": compatibility}
    (args.output_dir / "gsdb_audit_summary.json").write_text(
        json.dumps(final_summary, indent=2, ensure_ascii=False, default=str), encoding="utf-8"
    )

    print("=" * 72)
    print("GSDB AUDIT SUMMARY")
    print("=" * 72)
    print(json.dumps(final_summary, indent=2, ensure_ascii=False, default=str))
    print("\nCombined factual panel rows:", len(combined))
    print("Outputs written to:", args.output_dir.resolve())


if __name__ == "__main__":
    main()
