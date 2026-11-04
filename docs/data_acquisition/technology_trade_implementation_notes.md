# Technology-trade pipeline implementation notes

## Repository placement

- `collect_technology_trade.py` -> `src/data/collect_technology_trade.py`
- `collect_tiva_technology_ratios.py` -> `src/data/collect_tiva_technology_ratios.py`
- `build_technology_trade.py` -> `src/data/build_technology_trade.py`
- `test_technology_trade.py` -> `tests/test_technology_trade.py`
- `test_tiva_technology_ratios.py` -> `tests/test_tiva_technology_ratios.py`
- `17_technology_trade_development.ipynb` -> `notebooks/17_technology_trade_development.ipynb`

## Required reference file

Create and validate:

`data/reference/unctad_ict_goods_hs6.csv`

Required columns:

```text
hs_revision
hs6_code
hs6_description
ict_category_code
ict_category_name
include_baseline
include_three_category
include_broad_ict
include_narrow_core
classification_source
```

Use the official UNCTAD edition-specific lists for HS 2002, 2007, 2012, 2017 and 2022. Do not substitute complete HS4 headings.

Provisional basket flags:

- `include_three_category`: computers/peripherals, communication equipment, electronic components.
- `include_baseline`: three-category basket plus miscellaneous ICT, pending composition audit.
- `include_broad_ict`: all five UNCTAD ICT categories.
- `include_narrow_core`: selected core computing, communications and semiconductor HS6 products.

The reference table is deliberately not fabricated in this delivery. It must be constructed from the official UNCTAD classification lists before the Comtrade collector is run.

## Pilot run

```bash
python src/data/collect_tiva_technology_ratios.py
python src/data/collect_technology_trade.py --start-year 2014 --end-year 2024
python src/data/build_technology_trade.py
pytest -q tests/test_tiva_technology_ratios.py tests/test_technology_trade.py
```

The default Comtrade run is limited to Japan, Malaysia, Singapore and Vietnam. It reads `COMTRADE_API_KEY` from the repository-root `.env`.

## Full-universe run

Only after the pilot audit passes:

```bash
python src/data/collect_technology_trade.py \
  --start-year 2004 \
  --end-year 2024 \
  --full-universe

python src/data/build_technology_trade.py
```

## Methodological defaults

- Comtrade reporter-side annual imports from China and the United States.
- Total customs procedure and total mode of transport.
- Baseline TiVA activity: `C26`.
- Sensitivity TiVA activity: `C26_27`.
- Observed TiVA ratios through 2022.
- Latest observed ratio carried forward to 2023-2024 with explicit status fields.
- Baseline score: pooled-value domestic-value-added-adjusted orientation.
- Preserve the gross orientation score as a separate field.

## Known review items before scaling

1. Confirm Comtrade classification-code mapping (`H2` through `H6`) against API metadata.
2. Confirm whether empty HS6 returns represent genuine zero trade or absent reporting.
3. Decide whether miscellaneous ICT remains in the baseline after inspecting its composition.
4. Add category-level output and equal-category aggregation after the HS6 reference table is fixed.
5. Confirm that Comtrade query batching stays within the active subscription limits.
6. Do not include 2025 without a separate decision.
