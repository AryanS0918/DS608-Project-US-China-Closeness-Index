"""Scenario scoring for the dashboard, built on the production functions.

The dashboard does not keep its own copy of the weighting maths. It calls
``src.data.build_closeness_index.weighted_index`` (which includes the
all-missing fix) and applies the fixed production classes from
``src.data.build_orientation_classification``.

Scenario rules (decision register, 8 November 2026):
* official core pillars: security, diplomatic, economic, one-third each;
* a scenario without technology needs at least 2 positively weighted, observed pillars;
* a scenario with positive technology weight is *experimental* and needs at least 3;
* missing pillars are never zero; weights are renormalised over observed pillars.
"""

from __future__ import annotations

from typing import Mapping

import numpy as np
import pandas as pd

from src.data.build_closeness_index import CORE_PILLARS, weighted_index
from src.data.build_orientation_classification import (
    CHINA_STRONG_BREAK,
    NEUTRAL_HALF_WIDTH,
    US_STRONG_BREAK,
    classify_score,
)

ALL_PILLARS = CORE_PILLARS + ["technology_score"]
PILLAR_LABELS = {
    "security_score": "Security",
    "diplomatic_score": "Diplomatic",
    "economic_score": "Economic",
    "technology_score": "Technology (experimental)",
}
DEFAULT_WEIGHTS = {"security_score": 33, "diplomatic_score": 33, "economic_score": 33, "technology_score": 0}
CORE_MIN = 2
EXPERIMENTAL_MIN = 3

CLASS_ORDER = [
    "strongly_china_oriented",
    "moderately_china_oriented",
    "neutral_or_hedging",
    "moderately_us_oriented",
    "strongly_us_oriented",
    "no_score",
]
CLASS_LABELS = {
    "strongly_china_oriented": "Strongly China-oriented",
    "moderately_china_oriented": "Moderately China-oriented",
    "neutral_or_hedging": "Neutral or hedging",
    "moderately_us_oriented": "Moderately US-oriented",
    "strongly_us_oriented": "Strongly US-oriented",
    "no_score": "No score",
}
THRESHOLDS = {"china_strong": CHINA_STRONG_BREAK, "neutral": NEUTRAL_HALF_WIDTH, "us_strong": US_STRONG_BREAK}


def is_experimental(weights: Mapping[str, float]) -> bool:
    return float(weights.get("technology_score", 0)) > 0


def required_minimum(weights: Mapping[str, float]) -> int:
    return EXPERIMENTAL_MIN if is_experimental(weights) else CORE_MIN


def positive_pillars(weights: Mapping[str, float]) -> list[str]:
    return [c for c in ALL_PILLARS if float(weights.get(c, 0)) > 0]


def scenario_scores(frame: pd.DataFrame, weights: Mapping[str, float]) -> pd.DataFrame:
    """Production ``weighted_index`` with the dashboard's minimum-pillar rule."""
    used = {c: float(weights.get(c, 0)) for c in ALL_PILLARS}
    return weighted_index(frame, used, min_available=required_minimum(weights))


def classify(scores: pd.Series) -> pd.Series:
    """Fixed production classes (never recalculated by year)."""
    return scores.map(classify_score)


def neutral_type(scores: pd.Series, frame: pd.DataFrame, pillars: list[str]) -> pd.Series:
    """Same rule as production ``neutral_type``, vectorised and over the given pillars.

    Hedging: score in the neutral band and at least one pillar >= +0.05 and one <= -0.05.
    """
    in_band = scores.abs().lt(NEUTRAL_HALF_WIDTH)
    values = frame[pillars]
    us = values.ge(NEUTRAL_HALF_WIDTH).any(axis=1)
    cn = values.le(-NEUTRAL_HALF_WIDTH).any(axis=1)
    out = np.where(~in_band | scores.isna(), "", np.where(us & cn, "hedging", "neutral"))
    return pd.Series(out, index=scores.index)


def class_text(cls: str, ntype: str = "") -> str:
    label = CLASS_LABELS.get(cls, cls)
    if cls == "neutral_or_hedging" and ntype:
        return "Hedging (pillars point both ways)" if ntype == "hedging" else "Neutral (no opposing pillar pattern)"
    return label


def pillar_influence(frame: pd.DataFrame, weights: Mapping[str, float]) -> pd.Series:
    """Share of cross-country variation in the scenario attributable to each weighted pillar.

    Covariance decomposition on rows where every weighted pillar is observed.
    """
    cols = positive_pillars(weights)
    if len(cols) < 2:
        return pd.Series(dtype=float)
    w = pd.Series({c: float(weights[c]) for c in cols})
    w = w / w.sum()
    complete = frame.loc[frame[cols].notna().all(axis=1), cols]
    if len(complete) < 3:
        return pd.Series(np.nan, index=cols)
    composite = complete.mul(w, axis=1).sum(axis=1)
    var = composite.var()
    if not np.isfinite(var) or var == 0:
        return pd.Series(np.nan, index=cols)
    return pd.Series({c: w[c] * complete[c].cov(composite) / var for c in cols})
