"""Build SIPRI arms-transfer scores for the US-China Closeness Index.

The baseline score is the five-year net US-versus-China share of a
recipient's global major-arms imports:

    arms_transfer_score = (US_TIV_5yr - China_TIV_5yr) / Global_TIV_5yr

The script also retains two diagnostics:

    direction_score = (US_TIV_5yr - China_TIV_5yr) /
                      (US_TIV_5yr + China_TIV_5yr)

    anchor_exposure = (US_TIV_5yr + China_TIV_5yr) / Global_TIV_5yr

Thus, where both diagnostics are defined:

    arms_transfer_score = direction_score * anchor_exposure

SIPRI export conventions used here:
- an empty annual cell means no identified delivery and becomes 0;
- a displayed 0 means a positive value below 0.5 million TIV and is
  represented by the midpoint 0.25 in the baseline specification.

The complete 1996-2025 source history is used to calculate rolling values.
The production panel is restricted to 2004-2025 and to entities eligible
under the project's relationship-condition country master.
"""

from __future__ import annotations

import argparse
import json
import re
import unicodedata
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd

SOURCE_START_YEAR = 1996
SOURCE_END_YEAR = 2025
PROJECT_START_YEAR = 2004
PROJECT_END_YEAR = 2025
ROLLING_WINDOW = 5
ROUNDED_ZERO_VALUE = 0.25
LOW_VOLUME_THRESHOLD = 100.0
VOLUME_SENSITIVITY_THRESHOLDS = (25.0, 50.0, 100.0, 250.0)

# Exact source-specific aliases. The project country master remains the
# authority for entity eligibility and preferred names.
SIPRI_NAME_OVERRIDES = {
    "bosnia herzegovina": "BIH",
    "brunei": "BRN",
    "cape verde": "CPV",
    "congo": "COG",
    "cote d ivoire": "CIV",
    "czechia": "CZE",
    "dr congo": "COD",
    "east timor": "TLS",
    "e swatini": "SWZ",
    "eswatini": "SWZ",
    "gambia": "GMB",
    "iran": "IRN",
    "kosovo": "KSV",
    "laos": "LAO",
    "libya": "LBY",
    "macedonia": "MKD",
    "moldova": "MDA",
    "north korea": "PRK",
    "northern cyprus": "XNC",
    "palestine": "PSE",
    "russia": "RUS",
    "serbia and montenegro": "SCG",
    "south korea": "KOR",
    "syria": "SYR",
    "taiwan": "TWN",
    "tanzania": "TZA",
    "turkiye": "TUR",
    "uae": "ARE",
    "uk": "GBR",
    "usa": "USA",
    "venezuela": "VEN",
    "viet nam": "VNM",
    "western sahara": "ESH",
    "yugoslavia": "YUG",
}

VALUE_COLUMNS = ("us_tiv", "china_tiv", "global_tiv")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--us-file", type=Path, default=Path("data/raw/us_transfers.csv"))
    parser.add_argument("--china-file", type=Path, default=Path("data/raw/cn_transfers.csv"))
    parser.add_argument("--global-file", type=Path, default=Path("data/raw/global_transfers.csv"))
    parser.add_argument(
        "--country-master",
        type=Path,
        default=Path(
            "outputs/tables/relations_condition/"
            "relationship_condition_country_master.csv"
        ),
    )
    parser.add_argument(
        "--output-file",
        type=Path,
        default=Path("data/processed/sipri_arms_country_year.csv"),
    )
    parser.add_argument(
        "--audit-dir",
        type=Path,
        default=Path("outputs/tables/security_arms_transfers"),
    )
    return parser.parse_args()


def normalize_name(value: object) -> str:
    text = unicodedata.normalize("NFKD", str(value))
    text = text.encode("ascii", "ignore").decode("ascii").lower()
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def find_header_row(filepath: Path) -> int:
    with filepath.open("r", encoding="utf-8-sig") as handle:
        for row_number, line in enumerate(handle):
            if line.lstrip().startswith("Recipient,"):
                return row_number
    raise ValueError(f"Could not find a Recipient header in {filepath}")


