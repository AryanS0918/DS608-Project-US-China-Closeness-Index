# Workstream 2 Findings: Neutral Band and Jenks Classification

**Date:** 8 November 2026  
**Score classified:** `core_index_available`  
**Reference period:** 2004-2024

## Selected classification

Use a symmetric neutral band of `(-0.05, +0.05)` and apply two-class Jenks natural breaks separately to the observations on each directional side.

Fixed production classes:

- **Strongly China-oriented:** score `<= -0.2550873926`
- **Moderately China-oriented:** `-0.2550873926 < score <= -0.05`
- **Neutral or hedging:** `-0.05 < score < +0.05`
- **Moderately US-oriented:** `+0.05 <= score < +0.2708862274`
- **Strongly US-oriented:** score `>= +0.2708862274`
- **No score:** continuous core score unavailable

The neutral band is symmetric because zero has substantive directional meaning. The strong-orientation breaks are asymmetric because they are empirical, side-specific Jenks results.

## Why 0.05 was selected

Candidate neutral half-widths were 0.025, 0.05, 0.075, 0.10, 0.125 and 0.15.

At 0.05:

- 526 of 4,014 observations, or 13.10%, are neutral or hedging;
- the smallest directional class still contains 9.07% of observations;
- only 25 of 3,822 consecutive-year pairs, or 0.65%, jump directly from one directional side to the other across the neutral band;
- 18.50% of consecutive-year pairs change any category, reflecting movement between adjacent classes as well as structural change;
- leaving out any one year changes the China strong break by at most 0.000889 and the US break by at most 0.003614.

A 0.025 band leaves only 6.45% neutral or hedging and permits 1.94% full side-to-side reversals. Wider bands progressively absorb 20% to 42% of observations, which weakens the directional purpose of the index.

## Class distribution, 2004-2024

- Moderately China-oriented: 1,384
- Strongly China-oriented: 720
- Neutral or hedging: 526
- Moderately US-oriented: 1,020
- Strongly US-oriented: 364

Within the neutral band:

- Hedging: 423
- Neutral: 103

Hedging means that at least one observed pillar is at or above +0.05 and at least one is at or below -0.05. Neutral means that the score lies inside the neutral band without that cross-directional pillar pattern.

## 2024 distribution

- Moderately China-oriented: 63
- Strongly China-oriented: 38
- Neutral or hedging: 18
- Moderately US-oriented: 44
- Strongly US-oriented: 28

Of the 18 neutral-band countries in 2024, 15 are hedging and 3 are neutral.

## Production rule

Do not recalculate Jenks breaks each year. Use the fixed pooled-period breaks for all years so that a given score has the same label throughout the dashboard and historical analysis.

The classes describe relative orientation, not absolute closeness, alliance status, or normative quality. Relationship condition remains a separate contextual overlay.
