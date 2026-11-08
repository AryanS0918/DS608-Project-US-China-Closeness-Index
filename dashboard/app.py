"""US-China Relative Orientation Index: Streamlit dashboard.

Run from the repository root:

    streamlit run dashboard/app.py

Reads the canonical production output
outputs/tables/closeness_index/us_china_relative_orientation_index_classified.csv
(plus relationship-condition and technology context). Writes nothing.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dashboard.core import charts  # noqa: E402
from dashboard.core.data import (  # noqa: E402
    BASELINE_END,
    BASELINE_START,
    DEFAULT_TECHNOLOGY,
    TECHNOLOGY_VARIANTS,
    apply_technology_variant,
    load_panel,
)
from dashboard.core.weighting import (  # noqa: E402
    ALL_PILLARS,
    CLASS_LABELS,
    CLASS_ORDER,
    CORE_PILLARS,
    DEFAULT_WEIGHTS,
    PILLAR_LABELS,
    THRESHOLDS,
    class_text,
    classify,
    is_experimental,
    neutral_type,
    pillar_influence,
    positive_pillars,
    required_minimum,
    scenario_scores,
)

TITLE = "US–China Relative Orientation Index"
NEUTRAL = THRESHOLDS["neutral"]
DIFF_SCALE = 0.5  # fixed symmetric scale for difference / change maps

st.set_page_config(page_title=TITLE, page_icon="🧭", layout="wide", initial_sidebar_state="expanded")

st.markdown(
    """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
