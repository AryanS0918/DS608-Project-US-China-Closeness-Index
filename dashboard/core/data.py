"""Load the canonical production index and add dashboard context.

Canonical input (decision register, 8 November 2026):
    outputs/tables/closeness_index/us_china_relative_orientation_index_classified.csv

That file already contains the official core index, the strict comparison, the
experimental technology index, the fixed classes, hedging/neutral type and the
security no-ties flag. The dashboard only joins context that the file does not
carry, all read-only from existing production files:

* relationship condition toward each anchor, plus display-only diagnostic groups;
* technology sensitivity variants (shown side by side, never averaged);
* technology and economic period flags for tooltips.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
CANONICAL = ROOT / "outputs" / "tables" / "closeness_index" / "us_china_relative_orientation_index_classified.csv"
PROCESSED = ROOT / "data" / "processed"

BASELINE_START, BASELINE_END = 2004, 2024
ANCHORS = {"USA", "CHN"}

TECHNOLOGY_VARIANTS = {
    "dva_adjusted_orientation_score": "Pooled, DVA-adjusted (default experimental input)",
    "equal_category_dva_score": "Equal-category, DVA-adjusted",
    "gross_orientation_score": "Pooled, gross values",
    "equal_category_gross_score": "Equal-category, gross values",
}
DEFAULT_TECHNOLOGY = "dva_adjusted_orientation_score"

EXPECTED = {"rows": 4014, "countries": 192, "core_index_available": 4014, "core_index_complete": 3548,
            "experimental_technology_index": 3322}


def _require(path: Path) -> Path:
    if not path.exists():
        raise FileNotFoundError(
            f"Required production file not found: {path.relative_to(ROOT)}. "
            "Pull the latest main and run the dashboard from the repository root."
        )
    return path


# --------------------------------------------------------------------------
# Relationship condition: display-only diagnostic groups
# --------------------------------------------------------------------------
RELATIONSHIP_FIELDS = [
    "relationship_condition", "relationship_condition_severity", "condition_detail",
    "controlling_condition_trigger", "all_condition_triggers", "combined_evidence_profile",
    "evidence_merge_status", "evidence_status", "both_anchors_impose_measures",
]


def _relationship_display(rel: pd.DataFrame) -> pd.DataFrame:
    rel = rel.copy()
    families = rel["family_combination"].fillna("none")
    scope = rel["trade_scope_profile"].fillna("none")
    strained = rel["relationship_condition"].eq("strained")
    rel["condition_detail"] = rel["relationship_condition"]
    rel.loc[strained & families.str.contains("trade") & scope.str.contains("complete"), "condition_detail"] = "strained_complete_trade_measures"
    rel.loc[strained & families.str.contains("trade") & ~scope.str.contains("complete"), "condition_detail"] = "strained_partial_trade_measures"
    rel.loc[strained & ~families.str.contains("trade"), "condition_detail"] = "strained_targeted_measures"

    imposing = rel["sanctions_directions"].fillna("").str.contains("anchor_to_country")
    both = rel.assign(_imp=imposing).groupby(["country_iso3", "year"])["_imp"].transform("sum").ge(2)
    rel["both_anchors_impose_measures"] = both & imposing

    profile = rel["combined_evidence_profile"].fillna("")
    merge = rel["evidence_merge_status"].fillna("")
    rel["evidence_status"] = np.select(
        [rel["relationship_condition"].isna(), merge.eq("left_only"), profile.ne("no_adverse_evidence")],
        ["unsupported", "grid_completed_no_source_row", "directly_evidenced"],
        default="normal_supported_by_evidence",
    )
    return rel


def _relationship_wide() -> pd.DataFrame:
    rel = pd.read_csv(_require(PROCESSED / "relationship_condition_country_anchor_year.csv"))
    rel = rel.loc[rel["year"].between(BASELINE_START, BASELINE_END) & ~rel["country_iso3"].isin(ANCHORS)].copy()
    rel["anchor_key"] = rel["anchor"].map({"United States": "us", "China": "china"})
    if rel["anchor_key"].isna().any():
        raise ValueError("Unexpected anchor label in relationship-condition panel")
    rel = _relationship_display(rel)
    wide = rel.pivot(index=["country_iso3", "year"], columns="anchor_key", values=RELATIONSHIP_FIELDS)
    wide.columns = [f"{anchor}_{field}" for field, anchor in wide.columns]
    return wide.reset_index()


def _technology_variants() -> pd.DataFrame:
    tech = pd.read_csv(_require(PROCESSED / "technology_trade_country_year.csv"))
    tech = tech.rename(columns={"reporter_iso": "country_iso3"})
    keep = {v: f"technology_{v}" for v in TECHNOLOGY_VARIANTS}
    return tech[["country_iso3", "year", *keep]].rename(columns=keep)


# --------------------------------------------------------------------------
# Main loader
# --------------------------------------------------------------------------
def load_panel() -> tuple[pd.DataFrame, dict]:
    panel = pd.read_csv(_require(CANONICAL))
    keys = ["country_iso3", "year"]
    if panel.duplicated(keys).any():
        raise AssertionError("Duplicate country-year keys in the canonical index")

    panel = panel.merge(_technology_variants(), on=keys, how="left", validate="one_to_one")
    # The canonical technology_score must equal the default variant.
    diff = (panel["technology_score"] - panel[f"technology_{DEFAULT_TECHNOLOGY}"]).abs().max()
    if pd.notna(diff) and diff > 1e-12:
        raise AssertionError("technology_score does not match the default technology variant")

    panel = panel.merge(_relationship_wide(), on=keys, how="left", validate="one_to_one")
    for anchor in ("us", "china"):
        panel[f"{anchor}_evidence_status"] = panel[f"{anchor}_evidence_status"].fillna("unsupported")

    carried = panel["china_ratio_status"].eq("carried_forward") | panel["us_ratio_status"].eq("carried_forward")
    panel["technology_flag"] = np.where(
        panel["technology_score"].isna(), "",
        np.where(carried & panel["year"].eq(2024), "TiVA ratios carried forward; reduced 2024 reporter coverage",
                 np.where(carried, "TiVA ratios carried forward from 2022", "")),
    )
    panel["economic_period"] = pd.cut(
        panel["year"], bins=[2003, 2008, 2017, 2024],
        labels=["2004-08: before FDI source availability", "2009-17: host-official FDI historical extension",
                "2018-24: fixed-regime common period"],
    ).astype(str)
    panel["neutral_type"] = panel["neutral_type"].fillna("")
    panel["core_missing_pillars"] = panel["core_missing_pillars"].fillna("")

    found = {
        "rows": len(panel),
        "countries": panel["country_iso3"].nunique(),
        "core_index_available": int(panel["core_index_available"].notna().sum()),
        "core_index_complete": int(panel["core_index_complete"].notna().sum()),
        "experimental_technology_index": int(panel["experimental_technology_index"].notna().sum()),
    }
    meta = {**found, "years": (int(panel["year"].min()), int(panel["year"].max())),
            "matches_expected": found == EXPECTED}
    return panel, meta


def apply_technology_variant(panel: pd.DataFrame, variant: str) -> pd.DataFrame:
    """Swap the experimental technology input (sensitivity only)."""
    out = panel.copy()
    out["technology_score"] = out[f"technology_{variant}"]
    return out


def last_scored(panel: pd.DataFrame, score_col: str) -> pd.DataFrame:
    scored = panel.loc[panel[score_col].notna(), ["country_iso3", "year", score_col]]
    last = scored.sort_values("year").groupby("country_iso3").tail(1)
    return last.rename(columns={"year": "last_scored_year", score_col: "last_scored_value"})