def read_source_metadata(filepath: Path, header_row: int) -> dict[str, object]:
    lines = filepath.read_text(encoding="utf-8-sig").splitlines()[:header_row]
    generated = next(
        (line.split(":", 1)[1].strip() for line in lines if line.startswith("Data generated:")),
        None,
    )
    return {
        "source_file": filepath.as_posix(),
        "data_generated": generated,
        "header_row_zero_based": header_row,
    }


def load_sipri_export(
    filepath: Path,
    value_name: str,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict[str, object]]:
    """Load one SIPRI export and retain value-treatment provenance."""
    if not filepath.exists():
        raise FileNotFoundError(f"Required SIPRI export not found: {filepath}")

    header_row = find_header_row(filepath)
    wide = pd.read_csv(filepath, skiprows=header_row, dtype="string")
    wide.columns = wide.columns.astype(str).str.strip()

    if "Recipient" not in wide.columns:
        raise ValueError(f"Recipient column missing from {filepath}")

    year_columns = [
        str(year)
        for year in range(SOURCE_START_YEAR, SOURCE_END_YEAR + 1)
        if str(year) in wide.columns
    ]
    expected_years = [str(year) for year in range(SOURCE_START_YEAR, SOURCE_END_YEAR + 1)]
    if year_columns != expected_years:
        missing = sorted(set(expected_years) - set(year_columns))
        raise ValueError(f"Missing expected year columns in {filepath}: {missing}")

    long = wide[["Recipient", *year_columns]].melt(
        id_vars="Recipient",
        var_name="year",
        value_name="raw_value",
    )
    long["recipient_source_name"] = long["Recipient"].astype("string").str.strip()
    long["year"] = long["year"].astype(int)

    lower_name = long["recipient_source_name"].str.lower()
    is_nonstate = (
        long["recipient_source_name"].str.endswith("*", na=False)
        | lower_name.str.startswith("total ", na=False)
        | lower_name.str.startswith("unknown recipient", na=False)
    )

    removed = long.loc[is_nonstate, ["recipient_source_name", "year", "raw_value"]].copy()
    removed["source"] = value_name
    removed["removal_reason"] = np.select(
        [
            removed["recipient_source_name"].str.endswith("*", na=False).to_numpy(dtype=bool),
            removed["recipient_source_name"].str.lower().str.startswith("total ", na=False).to_numpy(dtype=bool),
            removed["recipient_source_name"].str.lower().str.startswith("unknown recipient", na=False).to_numpy(dtype=bool),
        ],
        ["source_marked_nonstate", "source_total_row", "unknown_recipient"],
        default="other",
    )

    kept = long.loc[~is_nonstate].copy()
    raw_text = kept["raw_value"].astype("string").str.strip()
    is_blank = raw_text.isna() | raw_text.eq("")
    is_rounded_zero = raw_text.eq("0")
    numeric = pd.to_numeric(raw_text, errors="coerce")
    is_positive_numeric = numeric.notna() & numeric.gt(0)
    is_unexpected = ~(is_blank | is_rounded_zero | is_positive_numeric)

    if is_unexpected.any():
        examples = sorted(raw_text.loc[is_unexpected].dropna().unique().tolist())
        raise ValueError(f"Unexpected SIPRI values in {filepath}: {examples[:20]}")

    kept[value_name] = numeric.astype(float)
    kept.loc[is_blank, value_name] = 0.0
    kept.loc[is_rounded_zero, value_name] = ROUNDED_ZERO_VALUE
    kept["value_treatment"] = np.select(
        [
            is_blank.fillna(False).to_numpy(dtype=bool),
            is_rounded_zero.fillna(False).to_numpy(dtype=bool),
            is_positive_numeric.fillna(False).to_numpy(dtype=bool),
        ],
        ["blank_to_zero", "displayed_zero_to_midpoint", "positive_numeric"],
        default="unexpected",
    )

    treatment_audit = (
        kept.groupby("value_treatment", as_index=False)
        .size()
        .rename(columns={"size": "cell_count"})
    )
    treatment_audit["source"] = value_name
    treatment_audit["rounded_zero_value"] = ROUNDED_ZERO_VALUE

    evidence = kept[
        ["recipient_source_name", "year", value_name, "value_treatment"]
    ].copy()
    metadata = read_source_metadata(filepath, header_row)
    metadata["source"] = value_name
    metadata["recipient_rows_before_removal"] = int(wide.shape[0])
    metadata["recipient_rows_after_removal"] = int(
        kept["recipient_source_name"].nunique()
    )
    return evidence, removed, treatment_audit, metadata


