# FDI structural-ties production method

## Purpose

The FDI structural-ties component measures the intensity of the bilateral direct-investment relationship between each eligible country and the two anchors. Anchor-specific scores lie within `[0, 1]`. The signed FDI orientation is calculated as:

```text
United States FDI score - China FDI score
```

Positive values indicate greater FDI closeness to the United States. Negative values indicate greater FDI closeness to China.

## Source

Use IMF Direct Investment Positions data with:

- economic direction: anchor to country;
- data type: reported official data;
- anchors: China and the United States;
- host-reported and anchor-reported official perspectives selected through a fixed country-level regime.

Do not use observations derived using counterparty information in the production baseline.

## Entity mapping

Map IMF country names to the canonical project country master. Retain reviewed mappings and explicit legal-form aliases. Exclude aggregates, territories, anchors, and baseline-ineligible entities. Apply historical validity intervals, including Serbia and Montenegro (`SCG`) only during 2004–2006.

## Fixed reporting regimes

Assign each country permanently to one official reporting regime.

Assign a country to the **host-official fixed regime** when signed host-reported official positions for both anchors are available in:

- at least 6 of 9 years during 2009–2017; and
- at least 4 of 7 years during 2018–2024.

Assign all remaining countries to the **anchor-official fixed regime**.

The production assignment contains:

- 79 host-official fixed-regime countries;
- 112 anchor-official fixed-regime countries; and
- `SCG` outside the FDI source period because its valid project years end in 2006.

For host-regime countries, use host-reported official inward positions for both anchors during 2009–2024.

For anchor-regime countries, use anchor-reported official outward positions for both anchors during 2018–2024.

Do not switch reporting perspective within a country. Do not fill an isolated host-regime gap with anchor evidence or an anchor-regime gap with host evidence.

## Score

Select the official raw positions under the fixed-regime rule before calculating scores.

For each anchor-year:

1. assign zero positive intensity to observed zero and negative net positions;
2. apply `log1p` to observed positive positions;
3. calculate the 95th percentile of positive logged positions in the final selected anchor-year panel;
4. divide each logged positive position by that cap; and
5. clip the score at one.

Leave unavailable official positions missing. Never convert missing FDI evidence to zero.

## Period treatment

- **2004–2008:** FDI source unavailable for all countries.
- **2009–2017:** host-official historical extension for host-regime countries; FDI unavailable for anchor-regime countries.
- **2018–2024:** fixed-regime common period.
- **2025:** provisional latest-year FDI source unavailable.

## Production validation

The canonical panel contains:

- 8,410 country-anchor-years;
- 192 eligible entities;
- 2,438 host-reported official observations;
- 1,418 anchor-reported official observations;
- 240 official positions unavailable within selected source periods;
- 4,314 rows outside the selected source period;
- 663 signed FDI scores during 2009–2017;
- 1,171 signed FDI scores during 2018–2024;
- 1,834 signed FDI scores in total;
- no duplicate keys;
- no within-country reporting-perspective switching;
- no scores without observed positions;
- no scores before 2009 or in 2025; and
- all non-missing anchor scores within `[0, 1]`.

## Sensitivities

Retain the following regime-assignment sensitivities:

- moderate: 5 of 9 pre-period years and 4 of 7 post-period years;
- preferred: 6 of 9 and 4 of 7; and
- strict: 7 of 9 and 5 of 7.

Do not use counterparty-derived observations in the baseline. They may be retained for separate sensitivity analysis.

## Production artefacts

Production output:

`data/processed/fdi_structural_ties_country_anchor_year.csv`

Production builder:

`src/data/build_fdi_structural_ties.py`

Focused tests:

`tests/test_fdi_structural_ties.py`

Crosswalk audit:

`outputs/tables/fdi/fdi_country_crosswalk_production_audit.csv`

Regime-assignment audit:

`outputs/tables/fdi/fdi_reporting_regime_assignment.csv`

Threshold sensitivity:

`outputs/tables/fdi/fdi_regime_assignment_sensitivity_by_year.csv`

Summary:

`outputs/tables/fdi/fdi_structural_ties_summary.json`

## Reopening triggers

Revisit this method if:

- revised IMF data materially change bilateral positions or coverage;
- the host-versus-anchor overlap relationship changes materially;
- alternate availability thresholds materially affect the economic subindex;
- derived observations are proposed for the production baseline;
- repaired country mappings are shown to be incorrect; or
- a more complete and comparable bilateral FDI source becomes available.
