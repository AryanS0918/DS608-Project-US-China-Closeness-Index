import numpy as np
import pandas as pd

from src.data.build_fdi_structural_ties import (
    KEYS,
    build_panel,
    score_anchor_year,
    validate_panel,
)


def test_score_anchor_year_preserves_missing_and_nonpositive_values():
    group = pd.DataFrame(
        {
            "country_iso3": ["AAA", "BBB", "CCC", "DDD"],
            "country_name": ["A", "B", "C", "D"],
            "anchor": ["China"] * 4,
            "year": [2024] * 4,
            "fdi_outward_position_usd_mn": [100.0, 0.0, -5.0, np.nan],
            "observed": [True, True, True, False],
            "observed_zero": [False, True, False, False],
            "observed_negative": [False, False, True, False],
            "positive_position_usd_mn": [100.0, 0.0, 0.0, np.nan],
        }
    )
    scored = score_anchor_year(group)
    assert scored.loc[0, "fdi_structural_score_raw"] == 1.0
    assert scored.loc[1, "fdi_structural_score_raw"] == 0.0
    assert scored.loc[2, "fdi_structural_score_raw"] == 0.0
    assert pd.isna(scored.loc[3, "fdi_structural_score_raw"])


def test_build_panel_has_expected_grid_and_anchor_self_exclusions():
    master = pd.DataFrame(
        {
            "iso3": ["AAA", "CHN", "USA"],
            "country_name": ["A", "China", "United States"],
            "historical_entity": [False, False, False],
        }
    )
    crosswalk = pd.DataFrame(
        {
            "country_source_name": ["A"],
            "country_iso3": ["AAA"],
            "country_name": ["A"],
            "dip_period_eligible": [True],
        }
    )
    rows = []
    for year in range(2018, 2025):
        rows.extend(
            [
                {
                    "country_source_name": "A",
                    "anchor": "China",
                    "reporting_perspective": "anchor_report",
                    "economic_direction": "anchor_to_country",
                    "DV_TYPE": "Reported official data",
                    "year": year,
                    "fdi_position_usd_millions": 10.0,
                },
                {
                    "country_source_name": "A",
                    "anchor": "United States",
                    "reporting_perspective": "anchor_report",
                    "economic_direction": "anchor_to_country",
                    "DV_TYPE": "Reported official data",
                    "year": year,
                    "fdi_position_usd_millions": 20.0,
                },
            ]
        )
    candidates = pd.DataFrame(rows)
    panel = build_panel(candidates, crosswalk, master)
    assert not panel.duplicated(KEYS).any()
    assert not ((panel["country_iso3"] == "CHN") & (panel["anchor"] == "China")).any()
    assert not ((panel["country_iso3"] == "USA") & (panel["anchor"] == "United States")).any()
    validate_panel(panel)


def test_negative_position_scores_zero():
    group = pd.DataFrame(
        {
            "country_iso3": ["AAA", "BBB"],
            "anchor": ["United States", "United States"],
            "year": [2024, 2024],
            "observed": [True, True],
            "positive_position_usd_mn": [0.0, 500.0],
        }
    )
    scored = score_anchor_year(group)
    assert scored.loc[0, "fdi_structural_score_raw"] == 0.0
    assert scored.loc[1, "fdi_structural_score_raw"] == 1.0
