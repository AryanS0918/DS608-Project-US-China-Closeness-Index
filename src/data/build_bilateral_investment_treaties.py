"""Build annual bilateral investment treaty ties with China and the United States.

Run from the repository root:
    python -u src/data/build_bilateral_investment_treaties.py

Each annual observation is a year-end institutional snapshot. A treaty is in
force in year y when its entry-into-force date is on or before 31 December y
and its termination date is either missing or after 31 December y. Signed-only
agreements receive partial structural credit; terminated agreements receive no
current score but remain visible through historical flags and counts.
"""
from __future__ import annotations

import argparse
import json
import re
import unicodedata
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

KEYS = ["country_iso3", "anchor", "year"]
METHOD_VERSION = "bit_year_end_v1_signed25_in_force100"
ANCHOR_PARTY_NAMES = {
    "China": {"china"},
    "United States": {"united states", "united states of america"},
}
MULTI_PARTY_COUNTERPARTS = {
    "bleu belgium luxembourg economic union": ["BEL", "LUX"],
}
NAME_ALIASES = {
    "bahamas": "BHS",
    "bolivia plurinational state of": "BOL",
    "brunei darussalam": "BRN",
    "congo": "COG",
    "congo democratic republic of the": "COD",
    "cote d ivoire": "CIV",
    "iran islamic republic of": "IRN",
    "korea dem people s rep of": "PRK",
    "korea republic of": "KOR",
    "lao people s democratic republic": "LAO",
    "malaysia": "MYS",
    "moldova republic of": "MDA",
    "north macedonia": "MKD",
    "russian federation": "RUS",
    "sri lanka": "LKA",
    "syrian arab republic": "SYR",
    "tanzania united republic of": "TZA",
    "turkiye": "TUR",
    "venezuela bolivarian republic of": "VEN",
    "viet nam": "VNM",
}


def normalize_name(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value))
    text = "".join(character for character in text if not unicodedata.combining(character))
    text = text.lower().replace("&", " and ")
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def require_columns(frame: pd.DataFrame, columns: set[str], label: str) -> None:
    missing = columns.difference(frame.columns)
    if missing:
        raise KeyError(f"{label} is missing fields: {sorted(missing)}")


def load_universe(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path, low_memory=False)
    require_columns(
        frame,
        {"country_iso3", "country_name", "historical_entity", "anchor", "year"},
        "Production universe",
    )
    universe = frame[
        ["country_iso3", "country_name", "historical_entity", "anchor", "year"]
    ].drop_duplicates()
    if universe.duplicated(KEYS).any():
        raise ValueError("BIT universe contains duplicate keys")
    return universe.sort_values(KEYS).reset_index(drop=True)


def build_name_map(universe: pd.DataFrame) -> dict[str, str]:
    names = universe[["country_iso3", "country_name"]].drop_duplicates()
    mapping = {
        normalize_name(row.country_name): row.country_iso3
        for row in names.itertuples(index=False)
    }
    for iso3 in names["country_iso3"].dropna().astype(str).unique():
        mapping[normalize_name(iso3)] = iso3
    mapping.update(NAME_ALIASES)
    return mapping


def clean_treaty_sheet(path: Path, anchor: str) -> pd.DataFrame:
    frame = pd.read_excel(path, sheet_name="Treaties", engine="openpyxl")
    required = {
        "No.", "Short title", "Parties", "Type of agreement", "Status",
        "Date of signature", "Date of entry into force", "Date of termination",
        "Type of termination",
    }
    require_columns(frame, required, f"{anchor} BIT workbook")
    frame = frame[frame["No."].notna() & frame["Short title"].notna()].copy()
    frame["anchor"] = anchor
    frame["source_record_id"] = frame["No."].astype(int).astype(str)
    frame["treaty_id"] = (
        anchor.lower().replace(" ", "_")
        + "_bit_"
        + frame["source_record_id"]
    )
    for column in [
        "Date of signature", "Date of entry into force", "Date of termination"
    ]:
        frame[column] = pd.to_datetime(frame[column], errors="coerce")
    if frame["Date of signature"].isna().any():
        raise ValueError(f"{anchor} BIT records contain missing signature dates")
    valid_statuses = {"Signed", "In force", "Terminated"}
    invalid_statuses = sorted(set(frame["Status"].dropna()) - valid_statuses)
    if invalid_statuses:
        raise ValueError(f"Unexpected {anchor} BIT statuses: {invalid_statuses}")
    return frame


def extract_counterparty_names(parties: Any, anchor: str) -> list[str]:
    names = [part.strip() for part in str(parties).split(";") if part.strip()]
    anchor_names = ANCHOR_PARTY_NAMES[anchor]
    counterparties = [name for name in names if normalize_name(name) not in anchor_names]
    if len(counterparties) != 1:
        raise ValueError(
            f"Expected one counterparty for {anchor}; found {counterparties} in {parties!r}"
        )
    return counterparties