def load_country_master(filepath: Path) -> pd.DataFrame:
    if not filepath.exists():
        raise FileNotFoundError(f"Required country master not found: {filepath}")

    master = pd.read_csv(filepath)
    required = {
        "iso3",
        "country_name",
        "preferred_country_name",
        "baseline_index_eligible",
        "first_valid_year",
        "last_valid_year",
    }
    missing = required - set(master.columns)
    if missing:
        raise ValueError(f"Country master is missing columns: {sorted(missing)}")

    master["iso3"] = master["iso3"].astype("string").str.strip()
    if master["iso3"].duplicated().any():
        duplicates = master.loc[master["iso3"].duplicated(False), "iso3"].tolist()
        raise ValueError(f"Duplicate ISO3 values in country master: {duplicates}")

    master["baseline_index_eligible"] = (
        master["baseline_index_eligible"]
        .astype("string")
        .str.strip()
        .str.lower()
        .map({"true": True, "false": False})
    )
    if master["baseline_index_eligible"].isna().any():
        raise ValueError("Unparseable baseline_index_eligible values in country master")

    return master


def build_mapping_lookup(master: pd.DataFrame) -> tuple[dict[str, str], pd.DataFrame]:
    records: list[dict[str, str]] = []
    for row in master.itertuples(index=False):
        for column in ("country_name", "preferred_country_name"):
            value = getattr(row, column)
            if pd.notna(value):
                records.append(
                    {
                        "normalized_name": normalize_name(value),
                        "source_name": str(value),
                        "iso3": str(row.iso3),
                        "mapping_method": f"country_master_{column}",
                    }
                )

    for source_name, iso3 in SIPRI_NAME_OVERRIDES.items():
        records.append(
            {
                "normalized_name": normalize_name(source_name),
                "source_name": source_name,
                "iso3": iso3,
                "mapping_method": "sipri_name_override",
            }
        )

    mapping = pd.DataFrame(records).drop_duplicates()
    conflicts = (
        mapping.groupby("normalized_name")["iso3"]
        .nunique()
        .loc[lambda series: series > 1]
    )
    if not conflicts.empty:
        raise ValueError(
            "Conflicting country mappings for normalized names: "
            f"{conflicts.index.tolist()}"
        )

    lookup = (
        mapping.drop_duplicates("normalized_name")
        .set_index("normalized_name")["iso3"]
        .to_dict()
    )
    return lookup, mapping