html, body, [class*="css"], .stMarkdown, .stText, button, input, label { font-family: 'Inter', sans-serif; }
.block-container { padding-top: 3.2rem; padding-bottom: 3rem; max-width: 1400px; }
h1, h2, h3, h4, h5 { letter-spacing: -0.01em; color: #111827; }
section[data-testid="stSidebar"] { background: #F9FAFB; border-right: 1px solid #E5E7EB; }
section[data-testid="stSidebar"] h3 { font-size: 0.78rem; text-transform: uppercase; letter-spacing: 0.06em;
  color: #6B7280; margin: 1.1rem 0 0.2rem 0; }
.app-title { font-size: 1.75rem !important; line-height: 1.25; font-weight: 700; color: #111827; margin: 0; }
.app-sub { color: #6B7280; font-size: 0.95rem; margin: 0.2rem 0 0.8rem 0; }
.badge { display:inline-block; padding: 0.18rem 0.6rem; border-radius: 999px; font-size: 0.75rem; font-weight: 600;
  margin: 0 0.35rem 0.3rem 0; border: 1px solid #E5E7EB; background: #FFFFFF; color: #374151; }
.badge.official { background: #ECFDF5; border-color: #10B981; color: #065F46; }
.badge.scenario { background: #FEF3C7; border-color: #F59E0B; color: #92400E; }
.badge.experimental { background: #FFE4E6; border-color: #FB7185; color: #9F1239; }
.badge.warn { background: #FFF7ED; border-color: #FDBA74; color: #9A3412; }
.kpi { border: 1px solid #E5E7EB; border-radius: 10px; padding: 0.6rem 0.8rem; background: #FFFFFF; min-height: 112px; }
.kpi .l { min-height: 2.1em; }
.kpi .v { font-size: 1.4rem; font-weight: 700; color: #111827; line-height: 1.2; }
.kpi .l { font-size: 0.72rem; color: #6B7280; text-transform: uppercase; letter-spacing: 0.04em; }
.kpi .s { font-size: 0.72rem; color: #6B7280; }
.kpi .bar { height: 4px; border-radius: 2px; margin-bottom: 0.4rem; }
.legend-wrap { display:flex; align-items:center; gap: 1rem; flex-wrap: wrap; font-size: 0.8rem; color:#4B5563;
  margin: 0.3rem 0 0.2rem 0; }
.legend-bar { height: 12px; width: 320px; border-radius: 3px; border: 1px solid #E5E7EB; }
.legend-ends { display:flex; justify-content: space-between; width: 320px; font-size: 0.74rem; color:#6B7280; }
.sw { display:inline-block; width: 14px; height: 12px; border-radius: 2px; vertical-align: middle; margin-right: 5px;
  border: 1px solid #A8A29E; }
.card { border: 1px solid #E5E7EB; border-radius: 12px; padding: 1rem 1.1rem; background: #FFFFFF; }
.card h4 { margin: 0 0 0.25rem 0; font-size: 1.05rem; }
.muted { color:#6B7280; font-size: 0.83rem; }
.score-big { font-size: 1.7rem; font-weight: 700; line-height: 1.1; }
.note { color:#6B7280; font-size: 0.8rem; }
.callout { border: 1px solid #FCD34D; background: #FFFBEB; border-radius: 10px; padding: 0.6rem 0.9rem;
  font-size: 0.87rem; color: #78350F; margin-bottom: 0.4rem; }
div[data-testid="stTabs"] button p { font-size: 0.93rem; font-weight: 500; }
</style>
""",
    unsafe_allow_html=True,
)


# --------------------------------------------------------------------------
# Data
# --------------------------------------------------------------------------
@st.cache_data(show_spinner="Loading the canonical index…")
def get_panel():
    return load_panel()


@st.cache_data(show_spinner=False)
def get_variant(variant: str):
    base, _ = get_panel()
    return base if variant == DEFAULT_TECHNOLOGY else apply_technology_variant(base, variant)


@st.cache_data(show_spinner=False)
def get_scenario(variant: str, weights: tuple) -> pd.DataFrame:
    frame = get_variant(variant)
    return scenario_scores(frame, dict(zip(ALL_PILLARS, weights)))


try:
    BASE, META = get_panel()
except FileNotFoundError as exc:
    st.error(str(exc))
    st.stop()

NAMES = BASE.drop_duplicates("country_iso3").set_index("country_iso3")["preferred_country_name"].sort_values()
WEIGHT_KEYS = {c: f"w_{c.replace('_score', '')}" for c in ALL_PILLARS}
for column, key in WEIGHT_KEYS.items():
    st.session_state.setdefault(key, DEFAULT_WEIGHTS[column])
st.session_state.setdefault("country", "JPN" if "JPN" in NAMES.index else NAMES.index[0])
st.session_state.setdefault("map_view", "Official")

VIEWS = ["Official", "Your scenario", "Difference", "Single pillar", "Relationship condition"]


def reset_weights():
    for column, key in WEIGHT_KEYS.items():
        st.session_state[key] = DEFAULT_WEIGHTS[column]


def show_view(view: str):
    st.session_state["map_view"] = view


# --------------------------------------------------------------------------
# Sidebar
# --------------------------------------------------------------------------
with st.sidebar:
    st.markdown(f"**{TITLE}**")
    st.caption("Relative orientation between the United States and China, 2004–2024.")

    st.markdown("### Time")
    time_mode = st.radio("Period", ["Single year", "Year range"], horizontal=True, label_visibility="collapsed")
    if time_mode == "Single year":
        year = st.slider("Year", BASELINE_START, BASELINE_END, BASELINE_END)
        year_range, range_stat = (year, year), "single"
    else:
        year_range = st.slider("Years", BASELINE_START, BASELINE_END, (2014, BASELINE_END))
        choice = st.radio("Show", ["Average over range", "Change (end − start)"],
                          help="Average: mean yearly score, shown only if scored in at least half the years, then "
                               "classified with the fixed thresholds. Change: end-year minus start-year score "
                               "(blue = moved toward the US, red = toward China).")
        range_stat = "single" if year_range[0] == year_range[1] else ("average" if choice.startswith("Average") else "change")

    st.markdown("### Official benchmark")
    official_field = st.selectbox(
        "Official field",
        ["core_index_available", "core_index_complete"],
        format_func={"core_index_available": "Official: ≥2 of 3 core pillars",
                     "core_index_complete": "Strict comparison: all 3 core pillars"}.get,
        help="Official benchmark = security, diplomatic and economic, one-third each, renormalised when one core "
             "pillar is missing. The strict field requires all three.",
    )

    st.markdown("### Scenario weights")
    st.caption("Normalised automatically. The official benchmark is unaffected; see your scenario with the "
               "**Your scenario** or **Difference** map views.")
    selected = {}
    for column, key in WEIGHT_KEYS.items():
        selected[column] = st.slider(PILLAR_LABELS[column], 0, 100, key=key)
    st.button("Reset to official weights (⅓ each, technology 0)", on_click=reset_weights, width="stretch")

    total = sum(selected.values())
    weights_ok = total > 0
    experimental = is_experimental(selected)
    if not weights_ok:
        st.error("All weights are zero. Set at least one weight above zero.")
    else:
        norm = {c: selected[c] / total for c in ALL_PILLARS}
        st.dataframe(pd.DataFrame({
            "Pillar": [PILLAR_LABELS[c].replace(" (experimental)", " (exp.)") for c in ALL_PILLARS],
            "Set": [selected[c] for c in ALL_PILLARS],
            "Share": [f"{norm[c]:.0%}" for c in ALL_PILLARS],
        }), hide_index=True, width="stretch")
        st.caption(f"Total selected weight: **{total}**")
        need, have = required_minimum(selected), len(positive_pillars(selected))
        if have < need:
            st.warning(f"A scenario needs at least {need} weighted pillars"
                       f"{' when technology is included' if experimental else ''}. "
                       "To view one pillar alone, use the **Single pillar** map view.")
        if experimental:
            st.info("Technology has positive weight, so this is an **experimental** user-weighted scenario.")

    with st.expander("Display & sensitivity", expanded=False):
        region = st.selectbox("Zoom to region", list(charts.REGIONS), index=0)
        tech_variant = st.selectbox("Technology input (experimental)", list(TECHNOLOGY_VARIANTS),
                                    format_func=TECHNOLOGY_VARIANTS.get,
                                    help="Affects only the experimental technology views and scenarios. "
                                         "Variants are never averaged together.")

weights_tuple = tuple(selected[c] for c in ALL_PILLARS)
scenario_changed = weights_tuple != tuple(DEFAULT_WEIGHTS[c] for c in ALL_PILLARS)
panel = get_variant(tech_variant).copy()
scen_pillars = positive_pillars(selected)
if weights_ok:
    sc = get_scenario(tech_variant, weights_tuple)
    panel["scenario"] = sc["score"].values
    for c in ALL_PILLARS:
        panel[f"eff_{c.replace('_score', '')}"] = sc[f"effective_{c.replace('_score', '')}_weight"].values
    panel["scenario_coverage"] = sc["requested_weight_coverage"].values
else:
    panel["scenario"] = np.nan
    panel["scenario_coverage"] = np.nan
panel["official"] = panel[official_field]
panel["official_class"] = classify(panel["official"])
panel["official_ntype"] = neutral_type(panel["official"], panel, CORE_PILLARS)
panel["scenario_class"] = classify(panel["scenario"])
panel["scenario_ntype"] = neutral_type(panel["scenario"], panel, scen_pillars or CORE_PILLARS)
SCEN_LABEL = "Experimental user-weighted scenario" if experimental else "User-weighted scenario"


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------
def fmt(v, signed=True):
    return "—" if v is None or pd.isna(v) else (f"{v:+.3f}" if signed else f"{v:.3f}")


def cond_text(detail, evidence):
    if detail is None or pd.isna(detail):
        return "unsupported"
    label = charts.CONDITION_LABELS.get(detail, detail).split(" (")[0]
    tag = {"directly_evidenced": "evidenced", "normal_supported_by_evidence": "supported",
           "grid_completed_no_source_row": "grid-completed", "unsupported": "unsupported"}.get(evidence, evidence)
    return f"{label} · {tag}"


def period_text():
    y0, y1 = year_range
    return {"single": f"{y1}", "average": f"{y0}–{y1} average", "change": f"change {y0}→{y1}"}[range_stat]


# --------------------------------------------------------------------------
# Header
# --------------------------------------------------------------------------
st.markdown(f"<div class='app-title'>{TITLE}</div>", unsafe_allow_html=True)
st.markdown(
    "<p class='app-sub'>Where each country's observable security, diplomatic and economic ties sit <i>between</i> "
    "the United States and China. The labels are directions on a neutral axis, not value judgements, and describe "
    "relative orientation, not absolute closeness or alliance status.</p>",
    unsafe_allow_html=True,
)

tab_map, tab_profile, tab_compare, tab_weights, tab_method = st.tabs(
    ["Global map", "Country profile", "Pillar comparison", "Weight explorer", "Methodology & coverage"]
)


# --------------------------------------------------------------------------
# Tab 1: map
# --------------------------------------------------------------------------
with tab_map:
    view_options = [v for v in VIEWS if not (range_stat == "change" and v == "Difference")]
    if st.session_state["map_view"] not in view_options:
        st.session_state["map_view"] = "Official"
    c_view, c_extra = st.columns([3.2, 1.3])
    map_view = c_view.radio("Map view", view_options, key="map_view", horizontal=True, label_visibility="collapsed")
    pillar_choice, anchor_choice = None, None
    if map_view == "Single pillar":
        pillar_choice = c_extra.selectbox("Pillar", ALL_PILLARS, format_func=PILLAR_LABELS.get,
                                          label_visibility="collapsed")
    elif map_view == "Relationship condition":
        anchor_choice = c_extra.selectbox("Toward", ["us", "china"], label_visibility="collapsed",
                                          format_func={"us": "Toward the United States", "china": "Toward China"}.get)

    # Badges
    badges = [f"<span class='badge'>{period_text()}</span>"]
    if map_view == "Official":
        badges.append(f"<span class='badge official'>Official benchmark · "
                      f"{'≥2 core pillars' if official_field == 'core_index_available' else 'strict, all 3 core pillars'}</span>")
    elif map_view in ("Your scenario", "Difference"):
        badges.append(f"<span class='badge {'experimental' if experimental else 'scenario'}'>{SCEN_LABEL} · "
                      "not the official index</span>")
    elif map_view == "Single pillar":
        exp = pillar_choice == "technology_score"
        badges.append(f"<span class='badge {'experimental' if exp else ''}'>Single pillar: {PILLAR_LABELS[pillar_choice]}"
                      f"{' · experimental ICT-goods trade orientation' if exp else ''}</span>")
    else:
        badges.append("<span class='badge'>Context only: does not change any score</span>")
    if year_range[1] >= 2023 and (experimental and map_view in ("Your scenario", "Difference")
                                  or pillar_choice == "technology_score"):
        badges.append("<span class='badge warn'>2023–24 technology uses carried-forward TiVA ratios</span>")
    st.markdown("".join(badges), unsafe_allow_html=True)

    if map_view == "Official" and scenario_changed and weights_ok:
        cc1, cc2, cc3 = st.columns([4, 1.1, 1.1])
        cc1.markdown("<div class='callout'>You've changed the scenario weights. The map still shows the "
                     "official benchmark.</div>", unsafe_allow_html=True)
        cc2.button("Show my scenario", on_click=show_view, args=("Your scenario",), width="stretch")
        cc3.button("Show difference", on_click=show_view, args=("Difference",), width="stretch")

    # ---- Build the period view --------------------------------------------
    value_col = {"Official": "official", "Your scenario": "scenario", "Difference": "difference",
                 "Single pillar": pillar_choice, "Relationship condition": "official"}[map_view]
    panel["difference"] = panel["scenario"] - panel["official"]
    hedge_pillars = {"Official": CORE_PILLARS, "Your scenario": scen_pillars or CORE_PILLARS}.get(map_view, [])

    y0, y1 = year_range
    sub = panel[panel["year"].between(y0, y1)]
    end = panel[panel["year"].eq(y1)].set_index("country_iso3")
    view = pd.DataFrame(index=pd.Index(sub["country_iso3"].unique(), name="country_iso3"))
    view["preferred_country_name"] = view.index.map(NAMES)
    grouped = sub.groupby("country_iso3")
    carry = ["official", "scenario", *ALL_PILLARS]
    if range_stat == "single":
        view["map_value"] = end[value_col]
        for c in carry:
            view[c] = end[c]
    elif range_stat == "average":
        n_years = y1 - y0 + 1
        enough = lambda col: grouped[col].mean().where(grouped[col].count() >= math.ceil(n_years / 2))
        view["map_value"] = enough(value_col)
        for c in carry:
            view[c] = enough(c)
    else:
        start = panel[panel["year"].eq(y0)].set_index("country_iso3")
        view["map_value"] = end[value_col] - start[value_col]
        for c in carry:
            view[c] = end[c] - start[c]
    for c in ["core_index_status", "core_missing_pillars", "security_no_ties_flag", "technology_flag",
              "us_condition_detail", "china_condition_detail", "us_evidence_status", "china_evidence_status",
              "us_both_anchors_impose_measures"]:
        view[c] = end[c]
    view = view.reset_index()

    is_continuous = map_view == "Difference" or range_stat == "change"
    if is_continuous:
        view["map_class"] = ""
        view["ntype"] = ""
    else:
        view["map_class"] = classify(view["map_value"])
        view["ntype"] = (neutral_type(view["map_value"], view, hedge_pillars) if hedge_pillars
                         else pd.Series("", index=view.index))
        view["official_class"] = classify(view["official"])
        view["official_ntype"] = neutral_type(view["official"], view, CORE_PILLARS)
        view["scenario_class"] = classify(view["scenario"])

    # ---- Hover text ------------------------------------------------------
    view_name = {"Official": "Official", "Your scenario": SCEN_LABEL, "Difference": "Scenario − official",
                 "Single pillar": PILLAR_LABELS.get(pillar_choice, ""), "Relationship condition": "Official"}[map_view]

    def main_line(r):
        v = r["map_value"]
        if is_continuous:
            if pd.isna(v):
                return f"{view_name} · {period_text()}: no score"
            direction = "toward the US" if v >= NEUTRAL else "toward China" if v <= -NEUTRAL else "little change"
            return f"{view_name} · {period_text()}: {fmt(v)} ({direction})"
        return f"{view_name} · {period_text()}: {fmt(v)} · <b>{class_text(r['map_class'], r['ntype'])}</b>"

    def second_line(r):
        if map_view in ("Your scenario", "Difference", "Single pillar") and not is_continuous:
            return f"Official: {fmt(r['official'])} · {class_text(r['official_class'], r['official_ntype'])}"
        if map_view in ("Your scenario", "Difference", "Single pillar"):
            return f"Official {fmt(r['official'])} · Scenario {fmt(r['scenario'])}"
        if scenario_changed and weights_ok:
            return f"Your scenario: {fmt(r['scenario'])}"
        return ""

    def status_line(r):
        bits = []
        if r["core_index_status"] == "available_two_pillar_renormalised":
            bits.append(f"2 of 3 core pillars, renormalised (missing {r['core_missing_pillars']})")
        if pd.notna(r["security_no_ties_flag"]) and bool(r["security_no_ties_flag"]):
            bits.append("security 0 = no measured ties with either power")
        if (pillar_choice == "technology_score" or (experimental and map_view in ("Your scenario", "Difference"))) \
                and isinstance(r["technology_flag"], str) and r["technology_flag"]:
            bits.append(r["technology_flag"])
        return " · ".join(bits) if bits else "Complete three-pillar observation"

    view["h0"] = view["country_iso3"]
    view["h1"] = view["preferred_country_name"]
    view["h2"] = view.apply(main_line, axis=1)
    view["h3"] = view.apply(second_line, axis=1)
    view["h4"] = view.apply(status_line, axis=1)
    for i, c in enumerate(ALL_PILLARS):
        tag = " · not in official" if c == "technology_score" else ""
        view[f"h{5 + i}"] = [f"{PILLAR_LABELS[c]}: {fmt(v)}{tag}" for v in view[c]]
    view["h9"] = [cond_text(d, e) for d, e in zip(view["us_condition_detail"], view["us_evidence_status"])]
    view["h10"] = [cond_text(d, e) for d, e in zip(view["china_condition_detail"], view["china_evidence_status"])]

    # ---- KPIs --------------------------------------------------------------
    if map_view == "Relationship condition":
        col = f"{anchor_choice}_condition_detail"
        counts = view[col].fillna("unsupported").value_counts()
        groups = [("Normal", ["normal"]), ("Strained: targeted", ["strained_targeted_measures"]),
                  ("Strained: trade", ["strained_partial_trade_measures", "strained_complete_trade_measures"]),
                  ("Severely strained", ["severely_strained"]), ("Ruptured", ["ruptured"])]
        tiles = [(label, int(sum(counts.get(k, 0) for k in keys)), "", charts.CONDITION_COLOURS[keys[0]])
                 for label, keys in groups]
    elif is_continuous:
        v = view["map_value"]
        tiles = [("Moved toward US", int((v >= NEUTRAL).sum()), f"by ≥ {NEUTRAL}", charts.US_BLUE),
                 ("Moved toward China", int((v <= -NEUTRAL).sum()), f"by ≥ {NEUTRAL}", charts.CN_RED),
                 ("Little change", int((v.abs() < NEUTRAL).sum()), f"within ±{NEUTRAL}", charts.NEUTRAL),
                 ("No score", int(v.isna().sum()), "", charts.NO_SCORE)]
    else:
        counts = view["map_class"].value_counts()
        hedging = int((view["ntype"] == "hedging").sum())
        tiles = []
        for cls in CLASS_ORDER[:5]:
            sub_txt = f"{hedging} hedging · {int(counts.get(cls, 0)) - hedging} neutral" if cls == "neutral_or_hedging" and hedge_pillars else ""
            tiles.append((CLASS_LABELS[cls], int(counts.get(cls, 0)), sub_txt, charts.CLASS_COLOURS[cls]))
        if counts.get("no_score", 0):
            tiles.append(("No score", int(counts.get("no_score", 0)), "", charts.NO_SCORE))
    kcols = st.columns(len(tiles))
    for col, (label, value, sub_txt, colour) in zip(kcols, tiles):
        col.markdown(f"<div class='kpi'><div class='bar' style='background:{colour}'></div>"
                     f"<div class='l'>{label}</div><div class='v'>{value}</div><div class='s'>{sub_txt or '&nbsp;'}</div></div>",
                     unsafe_allow_html=True)

    # ---- Map -----------------------------------------------------------------
    if map_view in ("Your scenario", "Difference") and view["scenario"].notna().sum() == 0:
        st.warning("No scenario scores with the current weights. Check the weight settings in the sidebar.")
    if map_view == "Relationship condition":
        fig = charts.condition_map(view, f"{anchor_choice}_condition_detail", region)
    elif is_continuous:
        fig = charts.continuous_map(view, DIFF_SCALE, NEUTRAL, region)
    else:
        fig = charts.class_map(view, region)
    event = st.plotly_chart(fig, width="stretch", key="world_map", on_select="rerun", selection_mode="points",
                            config={"scrollZoom": True, "displaylogo": False,
                                    "modeBarButtonsToRemove": ["select2d", "lasso2d", "toImage"]})
    try:
        points = event.selection.points if event and event.selection else []
    except AttributeError:
        points = []
    if points:
        p = points[0]
        iso = p.get("location") or (p.get("customdata") or [None])[0]
        if iso in NAMES.index and iso != st.session_state.get("_last_click"):
            st.session_state["country"] = iso
            st.session_state["_last_click"] = iso

    # ---- Legend ----------------------------------------------------------------
    t = THRESHOLDS
    if map_view == "Relationship condition":
        items = "".join(f"<span><span class='sw' style='background:{charts.CONDITION_COLOURS[s]}'></span>"
                        f"{charts.CONDITION_LABELS[s]}</span>" for s in charts.CONDITION_ORDER)
        legend = f"<div class='legend-wrap'>{items}</div>"
    elif is_continuous:
        stops = charts.diverging_colorscale(DIFF_SCALE, NEUTRAL)
        gradient = ", ".join(f"{c} {p * 100:.1f}%" for p, c in stops)
        legend = (f"<div class='legend-wrap'><div><div class='legend-bar' style='background: linear-gradient(90deg, {gradient});'></div>"
                  f"<div class='legend-ends'><span>−{DIFF_SCALE} toward China</span><span>0</span>"
                  f"<span>toward US +{DIFF_SCALE}</span></div></div>"
                  f"<span><span class='sw' style='background:{charts.NEUTRAL}'></span>Little change (|Δ| &lt; {NEUTRAL})</span>"
                  f"<span><span class='sw' style='background:{charts.NO_SCORE}'></span>No score</span></div>")
    else:
        ranges = {
            "strongly_china_oriented": f"≤ {t['china_strong']:.3f}",
            "moderately_china_oriented": f"{t['china_strong']:.3f} to −{NEUTRAL}",
            "neutral_or_hedging": f"−{NEUTRAL} to +{NEUTRAL}",
            "moderately_us_oriented": f"+{NEUTRAL} to +{t['us_strong']:.3f}",
            "strongly_us_oriented": f"≥ +{t['us_strong']:.3f}",
            "no_score": "insufficient pillars",
        }
        legend = "<div class='legend-wrap'>" + "".join(
            f"<span><span class='sw' style='background:{charts.CLASS_COLOURS[c]}'></span>{CLASS_LABELS[c]} "
            f"<span style='color:#9CA3AF'>({ranges[c]})</span></span>" for c in CLASS_ORDER) + "</div>"
    legend += (f"<div class='legend-wrap'><span><span class='sw' style='background:{charts.ANCHOR_US}'></span>"
               f"<span class='sw' style='background:{charts.ANCHOR_CN}'></span>Reference powers (not scored)</span>"
               f"<span><span class='sw' style='background:{charts.LAND}'></span>Outside the baseline universe</span></div>")
    st.markdown(legend, unsafe_allow_html=True)
    st.markdown("<p class='note'>Fixed thresholds for every year (side-specific Jenks breaks with a ±0.05 neutral band). "
                "Scroll or pinch to zoom, drag to pan, or use <b>Zoom to region</b>. Small states are marked with dots. "
                "Hover for details, click a country to select it. Neutral and hedging share a colour; the tooltip says which.</p>",
                unsafe_allow_html=True)

    # ---- Selected country and rankings ------------------------------------
    left, right = st.columns([1.05, 1])
    with left:
        iso = st.session_state["country"]
        st.markdown("##### Selected country")
        row = panel[(panel["country_iso3"].eq(iso)) & panel["year"].eq(y1)]
        if row.empty:
            st.info("The selected country is not in the baseline universe for this year.")
        else:
            r = row.iloc[0]

            def score_block(title, value, cls, ntype, extra=""):
                return (f"<div style='flex:1'><div class='muted'>{title}</div>"
                        f"<div style='display:flex;align-items:center;gap:0.5rem;margin:0.25rem 0'>"
                        f"<span style='display:inline-block;width:16px;height:16px;border-radius:4px;"
                        f"background:{charts.class_colour(cls)};border:1px solid #D1D5DB'></span>"
                        f"<span class='score-big'>{fmt(value)}</span></div>"
                        f"<div class='muted'>{class_text(cls, ntype)}{extra}</div></div>")

            blocks = score_block("Official benchmark", r["official"], r["official_class"], r["official_ntype"])
            if scenario_changed and weights_ok:
                blocks += score_block(SCEN_LABEL, r["scenario"], r["scenario_class"], r["scenario_ntype"])
            pillars = "".join(
                f"<div style='display:flex;justify-content:space-between;font-size:0.87rem;padding:2px 0'>"
                f"<span>{PILLAR_LABELS[c]}</span><b>{fmt(r[c])}</b></div>" for c in ALL_PILLARS)
            notes = []
            if bool(r["security_no_ties_flag"]):
                notes.append("Security 0 reflects no measured security ties with either power.")
            if r["core_index_status"] == "available_two_pillar_renormalised":
                notes.append(f"Scored on 2 of 3 core pillars (missing: {r['core_missing_pillars']}).")
            st.markdown(
                f"""<div class='card'><h4>{r['preferred_country_name']}</h4><div class='muted'>{y1}</div>
<div style='display:flex;gap:1.2rem;margin:0.6rem 0'>{blocks}</div>{pillars}
<div class='muted' style='margin-top:0.6rem'>{'<br>'.join(notes)}</div>
<div class='muted' style='margin-top:0.4rem'>With US: {cond_text(r['us_condition_detail'], r['us_evidence_status'])}<br>
With China: {cond_text(r['china_condition_detail'], r['china_evidence_status'])}</div></div>""",
                unsafe_allow_html=True)
    with right:
        ranked = view.dropna(subset=["map_value"]).sort_values("map_value")
        if map_view == "Relationship condition":
            ranked = view.dropna(subset=["official"]).sort_values("official").assign(map_value=lambda d: d["official"])
        st.markdown("##### " + ("Largest movements" if is_continuous else "Strongest orientation"))
        c1, c2 = st.columns(2)
        tbl = lambda d: d[["preferred_country_name", "map_value"]].rename(
            columns={"preferred_country_name": "Country", "map_value": "Score"})
        cfg = {"Score": st.column_config.NumberColumn(format="%+.3f")}
        c1.caption("Toward the US" if is_continuous else "Most US-oriented")
        c1.dataframe(tbl(ranked.tail(10).iloc[::-1]), hide_index=True, width="stretch", column_config=cfg)
        c2.caption("Toward China" if is_continuous else "Most China-oriented")
        c2.dataframe(tbl(ranked.head(10)), hide_index=True, width="stretch", column_config=cfg)
        st.download_button("Download this view (CSV)",
                           view[["country_iso3", "preferred_country_name", "map_value", "map_class", "ntype",
                                 "official", "scenario", *ALL_PILLARS, "core_index_status",
                                 "us_condition_detail", "china_condition_detail"]]
                           .assign(view=map_view, period=period_text()).to_csv(index=False),
                           file_name=f"orientation_{map_view.lower().replace(' ', '_')}_{period_text().replace(' ', '_')}.csv",
                           mime="text/csv", width="stretch")


# --------------------------------------------------------------------------
# Tab 2: country profile
# --------------------------------------------------------------------------
with tab_profile:
    options = list(NAMES.index)
    iso = st.selectbox("Country", options, index=options.index(st.session_state["country"]),
                       format_func=lambda x: NAMES[x], key="profile_country")
    if iso != st.session_state["country"]:
        st.session_state["country"] = iso
    cf = panel[panel["country_iso3"].eq(iso)].sort_values("year")
    latest = cf.iloc[-1]
    st.markdown(f"#### {NAMES[iso]}")
    st.markdown(f"<p class='muted'>{latest['year']}: official {fmt(latest['core_index_available'])} · "
                f"<b>{class_text(latest['orientation_class'], latest['neutral_type'])}</b></p>", unsafe_allow_html=True)
    series = {
        "Official (≥2 core pillars)": ("core_index_available", "#111827", "solid"),
        "Strict (all 3 core pillars)": ("core_index_complete", "#6B7280", "dash"),
        "Experimental: with technology": ("experimental_technology_index", "#0F766E", "dot"),
    }
    if scenario_changed and weights_ok:
        series[SCEN_LABEL] = ("scenario", charts.SCENARIO, "solid")
    st.plotly_chart(charts.country_timeseries(cf, series, year_range), width="stretch")
    st.caption("Background bands = the five fixed classes. Shaded column = selected period. Gaps mean no score; "
               "missing pillars are never treated as zero.")

    c1, c2 = st.columns([1.3, 1])
    with c1:
        st.markdown("##### Pillars over time")
        st.plotly_chart(charts.pillar_small_multiples(cf), width="stretch")
    with c2:
        st.markdown("##### Relationship condition (context only)")
        st.plotly_chart(charts.condition_strip(cf), width="stretch")
        st.markdown("<div class='note'>" + "".join(
            f"<div><span class='sw' style='background:{charts.CONDITION_COLOURS[s]}'></span>{charts.CONDITION_LABELS[s]}</div>"
            for s in charts.CONDITION_ORDER) + "</div>", unsafe_allow_html=True)
        st.caption("Sub-groups of 'strained' are provisional display diagnostics; the production classifier is unchanged.")
        both = cf["us_both_anchors_impose_measures"].fillna(False).astype(bool) & \
            cf["china_both_anchors_impose_measures"].fillna(False).astype(bool)
        if both.any():
            yrs = cf.loc[both, "year"].tolist()
            st.info(f"In {len(yrs)} year(s) ({yrs[0]}–{yrs[-1]}) both powers had adverse measures at the same time, "
                    "which often indicates a multilateral (e.g. UN Security Council) regime.")
        no_ties = cf.loc[cf["security_no_ties_flag"].astype(bool), "year"].tolist()
        if no_ties:
            st.info(f"Security is 0 in {len(no_ties)} year(s) because there were **no measured security ties with "
                    "either power**, not balanced ties.")

    st.markdown("##### Classification and coverage by year")
    flags = cf.assign(
        cls=[class_text(c, n) for c, n in zip(cf["orientation_class"], cf["neutral_type"])],
    )[["year", "core_index_available", "cls", "core_index_status", "core_missing_pillars", "security_no_ties_flag",
       "technology_status", "technology_flag", "economic_period", "us_evidence_status", "china_evidence_status"]].rename(columns={
        "year": "Year", "core_index_available": "Official", "cls": "Class", "core_index_status": "Status",
        "core_missing_pillars": "Missing core pillar", "security_no_ties_flag": "Security no ties",
        "technology_status": "Technology", "technology_flag": "Technology flag", "economic_period": "Economic period",
        "us_evidence_status": "US condition evidence", "china_evidence_status": "China condition evidence"})
    st.dataframe(flags.iloc[::-1], hide_index=True, width="stretch", height=300,
                 column_config={"Official": st.column_config.NumberColumn(format="%+.3f")})


# --------------------------------------------------------------------------
# Tab 3: pillar comparison
# --------------------------------------------------------------------------
with tab_compare:
    c1, c2 = st.columns([3, 1])
    default = [st.session_state["country"]] + [x for x in ["IND", "BRA", "DEU"] if x in NAMES.index and x != st.session_state["country"]][:2]
    chosen = c1.multiselect("Countries (up to 4)", list(NAMES.index), default=default[:3],
                            format_func=lambda x: NAMES[x], max_selections=4)
    cy = c2.selectbox("Year", list(range(BASELINE_END, BASELINE_START - 1, -1)), index=BASELINE_END - year_range[1])
    rows = panel[panel["year"].eq(cy) & panel["country_iso3"].isin(chosen)].copy()
    rows["order"] = rows["country_iso3"].map({c: i for i, c in enumerate(chosen)})
    rows = rows.sort_values("order")
    if rows.empty:
        st.info("Select at least one country.")
    else:
        st.plotly_chart(charts.pillar_bars(rows), width="stretch")
        st.caption("Technology is experimental and not part of the official benchmark.")
        table = rows.assign(cls=[class_text(c, n) for c, n in zip(rows["official_class"], rows["official_ntype"])])[
            ["preferred_country_name", *ALL_PILLARS, "official", "cls", "scenario", "core_index_status", "technology_flag"]
        ].rename(columns={"preferred_country_name": "Country", **{c: PILLAR_LABELS[c] for c in ALL_PILLARS},
                          "official": "Official", "cls": "Official class", "scenario": "Scenario",
                          "core_index_status": "Status", "technology_flag": "Technology flag"})
        st.dataframe(table, hide_index=True, width="stretch", column_config={
            c: st.column_config.NumberColumn(format="%+.4f") for c in [*PILLAR_LABELS.values(), "Official", "Scenario"]})
        st.markdown("##### Experimental technology variants (side by side, never averaged)")
        tech = rows[["preferred_country_name", *[f"technology_{v}" for v in TECHNOLOGY_VARIANTS]]].rename(
            columns={"preferred_country_name": "Country", **{f"technology_{v}": TECHNOLOGY_VARIANTS[v] for v in TECHNOLOGY_VARIANTS}})
        st.dataframe(tech, hide_index=True, width="stretch",
                     column_config={c: st.column_config.NumberColumn(format="%+.3f") for c in tech.columns[1:]})


# --------------------------------------------------------------------------
# Tab 4: weight explorer
# --------------------------------------------------------------------------
with tab_weights:
    y = year_range[1]
    yf = panel[panel["year"].eq(y)]
    if not weights_ok:
        st.error("All weights are zero. Set at least one weight above zero in the sidebar.")
    elif yf["scenario"].notna().sum() == 0:
        st.warning("The current weights produce no scenario scores (see the sidebar).")
    else:
        if not scenario_changed:
            st.info("Your scenario currently equals the official weights. Move the sliders in the sidebar to compare.")
        st.markdown(f"#### Official vs {SCEN_LABEL.lower()} ({y})")
        comp = yf.dropna(subset=["official", "scenario"])
        c1, c2 = st.columns([1.1, 1])
        with c1:
            st.plotly_chart(charts.scenario_scatter(comp), width="stretch")
            st.caption("Grid lines mark the fixed class thresholds. Points are coloured by their scenario class.")
        with c2:
            changed = int((comp["official_class"] != comp["scenario_class"]).sum())
            switched = int((np.sign(comp["official"]) * np.sign(comp["scenario"]) < 0).sum())
            m1, m2 = st.columns(2)
            m1.metric("Countries changing class", changed)
            m2.metric("Switching side (US ↔ China)", switched)
            st.plotly_chart(charts.class_transition(comp["official_class"], comp["scenario_class"]), width="stretch")

        st.markdown("##### Largest score changes")
        comp = comp.assign(change=comp["scenario"] - comp["official"],
                           off_cls=[CLASS_LABELS[c] for c in comp["official_class"]],
                           sc_cls=[CLASS_LABELS[c] for c in comp["scenario_class"]])
        movers = comp.reindex(comp["change"].abs().sort_values(ascending=False).index).head(12)
        st.dataframe(movers[["preferred_country_name", "official", "off_cls", "scenario", "sc_cls", "change"]].rename(columns={
            "preferred_country_name": "Country", "official": "Official", "off_cls": "Official class",
            "scenario": "Scenario", "sc_cls": "Scenario class", "change": "Change"}), hide_index=True, width="stretch",
            column_config={c: st.column_config.NumberColumn(format="%+.3f") for c in ["Official", "Scenario", "Change"]})

        if len(scen_pillars) >= 2:
            st.markdown(f"##### How much each weighted pillar moves the scenario ({y})")
            influence = pillar_influence(yf, selected)
            nominal = pd.Series({c: selected[c] / sum(selected[p] for p in scen_pillars) for c in scen_pillars})
            st.plotly_chart(charts.influence_chart(nominal, influence), width="stretch")
            st.caption("Equal nominal weights do not guarantee equal influence: a pillar that varies more across "
                       "countries moves the composite more.")

        st.markdown(f"##### Renormalised scenario rows ({y})")
        renorm = yf[yf["scenario"].notna() & (yf["scenario_coverage"] < 0.999)]
        st.caption(f"{len(renorm)} countries are scored with weights renormalised over the pillars available; "
                   f"{int(yf['scenario'].isna().sum())} have no scenario score.")
        if len(renorm):
            show = renorm[["preferred_country_name", "scenario_coverage",
                           *[f"eff_{c.replace('_score', '')}" for c in ALL_PILLARS]]].rename(columns={
                "preferred_country_name": "Country", "scenario_coverage": "Requested weight covered",
                **{f"eff_{c.replace('_score', '')}": f"Effective {PILLAR_LABELS[c].split(' (')[0].lower()}" for c in ALL_PILLARS}})
            st.dataframe(show, hide_index=True, width="stretch",
                         column_config={c: st.column_config.NumberColumn(format="%.2f") for c in show.columns[1:]})


# --------------------------------------------------------------------------
# Tab 5: methodology
# --------------------------------------------------------------------------
with tab_method:
    st.markdown("#### What the index measures")
    st.markdown(
        "Each eligible country-year is placed on a **relative orientation** axis between the United States and "
        "China, by comparing its observable ties with one power against the corresponding ties with the other. "
        "It does not measure absolute closeness, alliance status or relationship quality: a country with weak ties "
        "to both can sit near zero, just like one with strong, evenly matched ties. "
        "**+1 = US-oriented, −1 = China-oriented, 0 = balanced.** Neither direction is better or worse."
    )
    st.markdown("#### Mathematical specification")
    st.markdown("**1. Official benchmark.** Core pillars $k \\in C = \\{S, D, E\\}$ (security, diplomatic, economic), "
                "scores $P_{k,it} \\in [-1,1]$, observed set $A_{it} \\subseteq C$:")
    st.latex(r"I_{it} = \frac{\sum_{k \in A_{it}} \tfrac13\, P_{k,it}}{\sum_{k \in A_{it}} \tfrac13}"
             r"\qquad\text{if } |A_{it}| \ge 2")
    st.markdown("Missing pillars are never set to zero. The strict comparison requires $|A_{it}| = 3$.")
    st.markdown("**2. User scenarios.** For non-negative weights $w_k$ over $\\{S, D, E, X\\}$ ($X$ = technology):")
    st.latex(r"\tilde w_k = \frac{w_k}{\sum_j w_j},\qquad "
             r"I^{\,w}_{it} = \frac{\sum_{k \in A^{+}_{it}} \tilde w_k P_{k,it}}{\sum_{k \in A^{+}_{it}} \tilde w_k}")
    st.markdown("where $A^{+}_{it}$ are observed pillars with $w_k > 0$. At least 2 are required, or 3 when "
                "$w_X > 0$. A scenario with $w_X > 0$ is **experimental**.")

    st.markdown("**3. Pillars** (each signed US − China, bounded in $[-1,1]$).")
    st.latex(r"S = \tfrac12\,\frac{d^{US}-d^{CN}}{3} + \tfrac12\,\frac{TIV^{US}_{5y}-TIV^{CN}_{5y}}{TIV^{global}_{5y}}")
    st.caption("d = maximum active security-institutional depth (0–3); TIV = SIPRI five-year rolling arms imports. "
               "Without any observed arms imports, S equals the institutional term. S = 0 with no measured ties to "
               "either power is flagged (security_no_ties_flag).")
    st.latex(r"D = \tfrac12\,(s^{US}-s^{CN}) + \tfrac12\,U,\qquad s^{a} = 0.75\,\overline{\text{depth}}^{a} + 0.25\,\min(\text{depth}^{a})")
    st.caption("s = diplomatic representation depth; U = UNGA alignment on resolutions where the US and China voted "
               "differently (+1 matches US, −1 matches China, 0 neither).")
    st.latex(r"E = \text{mean of available}\Big\{\tfrac{T^{US}-T^{CN}}{T^{US}+T^{CN}},\; f^{US}-f^{CN},\; g^{US}-g^{CN}\Big\},\ \ge 2\text{ required}")
    st.caption("T = bilateral merchandise trade; f = FDI position intensity (log1p, scaled by the anchor-year 95th "
               "percentile, clipped at 1); g = economic institutional ties (0.75 trade agreements + 0.25 BITs).")
    st.latex(r"X_{\text{experimental}} = \frac{M^{US}_{DVA}-M^{CN}_{DVA}}{M^{US}_{DVA}+M^{CN}_{DVA}}")
    st.caption("ICT-goods imports adjusted by each anchor's domestic value-added share (OECD TiVA). Experimental: "
               "accessible TiVA data cannot reassign foreign value added by country of origin within ICT exports, so "
               "the measure systematically shifts results toward China. Not part of the official benchmark.")

    st.markdown("#### Classification (fixed for all years)")
    st.dataframe(pd.DataFrame({
        "Class": [CLASS_LABELS[c] for c in CLASS_ORDER],
        "Rule": [f"score ≤ {t['china_strong']:.10f}", f"{t['china_strong']:.10f} < score ≤ −0.05",
                 "−0.05 < score < +0.05", f"+0.05 ≤ score < +{t['us_strong']:.10f}",
                 f"score ≥ +{t['us_strong']:.10f}", "official score unavailable"],
    }), hide_index=True, width="stretch")
    st.markdown("The neutral band is symmetric because zero has substantive meaning. The strong-orientation breaks "
                "come from separate two-class Jenks splits on each side, so they differ slightly. Within the neutral band, "
                "**hedging** = at least one core pillar ≥ +0.05 and one ≤ −0.05; **neutral** = no such opposing pattern. "
                "Thresholds are pooled over 2004–2024 and never recalculated by year.")

    st.markdown("#### Relationship condition (context only)")
    st.markdown("Ordered states (normal, strained, severely strained, ruptured) toward each power, from sanctions and "
                "diplomatic-representation evidence. It never enters the index. *Normal* means no qualifying adverse "
                "condition, not closeness. The dashboard's sub-groups of *strained* (targeted / partial trade / complete "
                "trade) and the flag for both powers imposing measures are provisional display diagnostics; the "
                "production classifier is unchanged.")
    st.markdown("#### Time and comparability")
    st.markdown(
        "- Comparable period **2004–2024**; 2025 is not shown.\n"
        "- Economic: 2004–08 before FDI source availability; 2009–17 host-official FDI historical extension; 2018–24 "
        "fixed-regime common period.\n"
        "- Experimental technology: TiVA ratios observed to 2022; 2023–24 carried forward; 2024 has reduced reporter coverage.\n"
        "- Eligibility from the canonical country master; anchors and policy-excluded entities are outside the universe."
    )
    st.markdown("#### Coverage by year")
    cov = panel.groupby("year").agg(**{
        "Official (≥2 core pillars)": ("core_index_available", "count"),
        "Strict (all 3 core pillars)": ("core_index_complete", "count"),
        "Experimental (with technology)": ("experimental_technology_index", "count"),
        "Economic pillar": ("economic_score", "count"),
        "Technology (experimental)": ("technology_score", "count"),
    }).reset_index()
    st.plotly_chart(charts.coverage_chart(cov), width="stretch")
    st.caption(f"{META['rows']:,} country-years · {META['countries']} entities · {META['years'][0]}–{META['years'][1]} · "
               f"source: outputs/tables/closeness_index/us_china_relative_orientation_index_classified.csv"
               + ("" if META["matches_expected"] else " · ⚠ counts differ from the validated production summary"))
