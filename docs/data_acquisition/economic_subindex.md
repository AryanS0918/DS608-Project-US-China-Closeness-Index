# Economic subindex production method

## Purpose

The economic subindex combines merchandise-trade orientation, FDI structural orientation, and economic institutional orientation. Positive values indicate greater closeness to the United States. Negative values indicate greater closeness to China.

## Components

The three signed components are:

- `trade_orientation_score`;
- `fdi_orientation_score = United States FDI score - China FDI score`; and
- `economic_institutional_orientation_score = United States institutional score - China institutional score`.

## FDI reporting architecture

Each country uses one fixed official FDI reporting perspective.

Countries with signed host-official positions in at least six of nine years during 2009–2017 and at least four of seven years during 2018–2024 use host-reported official positions throughout 2009–2024.

All remaining countries use anchor-reported official positions during 2018–2024. Countries never switch reporting perspective.

## Score rule

When all three components are available, each receives one-third weight.

When exactly two components are available, renormalise the equal weights across the two available components.

Require at least two components to calculate an economic-subindex score. Institutional-only observations remain unavailable.

Do not replace unavailable components with zero.

## Period interpretation

- **2004–2008:** pre-FDI source-period extension.
- **2009–2017:** fixed-regime historical extension.
- **2018–2024:** fixed-regime common period.
- **2025:** provisional trade-plus-institutional extension. FDI is unavailable, trade coverage is incomplete, and institutional states are analyst-verified as unchanged from 2024.

These periods differ in component composition and must not be presented as fully compositionally identical.

## Production validation

The canonical panel contains:

- 4,205 country-years;
- 192 eligible entities;
- 3,670 available scores;
- 535 unavailable scores;
- 1,629 three-component scores;
- 2,041 two-component scores;
- 535 institutional-only unavailable observations;
- no duplicate keys;
- no one-component scores;
- no missing two- or three-component scores;
- no FDI scores in 2025; and
- all non-missing scores within `[-1, 1]`.

The production score range is:

- minimum: `-0.817393730317271`;
- maximum: `0.7120178416940932`.

## Sensitivities

Retain:

- zero filling as a rejected diagnostic specification;
- 40% trade, 40% FDI, and 20% institutional ties;
- 25% trade, 25% FDI, and 50% institutional ties;
- moderate and strict FDI regime-assignment thresholds; and
- component disagreement cases.

## Production artefacts

Production output:

`data/processed/economic_subindex_country_year.csv`

Production builder:

`src/data/build_economic_subindex.py`

Development notebook:

`notebooks/16_economic_subindex_integration.ipynb`

Focused tests:

`tests/test_economic_subindex.py`

Summary:

`outputs/tables/economic_subindex/economic_subindex_summary.json`

Weighting sensitivity:

`outputs/tables/economic_subindex/economic_subindex_sensitivity.csv`

Component disagreement audit:

`outputs/tables/economic_subindex/economic_component_disagreement_cases.csv`

## Reopening triggers

Revisit this method if:

- economic-component definitions change;
- FDI reporting-regime assignments change materially;
- alternative component weights materially affect the final composite;
- the minimum-two-component rule is reconsidered;
- complete and comparable 2025 FDI and trade data become available; or
- the final index adopts a different treatment of structurally unavailable components.
