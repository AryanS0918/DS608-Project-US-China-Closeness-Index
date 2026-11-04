"""Tests for the SIPRI arms-transfer processing pipeline."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "src" / "data" / "build_sipri_arms_transfers.py"

spec = importlib.util.spec_from_file_location("build_sipri_arms_transfers", MODULE_PATH)
if spec is None or spec.loader is None:
    raise ImportError(f"Cannot import SIPRI builder from {MODULE_PATH}")
sipri = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = sipri
spec.loader.exec_module(sipri)


def write_sipri_export(path: Path, rows: list[dict[str, object]]) -> None:
    """Write a minimal export with the same preamble and year layout as SIPRI."""
    years = list(range(sipri.SOURCE_START_YEAR, sipri.SOURCE_END_YEAR + 1))
    columns = ["Recipient", *map(str, years), "1996-2025", "Percentage"]
    frame = pd.DataFrame(rows)
    for column in columns:
        if column not in frame.columns:
            frame[column] = ""
    frame = frame[columns]

    preamble = (
        "Volume of transfers of major arms\n"
        "Figures are in millions of SIPRI trend-indicator values (TIVs).\n"
        "A '0' indicates a value below 0.5 million TIV.\n"
        "\n"
        "Source: SIPRI Arms Transfers Database.\n"
        "Data generated: 1 Jan 2026 12:00:00 PM\n"
        "\n"
    )
    path.write_text(preamble, encoding="utf-8")
    frame.to_csv(path, mode="a", index=False)


def make_row(recipient: str, values: dict[int, object]) -> dict[str, object]:
    row: dict[str, object] = {"Recipient": recipient}
    row.update({str(year): value for year, value in values.items()})
    return row


def minimal_master() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "iso3": "AAA",
                "country_name": "Alpha",
                "preferred_country_name": "Alpha",
                "historical_entity": False,
                "first_valid_year": np.nan,
                "last_valid_year": np.nan,
                "entity_type": "sovereign_state",
                "baseline_index_eligible": True,
                "eligibility_rule": "eligible_all_project_years",
                "entity_policy_status": "decided_baseline_inclusion",
                "entity_policy_note": "Synthetic test entity.",
            },
            {
                "iso3": "BBB",
                "country_name": "Beta",
                "preferred_country_name": "Beta",
                "historical_entity": True,
                "first_valid_year": 2004,
                "last_valid_year": 2006,
                "entity_type": "historical_state",
                "baseline_index_eligible": True,
                "eligibility_rule": "eligible_only_within_validity_interval",
                "entity_policy_status": "decided_historical_treatment",
                "entity_policy_note": "Synthetic validity-window entity.",
            },
            {
                "iso3": "CCC",
                "country_name": "Gamma",
                "preferred_country_name": "Gamma",
                "historical_entity": False,
                "first_valid_year": np.nan,
                "last_valid_year": np.nan,
                "entity_type": "special_or_policy_dependent_entity",
                "baseline_index_eligible": False,
                "eligibility_rule": "excluded_from_baseline_index",
                "entity_policy_status": "decided_baseline_exclusion",
                "entity_policy_note": "Synthetic excluded entity.",
            },
        ]
    )


def test_load_export_distinguishes_blank_rounded_zero_and_positive(tmp_path: Path) -> None:
    export = tmp_path / "source.csv"
    write_sipri_export(
        export,
        [make_row("Alpha", {1996: "", 1997: "0", 1998: "12.5"})],
    )

    evidence, removed, treatment, metadata = sipri.load_sipri_export(export, "us_tiv")
    values = evidence.set_index("year")["us_tiv"]

    assert values.loc[1996] == 0.0
    assert values.loc[1997] == sipri.ROUNDED_ZERO_VALUE
    assert values.loc[1998] == 12.5
    assert removed.empty
    assert treatment.set_index("value_treatment").loc["displayed_zero_to_midpoint", "cell_count"] == 1
    assert metadata["data_generated"] == "1 Jan 2026 12:00:00 PM"


def test_load_export_removes_source_marked_nonstates_and_totals(tmp_path: Path) -> None:
    export = tmp_path / "source.csv"
    write_sipri_export(
        export,
        [
            make_row("Alpha", {2000: 1}),
            make_row("Armed group*", {2000: 2}),
            make_row("Total imports from Test", {2000: 3}),
            make_row("unknown recipient(s)", {2000: 4}),
        ],
    )

    evidence, removed, _, _ = sipri.load_sipri_export(export, "us_tiv")

    assert set(evidence["recipient_source_name"].unique()) == {"Alpha"}
    assert set(removed["removal_reason"].unique()) == {
        "source_marked_nonstate",
        "source_total_row",
        "unknown_recipient",
    }


def test_mapping_uses_country_master_and_explicit_overrides() -> None:
    master = minimal_master()
    lookup, reference = sipri.build_mapping_lookup(master)

    assert lookup[sipri.normalize_name("Alpha")] == "AAA"
    assert lookup[sipri.normalize_name("Congo")] == "COG"
    assert "sipri_name_override" in set(reference["mapping_method"])


def test_mapping_aggregates_multiple_source_names_to_one_iso3() -> None:
    master = pd.DataFrame(
        [
            {
                "iso3": "SWZ",
                "country_name": "eSwatini",
                "preferred_country_name": "Eswatini",
            }
        ]
    )
    lookup, _ = sipri.build_mapping_lookup(master)

    def frame(column: str, first: float, second: float) -> pd.DataFrame:
        return pd.DataFrame(
            {
                "recipient_source_name": ["eSwatini", "Eswatini"],
                "year": [2004, 2004],
                column: [first, second],
                "value_treatment": ["positive_numeric", "positive_numeric"],
            }
        )

    annual, unmapped, audit = sipri.merge_and_map_sources(
        [
            frame("us_tiv", 1.0, 2.0),
            frame("china_tiv", 3.0, 4.0),
            frame("global_tiv", 5.0, 6.0),
        ],
        lookup,
    )

    assert unmapped.empty
    row = annual.iloc[0]
    assert row["us_tiv"] == 3.0
    assert row["china_tiv"] == 7.0
    assert row["global_tiv"] == 11.0
    assert audit["source_names_per_iso3"].max() == 2


def test_project_grid_applies_eligibility_and_validity_intervals() -> None:
    grid = sipri.create_eligible_project_grid(minimal_master())

    assert set(grid["iso3"]) == {"AAA", "BBB"}
    beta_years = grid.loc[grid["iso3"] == "BBB", "year"].tolist()
    assert beta_years == [2004, 2005, 2006]
    assert "CCC" not in set(grid["iso3"])


def test_rolling_scores_and_statuses_match_agreed_method() -> None:
    years = list(range(1996, 2026))
    rows = []
    for year in years:
        rows.append(
            {
                "iso3": "AAA",
                "preferred_country_name": "Alpha",
                "year": year,
                "us_tiv": 10.0 if 2000 <= year <= 2004 else 0.0,
                "china_tiv": 5.0 if 2000 <= year <= 2004 else 0.0,
                "global_tiv": 25.0 if 2000 <= year <= 2004 else 0.0,
            }
        )
    panel = sipri.add_rolling_measures(pd.DataFrame(rows))
    row_2004 = panel.loc[panel["year"] == 2004].iloc[0]

    assert row_2004["us_tiv_5yr"] == 50.0
    assert row_2004["china_tiv_5yr"] == 25.0
    assert row_2004["global_tiv_5yr"] == 125.0
    assert row_2004["direction_score"] == pytest.approx(1 / 3)
    assert row_2004["anchor_exposure_raw"] == pytest.approx(0.6)
    assert row_2004["arms_transfer_score"] == pytest.approx(0.2)
    assert row_2004["arms_transfer_score"] == pytest.approx(
        row_2004["direction_score"] * row_2004["anchor_exposure_raw"]
    )

    row_2009 = panel.loc[panel["year"] == 2009].iloc[0]
    assert row_2009["observation_status"] == "no_observed_arms_imports"
    assert pd.isna(row_2009["arms_transfer_score"])


def test_imports_without_anchor_transfers_receive_zero_score() -> None:
    years = list(range(1996, 2026))
    annual = pd.DataFrame(
        {
            "iso3": "AAA",
            "preferred_country_name": "Alpha",
            "year": years,
            "us_tiv": 0.0,
            "china_tiv": 0.0,
            "global_tiv": 10.0,
        }
    )
    panel = sipri.add_rolling_measures(annual)

    assert (panel["arms_transfer_score"] == 0.0).all()
    assert panel["direction_score"].isna().all()
    assert (panel["anchor_exposure_raw"] == 0.0).all()
    assert set(panel["observation_status"]) == {"no_observed_anchor_transfers"}
    assert panel["low_volume_flag"].isna().all()


def test_validate_panel_rejects_out_of_bounds_scores() -> None:
    panel = pd.DataFrame(
        {
            "iso3": ["AAA"],
            "year": [2004],
            "us_tiv_5yr": [12.0],
            "china_tiv_5yr": [0.0],
            "anchor_tiv_5yr": [12.0],
            "global_tiv_5yr": [10.0],
            "direction_score": [1.0],
            "anchor_exposure_raw": [1.2],
            "arms_transfer_score": [1.2],
        }
    )

    with pytest.raises(ValueError, match="outside"):
        sipri.validate_panel(panel)
