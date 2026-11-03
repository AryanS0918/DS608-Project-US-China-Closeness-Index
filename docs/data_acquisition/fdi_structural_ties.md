# FDI structural-ties production method

## Purpose

The FDI structural-ties component measures the intensity of each anchor's official outward direct-investment position in a country-year. Anchor-specific scores lie within `[0, 1]` and are later converted into a signed orientation score by subtracting China's score from the United States score.

## Source and direction

Use IMF Direct Investment Positions data with all of the following restrictions:

- reporting perspective: anchor report;
- economic direction: anchor to country;
- data type: reported official data;
- anchors: China and the United States;
- comparable source period: 2018-2024.

Country-reported inward positions and derived counterparty information remain outside the baseline.

## Entity mapping

The production builder maps IMF legal-form country names to the canonical project country master. It retains existing reviewed mappings and adds explicit aliases for valid countries previously misclassified as unresolved. Aggregates, territories, anchors, and baseline-ineligible entities remain excluded.

## Score

For an observed positive outward position:

1. calculate `log1p(position)`;
2. calculate the 95th percentile of positive log positions separately for each anchor-year;
3. divide the observation by that cap and clip at one.

Observed zero positions and observed negative net positions receive a zero structural-intensity score. Missing official positions remain missing and are never converted to zero.

## Time coverage

The canonical panel spans 2004-2025 so that it aligns with the other project components. Scores are only available in the comparable IMF source period, 2018-2024.

- 2004-2017: pre-FDI-source-period unavailable;
- 2018-2024: comparable FDI source period;
- 2025: provisional latest-year source unavailable.

## Production output

`data/processed/fdi_structural_ties_country_anchor_year.csv`

Primary key: `country_iso3`, `anchor`, `year`.

## Audit outputs

- `outputs/tables/fdi/fdi_structural_ties_summary.json`
- `outputs/tables/fdi/fdi_country_crosswalk_production_audit.csv`
