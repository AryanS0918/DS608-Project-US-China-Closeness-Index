# Trade orientation production method

## Purpose

The trade-orientation component measures whether a country-year's total merchandise trade with the two anchors is relatively more oriented toward the United States or China.

## Upstream collection

`src/data/collect_trade.py` retrieves or loads cached UN Comtrade annual bilateral flows, prioritises the reporting-country side, uses the corresponding anchor-side mirror observation when the reporting-country flow is unavailable, and writes `data/processed/trade_total_country_year.csv`.

The source-side labels are interpreted as reporter-side and mirror-side provenance. UN Comtrade metadata fields such as `isReported`, `isAggregate`, classification, and legacy-estimation flags remain in acquisition audit outputs. Aggregate total-merchandise observations are not excluded without stronger source-specific evidence that they are unsuitable.

## Production score

For country `i` and year `t`:

`US total trade = imports from US + exports to US`

`China total trade = imports from China + exports to China`

`trade_orientation_score = (US total trade - China total trade) / (US total trade + China total trade)`

The score is calculated only when all four bilateral flows are available and the denominator is positive. Missing flows are never replaced with zero.

## Canonical production layer

`src/data/build_trade_orientation.py` maps the broad Comtrade reporter-year panel onto the canonical 4,205-row project universe, excludes anchors and baseline-ineligible entities, respects historical validity intervals, and adds preferred country names.

The complete-data baseline period for the current index edition is 2004-2024. The year 2025 is retained as a provisional extension. Missing scores in either period remain explicit and are not zero-filled.

## Production output

`data/processed/trade_orientation_country_year.csv`

Primary key: `country_iso3`, `year`.

## Audit outputs

- `outputs/tables/trade_orientation/trade_orientation_summary.json`
- `outputs/tables/trade_orientation/trade_orientation_coverage_by_year.csv`
- `outputs/tables/trade_orientation/trade_orientation_provenance_audit.csv`
