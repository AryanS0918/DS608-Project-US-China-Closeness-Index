"""Plotly figures for the dashboard.

Map colour rules (fixed for every year, never rescaled):
* Five-class views (official, scenario, single pillar, range average):
  strongly China (dark red), moderately China (light red), neutral or hedging (grey),
  moderately US (light blue), strongly US (dark blue), no score (warm light grey).
* Continuous views (difference, change between years): red-grey-blue on a fixed
  symmetric scale, grey inside the production neutral half-width.
* Relationship condition: separate amber-brown palette.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.colors import sample_colorscale

from .weighting import ALL_PILLARS, CLASS_LABELS, CLASS_ORDER, PILLAR_LABELS, THRESHOLDS

FONT = "Inter, -apple-system, Segoe UI, Roboto, sans-serif"
INK = "#1F2937"
MUTED = "#6B7280"
GRID = "#E5E7EB"

CLASS_COLOURS = {
    "strongly_china_oriented": "#B2182B",
    "moderately_china_oriented": "#F4A582",
    "neutral_or_hedging": "#BDBDBD",
    "moderately_us_oriented": "#92C5DE",
    "strongly_us_oriented": "#2166AC",
    "no_score": "#ECE8E1",
}
RED_RAMP = ["#FDDBC7", "#F4A582", "#D6604D", "#B2182B", "#67001F"]
BLUE_RAMP = ["#D1E5F0", "#92C5DE", "#4393C3", "#2166AC", "#053061"]
RAMP_POS = [0.0, 0.3, 0.55, 0.8, 1.0]
NEUTRAL = "#BDBDBD"
NO_SCORE = CLASS_COLOURS["no_score"]
NO_SCORE_LINE = "#A8A29E"
LAND = "#F8F8F6"
US_BLUE = "#2166AC"
CN_RED = "#B2182B"
ANCHOR_US = "#0B2545"
ANCHOR_CN = "#4A0D12"
SCENARIO = "#D97706"

CONDITION_ORDER = ["normal", "strained_targeted_measures", "strained_partial_trade_measures",
                   "strained_complete_trade_measures", "severely_strained", "ruptured", "unsupported"]
CONDITION_LABELS = {
    "normal": "Normal (no qualifying adverse condition)",
    "strained_targeted_measures": "Strained: targeted / non-trade measures",
    "strained_partial_trade_measures": "Strained: partial trade measures",
    "strained_complete_trade_measures": "Strained: complete trade measures",
    "severely_strained": "Severely strained",
    "ruptured": "Ruptured",
    "unsupported": "Unsupported / no evidence",
}
CONDITION_COLOURS = {
    "normal": "#F1EEE6",
    "strained_targeted_measures": "#F3D9A4",
    "strained_partial_trade_measures": "#E7A548",
    "strained_complete_trade_measures": "#C97A2B",
    "severely_strained": "#A8561A",
    "ruptured": "#3B2312",
    "unsupported": "#FFFFFF",
}

REGIONS = {
    "World": dict(center=dict(lat=20, lon=10), projection_scale=1.0),
    "Europe": dict(center=dict(lat=52, lon=15), projection_scale=4.2),
    "Middle East": dict(center=dict(lat=28, lon=45), projection_scale=4.0),
    "Africa": dict(center=dict(lat=2, lon=18), projection_scale=2.4),
    "South & Central Asia": dict(center=dict(lat=30, lon=72), projection_scale=3.2),
    "East Asia": dict(center=dict(lat=35, lon=120), projection_scale=3.2),
    "Southeast Asia": dict(center=dict(lat=5, lon=112), projection_scale=3.6),
    "Oceania & Pacific": dict(center=dict(lat=-12, lon=165), projection_scale=2.6),
    "North America": dict(center=dict(lat=40, lon=-98), projection_scale=2.6),
    "Central America & Caribbean": dict(center=dict(lat=16, lon=-75), projection_scale=5.0),
    "South America": dict(center=dict(lat=-18, lon=-60), projection_scale=2.5),
}

_CENTROIDS = Path(__file__).resolve().parents[1] / "assets" / "small_state_centroids.csv"
HOVER_COLS = [f"h{i}" for i in range(11)]
HOVER = (
    "<b style='font-size:14px'>%{customdata[1]}</b><br>"
    "%{customdata[2]}<br>"
    "<span style='color:#6B7280'>%{customdata[3]}</span><br>"
    "<span style='color:#6B7280'>%{customdata[4]}</span><br><br>"
    "%{customdata[5]}<br>%{customdata[6]}<br>%{customdata[7]}<br>%{customdata[8]}<br><br>"
    "Condition with US: %{customdata[9]}<br>"
    "Condition with China: %{customdata[10]}"
    "<extra></extra>"
)


# --------------------------------------------------------------------------
# Colour helpers
# --------------------------------------------------------------------------
def diverging_colorscale(scale_max: float, band: float) -> list[list]:
    band = min(max(band, 0.0), scale_max * 0.9)

    def pos(x):
        return (x + scale_max) / (2 * scale_max)

    stops = []
    for t, colour in sorted(zip(RAMP_POS, RED_RAMP), reverse=True):
        stops.append([pos(-band - t * (scale_max - band)), colour])
    if band > 0:
        stops += [[pos(-band), NEUTRAL], [pos(band), NEUTRAL]]
    for t, colour in zip(RAMP_POS, BLUE_RAMP):
        stops.append([pos(band + t * (scale_max - band)), colour])
    stops[0][0], stops[-1][0] = 0.0, 1.0
    return stops


def diverging_colour(value: float, scale_max: float, band: float) -> str:
    if value is None or not np.isfinite(value):
        return NO_SCORE
    if abs(value) < band:
        return NEUTRAL
    ramp = BLUE_RAMP if value > 0 else RED_RAMP
    t = min((abs(value) - band) / max(scale_max - band, 1e-9), 1.0)
    return sample_colorscale([[p, c] for p, c in zip(RAMP_POS, ramp)], [t], colortype="rgb")[0]


def class_colour(cls: str) -> str:
    return CLASS_COLOURS.get(cls, NO_SCORE)


# --------------------------------------------------------------------------
# Maps
# --------------------------------------------------------------------------
def _geo_layout(fig: go.Figure, region: str, height: int) -> None:
    view = REGIONS.get(region, REGIONS["World"])
    fig.update_geos(
        projection_type="natural earth", projection_scale=view["projection_scale"], center=view["center"],
        showframe=False, showcoastlines=False, showcountries=True, countrycolor="#FFFFFF", countrywidth=0.5,
        showland=True, landcolor=LAND, showocean=True, oceancolor="#FFFFFF", showlakes=False,
        resolution=50, bgcolor="rgba(0,0,0,0)", lataxis_range=[-58, 85],
    )
    fig.update_layout(
        height=height, margin=dict(l=0, r=0, t=0, b=0), paper_bgcolor="rgba(0,0,0,0)",
        font=dict(family=FONT, color=INK),
        hoverlabel=dict(bgcolor="white", bordercolor=GRID, font=dict(family=FONT, size=12, color=INK), align="left"),
        showlegend=False, dragmode="pan", uirevision=region,
    )


def _add_anchors(fig: go.Figure) -> None:
    for iso, name, colour in [("USA", "United States", ANCHOR_US), ("CHN", "China", ANCHOR_CN)]:
        fig.add_trace(go.Choropleth(
            locations=[iso], locationmode="ISO-3", z=[0], colorscale=[[0, colour], [1, colour]], showscale=False,
            marker_line_color="#FFFFFF", marker_line_width=0.6,
            hovertemplate=f"<b style='font-size:14px'>{name}</b><br>Reference power: scores are measured "
                          f"relative to it<br>(not scored)<extra></extra>",
        ))


def _add_small_states(fig: go.Figure, view: pd.DataFrame, colours: pd.Series) -> None:
    centroids = pd.read_csv(_CENTROIDS)
    small = view.assign(_c=colours.values).merge(centroids, left_on="country_iso3", right_on="iso3")
    if len(small):
        fig.add_trace(go.Scattergeo(
            lat=small["lat"], lon=small["lon"], mode="markers",
            marker=dict(size=7, color=small["_c"], line=dict(color="#4B5563", width=0.7)),
            customdata=small[HOVER_COLS].values, hovertemplate=HOVER,
        ))


def _categorical_map(view: pd.DataFrame, category_col: str, order: list[str], colours: dict,
                     region: str, height: int) -> go.Figure:
    fig = go.Figure()
    for cat in order:
        subset = view[view[category_col].eq(cat)]
        if subset.empty:
            continue
        colour = colours[cat]
        light = cat in ("no_score", "normal", "unsupported")
        fig.add_trace(go.Choropleth(
            locations=subset["country_iso3"], locationmode="ISO-3", z=np.zeros(len(subset)),
            colorscale=[[0, colour], [1, colour]], showscale=False,
            marker_line_color=NO_SCORE_LINE if light else "#FFFFFF", marker_line_width=0.5 if light else 0.4,
            customdata=subset[HOVER_COLS].values, hovertemplate=HOVER,
        ))
    _add_anchors(fig)
    _add_small_states(fig, view, view[category_col].map(colours).fillna(NO_SCORE))
    _geo_layout(fig, region, height)
    return fig


def class_map(view: pd.DataFrame, region: str, height: int = 560) -> go.Figure:
    """``view`` needs country_iso3, map_class and h0..h10."""
    return _categorical_map(view, "map_class", CLASS_ORDER, CLASS_COLOURS, region, height)


def condition_map(view: pd.DataFrame, condition_col: str, region: str, height: int = 560) -> go.Figure:
    data = view.copy()
    data[condition_col] = data[condition_col].fillna("unsupported")
    return _categorical_map(data, condition_col, CONDITION_ORDER, CONDITION_COLOURS, region, height)


def continuous_map(view: pd.DataFrame, scale_max: float, band: float, region: str, height: int = 560) -> go.Figure:
    """Diverging map of ``map_value`` (used for differences and changes)."""
    fig = go.Figure()
    scored = view[view["map_value"].notna()]
    unscored = view[view["map_value"].isna()]
    if len(unscored):
        fig.add_trace(go.Choropleth(
            locations=unscored["country_iso3"], locationmode="ISO-3", z=np.zeros(len(unscored)),
            colorscale=[[0, NO_SCORE], [1, NO_SCORE]], showscale=False,
            marker_line_color=NO_SCORE_LINE, marker_line_width=0.5,
            customdata=unscored[HOVER_COLS].values, hovertemplate=HOVER,
        ))
    fig.add_trace(go.Choropleth(
        locations=scored["country_iso3"], locationmode="ISO-3", z=scored["map_value"].clip(-scale_max, scale_max),
        zmin=-scale_max, zmax=scale_max, colorscale=diverging_colorscale(scale_max, band), showscale=False,
        marker_line_color="#FFFFFF", marker_line_width=0.4,
        customdata=scored[HOVER_COLS].values, hovertemplate=HOVER,
    ))
    _add_anchors(fig)
    _add_small_states(fig, view, view["map_value"].map(lambda v: diverging_colour(v, scale_max, band)))
    _geo_layout(fig, region, height)
    return fig


# --------------------------------------------------------------------------
# Charts
# --------------------------------------------------------------------------
def _base_layout(fig: go.Figure, height: int) -> go.Figure:
    fig.update_layout(
        height=height, margin=dict(l=8, r=8, t=8, b=8),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family=FONT, color=INK, size=12),
        hoverlabel=dict(bgcolor="white", bordercolor=GRID, font=dict(family=FONT, color=INK)),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0, bgcolor="rgba(0,0,0,0)"),
    )
    fig.update_xaxes(gridcolor=GRID, zeroline=False, linecolor=GRID)
    fig.update_yaxes(gridcolor=GRID, zeroline=False, linecolor=GRID)
    return fig


def _class_bands(fig: go.Figure, row=None, col=None, y_max: float = 1.0) -> None:
    """Horizontal background bands at the fixed production thresholds."""
    kw = {} if row is None else dict(row=row, col=col)
    t = THRESHOLDS
    bands = [
        (-y_max, t["china_strong"], CLASS_COLOURS["strongly_china_oriented"]),
        (t["china_strong"], -t["neutral"], CLASS_COLOURS["moderately_china_oriented"]),
        (-t["neutral"], t["neutral"], CLASS_COLOURS["neutral_or_hedging"]),
        (t["neutral"], t["us_strong"], CLASS_COLOURS["moderately_us_oriented"]),
        (t["us_strong"], y_max, CLASS_COLOURS["strongly_us_oriented"]),
    ]
    for y0, y1, colour in bands:
        fig.add_hrect(y0=y0, y1=y1, fillcolor=colour, opacity=0.12, line_width=0, layer="below", **kw)
    fig.add_hline(y=0, line_color="#9CA3AF", line_width=1, **kw)


def country_timeseries(frame: pd.DataFrame, series: dict[str, tuple[str, str, str]],
                       year_range: tuple[int, int], height: int = 360) -> go.Figure:
    fig = go.Figure()
    _class_bands(fig)
    fig.add_vrect(x0=year_range[0] - 0.4, x1=year_range[1] + 0.4, fillcolor="#111827", opacity=0.04, line_width=0)
    for label, (column, colour, dash) in series.items():
        fig.add_trace(go.Scatter(
            x=frame["year"], y=frame[column], name=label, mode="lines+markers",
            line=dict(color=colour, width=2.6 if dash == "solid" else 1.8, dash=dash), marker=dict(size=5),
            connectgaps=False, hovertemplate=f"{label}<br>%{{x}}: %{{y:+.3f}}<extra></extra>",
        ))
    _base_layout(fig, height)
    fig.update_yaxes(range=[-1.02, 1.02], tickvals=[-1, -0.5, 0, 0.5, 1],
                     ticktext=["−1 China", "−0.5", "0", "+0.5", "+1 US"])
    fig.update_xaxes(dtick=2, range=[2003.5, 2024.5])
    return fig


def pillar_small_multiples(frame: pd.DataFrame, height: int = 420) -> go.Figure:
    from plotly.subplots import make_subplots

    fig = make_subplots(rows=2, cols=2, subplot_titles=[PILLAR_LABELS[c] for c in ALL_PILLARS],
                        shared_xaxes=True, shared_yaxes=True, vertical_spacing=0.14, horizontal_spacing=0.06)
    for i, column in enumerate(ALL_PILLARS):
        r, c = divmod(i, 2)
        _class_bands(fig, row=r + 1, col=c + 1)
        experimental = column == "technology_score"
        fig.add_trace(go.Scatter(
            x=frame["year"], y=frame[column], mode="lines+markers",
            line=dict(color=MUTED if experimental else INK, width=1.8, dash="dot" if experimental else "solid"),
            marker=dict(size=4), showlegend=False,
            hovertemplate=f"{PILLAR_LABELS[column]}<br>%{{x}}: %{{y:+.3f}}<extra></extra>",
        ), row=r + 1, col=c + 1)
    _base_layout(fig, height)
    fig.update_layout(margin=dict(t=30))
    fig.update_yaxes(range=[-1.05, 1.05], tickvals=[-1, 0, 1])
    fig.update_xaxes(dtick=4, range=[2003.5, 2024.5])
    fig.update_annotations(font=dict(size=12, color=MUTED))
    return fig


def condition_strip(frame: pd.DataFrame, height: int = 150) -> go.Figure:
    fig = go.Figure()
    for anchor, label in [("china", "China"), ("us", "United States")]:
        states = frame[f"{anchor}_condition_detail"].fillna("unsupported")
        fig.add_trace(go.Scatter(
            x=frame["year"], y=[label] * len(frame), mode="markers",
            marker=dict(symbol="square", size=17, color=[CONDITION_COLOURS.get(s, "#FFF") for s in states],
                        line=dict(color="#9CA3AF", width=0.6)),
            customdata=np.stack([states.map(CONDITION_LABELS).fillna(states),
                                 frame[f"{anchor}_controlling_condition_trigger"].fillna("—"),
                                 frame[f"{anchor}_evidence_status"].fillna("unsupported")], axis=1),
            hovertemplate="%{x} · " + label + "<br><b>%{customdata[0]}</b><br>Trigger: %{customdata[1]}"
                          "<br>Evidence: %{customdata[2]}<extra></extra>",
            showlegend=False,
        ))
    _base_layout(fig, height)
    fig.update_xaxes(dtick=4, range=[2003.5, 2024.5], showgrid=False, tickangle=0)
    fig.update_yaxes(showgrid=False)
    return fig


def pillar_bars(frame: pd.DataFrame, height: int = 400) -> go.Figure:
    fig = go.Figure()
    palette = ["#1F2937", "#9CA3AF", "#0F766E", "#B45309"]
    labels = [PILLAR_LABELS[c] for c in ALL_PILLARS]
    for i, (_, row) in enumerate(frame.iterrows()):
        values = [row[c] for c in ALL_PILLARS]
        fig.add_trace(go.Bar(
            y=labels, x=[v if pd.notna(v) else 0 for v in values], orientation="h", name=row["preferred_country_name"],
            marker=dict(color=palette[i % 4]),
            text=[f"{v:+.3f}" if pd.notna(v) else "missing" for v in values], textposition="outside",
            hovertemplate=row["preferred_country_name"] + "<br>%{y}: %{text}<extra></extra>",
        ))
    fig.add_vrect(x0=0, x1=1.15, fillcolor=US_BLUE, opacity=0.05, line_width=0, layer="below")
    fig.add_vrect(x0=-1.15, x1=0, fillcolor=CN_RED, opacity=0.05, line_width=0, layer="below")
    _base_layout(fig, height)
    fig.update_layout(barmode="group", bargap=0.25)
    fig.update_xaxes(range=[-1.15, 1.15], tickvals=[-1, -0.5, 0, 0.5, 1],
                     ticktext=["−1 China", "−0.5", "0", "+0.5", "+1 US"])
    fig.update_yaxes(autorange="reversed")
    fig.add_vline(x=0, line_color="#9CA3AF")
    return fig


def influence_chart(nominal: pd.Series, influence: pd.Series, height: int = 300) -> go.Figure:
    cols = list(influence.index)
    labels = [PILLAR_LABELS[c] for c in cols]
    fig = go.Figure()
    fig.add_trace(go.Bar(x=labels, y=[nominal[c] for c in cols], name="Nominal weight", marker_color="#CBD5E1",
                         hovertemplate="%{x}<br>Nominal weight %{y:.0%}<extra></extra>"))
    fig.add_trace(go.Bar(x=labels, y=[influence[c] for c in cols], name="Share of cross-country variation",
                         marker_color="#334155", hovertemplate="%{x}<br>Effective influence %{y:.0%}<extra></extra>"))
    _base_layout(fig, height)
    fig.update_layout(barmode="group", bargap=0.35)
    fig.update_yaxes(tickformat=".0%", rangemode="tozero")
    return fig


def scenario_scatter(frame: pd.DataFrame, height: int = 380) -> go.Figure:
    fig = go.Figure()
    lim = max(0.35, float(np.nanmax(np.abs(frame[["official", "scenario"]].values))) + 0.05) if len(frame) else 1
    for t in (THRESHOLDS["china_strong"], -THRESHOLDS["neutral"], THRESHOLDS["neutral"], THRESHOLDS["us_strong"]):
        fig.add_vline(x=t, line_color=GRID, line_width=1)
        fig.add_hline(y=t, line_color=GRID, line_width=1)
    fig.add_shape(type="line", x0=-lim, y0=-lim, x1=lim, y1=lim, line=dict(color="#9CA3AF", dash="dot"))
    fig.add_trace(go.Scatter(
        x=frame["official"], y=frame["scenario"], mode="markers",
        marker=dict(size=8, color=[class_colour(c) for c in frame["scenario_class"]], line=dict(color="#374151", width=0.6)),
        text=frame["preferred_country_name"],
        hovertemplate="<b>%{text}</b><br>Official %{x:+.3f}<br>Scenario %{y:+.3f}<extra></extra>",
    ))
    _base_layout(fig, height)
    fig.update_xaxes(range=[-lim, lim], title="Official benchmark", showgrid=False)
    fig.update_yaxes(range=[-lim, lim], title="Your scenario", showgrid=False)
    return fig


def class_transition(official: pd.Series, scenario: pd.Series, height: int = 340) -> go.Figure:
    order = [c for c in CLASS_ORDER]
    table = pd.crosstab(official, scenario).reindex(index=order, columns=order, fill_value=0)
    table = table.loc[(table.sum(axis=1) > 0), (table.sum(axis=0) > 0)]
    short = {k: v.replace("-oriented", "").replace("Moderately", "Mod.").replace("Strongly", "Strong")
             for k, v in CLASS_LABELS.items()}
    fig = go.Figure(go.Heatmap(
        z=table.values, x=[short[c] for c in table.columns], y=[short[c] for c in table.index],
        colorscale=[[0, "#FFFFFF"], [1, "#334155"]], showscale=False,
        text=table.values, texttemplate="%{text}", hovertemplate="Official: %{y}<br>Scenario: %{x}<br>%{z} countries<extra></extra>",
    ))
    _base_layout(fig, height)
    fig.update_xaxes(title="Your scenario", side="bottom", showgrid=False)
    fig.update_yaxes(title="Official", autorange="reversed", showgrid=False)
    return fig


def coverage_chart(coverage: pd.DataFrame, height: int = 320) -> go.Figure:
    fig = go.Figure()
    styles = {
        "Official (≥2 core pillars)": ("#111827", "solid"),
        "Strict (all 3 core pillars)": ("#111827", "dash"),
        "Experimental (with technology)": ("#6B7280", "dot"),
        "Economic pillar": ("#A16207", "solid"),
        "Technology (experimental)": ("#0F766E", "solid"),
    }
    for label, (colour, dash) in styles.items():
        fig.add_trace(go.Scatter(x=coverage["year"], y=coverage[label], name=label, mode="lines",
                                 line=dict(color=colour, dash=dash, width=2)))
    _base_layout(fig, height)
    fig.update_yaxes(title="Countries", rangemode="tozero")
    fig.update_xaxes(dtick=2)
    return fig