def expand_counterparties(
    treaties: pd.DataFrame,
    name_map: dict[str, str],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    expanded_rows: list[dict[str, Any]] = []
    crosswalk_rows: list[dict[str, Any]] = []
    for row in treaties.to_dict("records"):
        source_name = extract_counterparty_names(row["Parties"], row["anchor"])[0]
        normalized = normalize_name(source_name)
        iso3_values = MULTI_PARTY_COUNTERPARTS.get(normalized)
        if iso3_values is None:
            iso3 = name_map.get(normalized)
            iso3_values = [] if iso3 is None else [iso3]
        if not iso3_values:
            raise ValueError(
                f"Unresolved BIT counterparty: {source_name!r} ({row['anchor']})"
            )
        for iso3 in iso3_values:
            expanded = dict(row)
            expanded["counterparty_source_name"] = source_name
            expanded["counterparty_normalized_name"] = normalized
            expanded["country_iso3"] = iso3
            expanded_rows.append(expanded)
            crosswalk_rows.append(
                {
                    "counterparty_source_name": source_name,
                    "counterparty_normalized_name": normalized,
                    "country_iso3": iso3,
                    "anchor": row["anchor"],
                    "multi_country_source_entity": len(iso3_values) > 1,
                }
            )
    expanded = pd.DataFrame(expanded_rows)
    crosswalk = pd.DataFrame(crosswalk_rows).drop_duplicates().sort_values(
        ["anchor", "country_iso3", "counterparty_source_name"]
    )
    return expanded, crosswalk


def classify_treaty_at_year_end(treaty: pd.Series, year_end: pd.Timestamp) -> str:
    signature = treaty["Date of signature"]
    entry = treaty["Date of entry into force"]
    termination = treaty["Date of termination"]

    if signature > year_end:
        return "not_yet_signed"
    if pd.notna(termination) and termination <= year_end:
        return "terminated"
    if pd.notna(entry) and entry <= year_end:
        return "in_force"
    return "signed_not_in_force"


def aggregate_country_anchor_year(
    treaties: pd.DataFrame,
    universe: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    event_rows: list[dict[str, Any]] = []
    for treaty in treaties.to_dict("records"):
        treaty_series = pd.Series(treaty)
        for year in range(int(universe["year"].min()), int(universe["year"].max()) + 1):
            year_end = pd.Timestamp(year=year, month=12, day=31)
            state = classify_treaty_at_year_end(treaty_series, year_end)
            event_rows.append(
                {
                    "country_iso3": treaty["country_iso3"],
                    "anchor": treaty["anchor"],
                    "year": year,
                    "treaty_id": treaty["treaty_id"],
                    "short_title": treaty["Short title"],
                    "source_status": treaty["Status"],
                    "signature_date": treaty["Date of signature"],
                    "entry_into_force_date": treaty["Date of entry into force"],
                    "termination_date": treaty["Date of termination"],
                    "termination_type": treaty["Type of termination"],
                    "year_end_state": state,
                }
            )
    events = pd.DataFrame(event_rows)

    active = events[events["year_end_state"].ne("not_yet_signed")].copy()
    grouped_rows: list[dict[str, Any]] = []
    for key, group in active.groupby(KEYS, sort=False):
        states = set(group["year_end_state"])
        in_force = group[group["year_end_state"].eq("in_force")]
        signed = group[group["year_end_state"].eq("signed_not_in_force")]
        terminated = group[group["year_end_state"].eq("terminated")]
        if not in_force.empty:
            current_state = "in_force"
            current_score = 1.0
        elif not signed.empty:
            current_state = "signed_not_in_force"
            current_score = 0.25
        elif not terminated.empty:
            current_state = "historical_terminated"
            current_score = 0.0
        else:
            current_state = "none"
            current_score = 0.0
        grouped_rows.append(
            {
                "country_iso3": key[0],
                "anchor": key[1],
                "year": key[2],
                "bit_state_year_end": current_state,
                "bit_structural_score_raw": current_score,
                "bit_structural_score_scaled": 100 * current_score,
                "bit_in_force": bool(len(in_force)),
                "bit_signed_not_in_force": bool(len(signed)),
                "bit_terminated_history": bool(len(terminated)),
                "bit_ever_signed": True,
                "bit_ever_in_force": bool(
                    (
                        group["entry_into_force_date"].notna()
                        & (
                            group["entry_into_force_date"]
                            <= pd.Timestamp(key[2], 12, 31)
                        )
                    ).any()
                ),
                "bit_in_force_count": int(len(in_force)),
                "bit_signed_not_in_force_count": int(len(signed)),
                "bit_terminated_count": int(len(terminated)),
                "bit_replacement_overlap": int(len(in_force)) > 1,
                "bit_current_treaty_ids": "|".join(sorted(in_force["treaty_id"].astype(str))),
                "bit_current_treaty_titles": "|".join(sorted(in_force["short_title"].astype(str))),
                "bit_all_year_end_states": "|".join(sorted(states)),
            }
        )
    annual = pd.DataFrame(grouped_rows)
    panel = universe.merge(annual, on=KEYS, how="left", validate="one_to_one")

    boolean_columns = [
        "bit_in_force", "bit_signed_not_in_force", "bit_terminated_history",
        "bit_ever_signed", "bit_ever_in_force", "bit_replacement_overlap",
    ]
    count_columns = [
        "bit_in_force_count", "bit_signed_not_in_force_count", "bit_terminated_count"
    ]
    for column in boolean_columns:
        panel[column] = panel[column].map(
            lambda value: False if pd.isna(value) else bool(value)
        ).astype(bool)
    for column in count_columns:
        panel[column] = pd.to_numeric(panel[column], errors="coerce").fillna(0).astype(int)
    panel["bit_state_year_end"] = panel["bit_state_year_end"].fillna("none")
    panel["bit_structural_score_raw"] = panel["bit_structural_score_raw"].fillna(0.0)
    panel["bit_structural_score_scaled"] = panel["bit_structural_score_scaled"].fillna(0.0)
    for column in ["bit_current_treaty_ids", "bit_current_treaty_titles", "bit_all_year_end_states"]:
        panel[column] = panel[column].fillna("")
    panel["method_version"] = METHOD_VERSION
    return panel.sort_values(KEYS).reset_index(drop=True), events


def validate_panel(panel: pd.DataFrame) -> dict[str, Any]:
    failures = {
        "duplicate_keys": int(panel.duplicated(KEYS).sum()),
        "blank_country_names": int(panel["country_name"].isna().sum()),
        "raw_score_out_of_bounds": int((~panel["bit_structural_score_raw"].between(0, 1)).sum()),
        "scaled_score_out_of_bounds": int((~panel["bit_structural_score_scaled"].between(0, 100)).sum()),
        "in_force_score_mismatch": int((panel["bit_in_force"] & ~panel["bit_structural_score_raw"].eq(1)).sum()),
        "signed_score_mismatch": int((
            ~panel["bit_in_force"]
            & panel["bit_signed_not_in_force"]
            & ~panel["bit_structural_score_raw"].eq(0.25)
        ).sum()),
    }
    nonzero = {key: value for key, value in failures.items() if value}
    if nonzero:
        raise AssertionError(f"BIT panel validation failed: {nonzero}")
    return {
        "rows": int(len(panel)),
        "countries_or_historical_entities": int(panel["country_iso3"].nunique()),
        "years": [int(panel["year"].min()), int(panel["year"].max())],
        "state_counts": panel["bit_state_year_end"].value_counts().to_dict(),
        "anchor_state_counts": {
            f"{anchor}|{state}": int(count)
            for (anchor, state), count in panel.groupby(["anchor", "bit_state_year_end"]).size().items()
        },
        "validation_failures": failures,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--china-workbook", type=Path,
        default=Path("data/sources/relations/Bilateral Investment Treaty with China.xlsx"),
    )
    parser.add_argument(
        "--us-workbook", type=Path,
        default=Path("data/sources/relations/Bilateral Investment Treaty with US.xlsx"),
    )
    parser.add_argument(
        "--universe", type=Path,
        default=Path("data/processed/relationship_condition_country_anchor_year.csv"),
    )
    parser.add_argument(
        "--output", type=Path,
        default=Path("data/processed/bilateral_investment_treaties_country_anchor_year.csv"),
    )
    parser.add_argument(
        "--report-directory", type=Path,
        default=Path("outputs/tables/bilateral_investment_treaties"),
    )
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.report_directory.mkdir(parents=True, exist_ok=True)

    universe = load_universe(args.universe)
    name_map = build_name_map(universe)
    china = clean_treaty_sheet(args.china_workbook, "China")
    us = clean_treaty_sheet(args.us_workbook, "United States")
    treaties = pd.concat([china, us], ignore_index=True)
    expanded, crosswalk = expand_counterparties(treaties, name_map)
    panel, events = aggregate_country_anchor_year(expanded, universe)
    summary = validate_panel(panel)
    summary["treaty_records"] = {
        "China": int(china.shape[0]),
        "United States": int(us.shape[0]),
        "expanded_country_treaty_records": int(expanded.shape[0]),
    }

    panel.to_csv(args.output, index=False)
    events.to_csv(args.report_directory / "bit_treaty_year_states.csv", index=False)
    expanded.to_csv(args.report_directory / "bit_treaty_register_normalized.csv", index=False)
    crosswalk.to_csv(args.report_directory / "bit_counterparty_crosswalk.csv", index=False)
    (args.report_directory / "bit_panel_summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )

    print("=" * 72)
    print("BILATERAL INVESTMENT TREATY PANEL")
    print("=" * 72)
    print(json.dumps(summary, indent=2))
    print("\nProduction output:", args.output)
    print("Reports directory:", args.report_directory)


if __name__ == "__main__":
    main()