def merge_and_map_sources(
    source_frames: Iterable[pd.DataFrame],
    lookup: dict[str, str],
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    prepared = []
    for source_frame in source_frames:
        value_column = next(column for column in VALUE_COLUMNS if column in source_frame.columns)
        prepared.append(
            source_frame[
                ["recipient_source_name", "year", value_column, "value_treatment"]
            ].rename(columns={"value_treatment": f"{value_column}_treatment"})
        )

    merged = prepared[0]
    for frame in prepared[1:]:
        merged = merged.merge(
            frame,
            on=["recipient_source_name", "year"],
            how="outer",
            validate="one_to_one",
        )

    merged["normalized_recipient_name"] = merged["recipient_source_name"].map(normalize_name)
    merged["iso3"] = merged["normalized_recipient_name"].map(lookup)

    unmapped = (
        merged.loc[merged["iso3"].isna(), ["recipient_source_name", "normalized_recipient_name"]]
        .drop_duplicates()
        .sort_values("recipient_source_name")
    )
    if not unmapped.empty:
        return merged, unmapped, pd.DataFrame()

    name_map_audit = (
        merged[["recipient_source_name", "normalized_recipient_name", "iso3"]]
        .drop_duplicates()
        .sort_values(["iso3", "recipient_source_name"])
    )
    name_map_audit["source_names_per_iso3"] = name_map_audit.groupby("iso3")[
        "recipient_source_name"
    ].transform("nunique")

    for value_column in VALUE_COLUMNS:
        merged[value_column] = merged[value_column].fillna(0.0)
        treatment_column = f"{value_column}_treatment"
        merged[treatment_column] = merged[treatment_column].fillna("recipient_absent_from_export")

    annual = (
        merged.groupby(["iso3", "year"], as_index=False)[list(VALUE_COLUMNS)]
        .sum()
        .sort_values(["iso3", "year"])
    )
    if annual.duplicated(["iso3", "year"]).any():
        raise ValueError("Duplicate ISO3-year rows remain after mapping aggregation")

    return annual, unmapped, name_map_audit


def create_eligible_project_grid(master: pd.DataFrame) -> pd.DataFrame:
    years = pd.DataFrame({"year": range(SOURCE_START_YEAR, SOURCE_END_YEAR + 1)})
    entities = master.loc[master["baseline_index_eligible"]].copy()
    grid = entities.merge(years, how="cross")

    first_year = grid["first_valid_year"].fillna(SOURCE_START_YEAR)
    last_year = grid["last_valid_year"].fillna(SOURCE_END_YEAR)
    valid = grid["year"].between(first_year, last_year)
    return grid.loc[valid].copy()


def add_rolling_measures(panel: pd.DataFrame) -> pd.DataFrame:
    panel = panel.sort_values(["iso3", "year"]).copy()
    for source_column in VALUE_COLUMNS:
        rolling_column = source_column.replace("_tiv", "_tiv_5yr")
        panel[rolling_column] = panel.groupby("iso3")[source_column].transform(
            lambda values: values.rolling(
                window=ROLLING_WINDOW,
                min_periods=ROLLING_WINDOW,
            ).sum()
        )

    panel["window_start_year"] = panel["year"] - ROLLING_WINDOW + 1
    panel["window_end_year"] = panel["year"]
    panel = panel.loc[panel["year"].between(PROJECT_START_YEAR, PROJECT_END_YEAR)].copy()

    panel["anchor_tiv_5yr"] = panel["us_tiv_5yr"] + panel["china_tiv_5yr"]
    net_anchor_tiv = panel["us_tiv_5yr"] - panel["china_tiv_5yr"]

    panel["direction_score"] = np.where(
        panel["anchor_tiv_5yr"] > 0,
        net_anchor_tiv / panel["anchor_tiv_5yr"],
        np.nan,
    )
    panel["anchor_exposure_raw"] = np.where(
        panel["global_tiv_5yr"] > 0,
        panel["anchor_tiv_5yr"] / panel["global_tiv_5yr"],
        np.nan,
    )
    panel["arms_transfer_score"] = np.where(
        panel["global_tiv_5yr"] > 0,
        net_anchor_tiv / panel["global_tiv_5yr"],
        np.nan,
    )

    panel["low_volume_flag"] = pd.Series(pd.NA, index=panel.index, dtype="boolean")
    has_anchor_transfers = panel["anchor_tiv_5yr"] > 0
    panel.loc[has_anchor_transfers, "low_volume_flag"] = (
        panel.loc[has_anchor_transfers, "anchor_tiv_5yr"] < LOW_VOLUME_THRESHOLD
    )

    panel["observation_status"] = "available"
    panel.loc[
        (panel["global_tiv_5yr"] > 0) & (panel["anchor_tiv_5yr"] == 0),
        "observation_status",
    ] = "no_observed_anchor_transfers"
    panel.loc[
        panel["global_tiv_5yr"] == 0,
        "observation_status",
    ] = "no_observed_arms_imports"

    return panel


def validate_panel(panel: pd.DataFrame) -> pd.DataFrame:
    if panel.duplicated(["iso3", "year"]).any():
        raise ValueError("Production panel contains duplicate ISO3-year rows")
    if not panel["year"].between(PROJECT_START_YEAR, PROJECT_END_YEAR).all():
        raise ValueError("Production panel contains years outside the project period")
    if not panel["direction_score"].dropna().between(-1 - 1e-12, 1 + 1e-12).all():
        raise ValueError("Direction score falls outside [-1, 1]")

    available = panel["global_tiv_5yr"] > 0
    score_outside = available & ~panel["arms_transfer_score"].between(
        -1 - 1e-12,
        1 + 1e-12,
    )

    exposure_audit = panel.loc[
        available & (panel["anchor_exposure_raw"] > 1 + 1e-12),
        [
            "iso3",
            "year",
            "us_tiv_5yr",
            "china_tiv_5yr",
            "anchor_tiv_5yr",
            "global_tiv_5yr",
            "anchor_exposure_raw",
            "arms_transfer_score",
        ],
    ].copy()
    exposure_audit["anchor_minus_global_tiv"] = (
        exposure_audit["anchor_tiv_5yr"] - exposure_audit["global_tiv_5yr"]
    )

    if score_outside.any():
        bad = panel.loc[score_outside, ["iso3", "year", "arms_transfer_score"]]
        raise ValueError(
            "Arms-transfer score falls outside [-1, 1]. "
            f"Examples: {bad.head(10).to_dict('records')}"
        )

    identity_rows = panel[
        panel["direction_score"].notna()
        & panel["anchor_exposure_raw"].notna()
    ]
    identity_error = (
        identity_rows["arms_transfer_score"]
        - identity_rows["direction_score"] * identity_rows["anchor_exposure_raw"]
    ).abs()
    if not identity_error.le(1e-10).all():
        raise ValueError("Score identity failed: score != direction * exposure")

    return exposure_audit


def build_sensitivity(panel: pd.DataFrame) -> pd.DataFrame:
    scored = panel.loc[panel["anchor_tiv_5yr"] > 0].copy()
    rows = []
    for threshold in VOLUME_SENSITIVITY_THRESHOLDS:
        flagged = scored["anchor_tiv_5yr"] < threshold
        rows.append(
            {
                "threshold": threshold,
                "scored_country_years": int(len(scored)),
                "flagged_country_years": int(flagged.sum()),
                "flagged_share": float(flagged.mean()) if len(scored) else np.nan,
                "countries_ever_flagged": int(scored.loc[flagged, "iso3"].nunique()),
            }
        )
    return pd.DataFrame(rows)


def main() -> None:
    args = parse_args()
    master = load_country_master(args.country_master)
    lookup, mapping_reference = build_mapping_lookup(master)

    source_specs = [
        (args.us_file, "us_tiv"),
        (args.china_file, "china_tiv"),
        (args.global_file, "global_tiv"),
    ]
    source_frames = []
    removed_frames = []
    treatment_frames = []
    metadata_rows = []

    for filepath, value_name in source_specs:
        evidence, removed, treatment, metadata = load_sipri_export(filepath, value_name)
        source_frames.append(evidence)
        removed_frames.append(removed)
        treatment_frames.append(treatment)
        metadata_rows.append(metadata)

    annual_source, unmapped, mapping_audit = merge_and_map_sources(source_frames, lookup)

    args.audit_dir.mkdir(parents=True, exist_ok=True)
    if not unmapped.empty:
        unmapped.to_csv(args.audit_dir / "sipri_unmapped_names_audit.csv", index=False)
        raise ValueError(
            f"{len(unmapped)} SIPRI recipient names are unmapped. "
            f"See {args.audit_dir / 'sipri_unmapped_names_audit.csv'}"
        )

    project_grid = create_eligible_project_grid(master)
    annual_panel = project_grid.merge(
        annual_source,
        on=["iso3", "year"],
        how="left",
        validate="one_to_one",
    )
    for column in VALUE_COLUMNS:
        annual_panel[column] = annual_panel[column].fillna(0.0)

    panel = add_rolling_measures(annual_panel)
    exposure_audit = validate_panel(panel)
    sensitivity = build_sensitivity(panel)

    output_columns = [
        "iso3",
        "preferred_country_name",
        "year",
        "window_start_year",
        "window_end_year",
        "us_tiv_5yr",
        "china_tiv_5yr",
        "global_tiv_5yr",
        "anchor_tiv_5yr",
        "direction_score",
        "anchor_exposure_raw",
        "arms_transfer_score",
        "low_volume_flag",
        "observation_status",
    ]

    args.output_file.parent.mkdir(parents=True, exist_ok=True)
    panel[output_columns].to_csv(args.output_file, index=False)

    annual_evidence_columns = [
        "iso3",
        "preferred_country_name",
        "year",
        "us_tiv",
        "china_tiv",
        "global_tiv",
    ]
    annual_panel[annual_evidence_columns].to_csv(
        args.audit_dir / "sipri_annual_evidence.csv",
        index=False,
    )
    pd.concat(removed_frames, ignore_index=True).to_csv(
        args.audit_dir / "sipri_removed_nonstate_audit.csv",
        index=False,
    )
    pd.concat(treatment_frames, ignore_index=True).to_csv(
        args.audit_dir / "sipri_value_treatment_audit.csv",
        index=False,
    )
    mapping_reference.to_csv(
        args.audit_dir / "sipri_mapping_reference.csv",
        index=False,
    )
    mapping_audit.to_csv(
        args.audit_dir / "sipri_source_name_mapping_audit.csv",
        index=False,
    )
    exposure_audit.to_csv(
        args.audit_dir / "sipri_exposure_violation_audit.csv",
        index=False,
    )
    sensitivity.to_csv(
        args.audit_dir / "sipri_volume_threshold_sensitivity.csv",
        index=False,
    )
    pd.DataFrame(metadata_rows).to_csv(
        args.audit_dir / "sipri_source_metadata.csv",
        index=False,
    )

    summary = {
        "source_period": [SOURCE_START_YEAR, SOURCE_END_YEAR],
        "project_period": [PROJECT_START_YEAR, PROJECT_END_YEAR],
        "rolling_window_years": ROLLING_WINDOW,
        "rounded_zero_value": ROUNDED_ZERO_VALUE,
        "baseline_formula": "(us_tiv_5yr - china_tiv_5yr) / global_tiv_5yr",
        "production_rows": int(len(panel)),
        "production_entities": int(panel["iso3"].nunique()),
        "status_counts": {
            str(key): int(value)
            for key, value in panel["observation_status"].value_counts().items()
        },
        "non_null_score_rows": int(panel["arms_transfer_score"].notna().sum()),
        "exposure_violation_rows": int(len(exposure_audit)),
        "low_volume_threshold": LOW_VOLUME_THRESHOLD,
    }
    (args.audit_dir / "sipri_arms_transfers_summary.json").write_text(
        json.dumps(summary, indent=2) + "\n",
        encoding="utf-8",
    )

    print(f"Wrote production panel: {args.output_file}")
    print(f"Wrote audits: {args.audit_dir}")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
