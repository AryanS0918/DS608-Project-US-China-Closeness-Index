# Economic institutional-ties production method

## Purpose

The economic institutional-ties component combines formal trade-agreement ties and bilateral investment treaties with China and the United States.

## Component formula

`economic_institutional_score = 0.75 * trade_agreement_score + 0.25 * BIT_score`

The upstream trade-agreement score uses:

- 60% bilateral FTA;
- 35% regional trade agreement; and
- 5% sectoral trade agreement.

The resulting effective family weights are:

- bilateral FTA: 0.4500;
- regional trade agreement: 0.2625;
- sectoral trade agreement: 0.0375; and
- BIT: 0.2500.

## BIT states

The BIT component distinguishes `none`, `historical_terminated`, `signed_not_in_force`, and `in_force`. The combined production panel preserves the BIT state and its supporting treaty fields.

## Canonical universe and 2025 treatment

The production builder maps the broad 2000-2024 agreement panels onto the canonical 8,410-row country-anchor-year universe for 2004-2025.

Rows from 2004-2024 are directly reconstructed from the agreement registers. Analyst review found no establishment, entry into force, termination, replacement, or other treaty-state change during 2025. The builder therefore carries the verified 31 December 2024 agreement states into 2025 and labels those rows `verified_unchanged_carry_forward`.

The carry-forward is limited to 2024-to-2025 and is validated field by field. It must not be extended automatically to later years.

## Production output

`data/processed/economic_institutional_ties_country_anchor_year.csv`

Primary key: `country_iso3`, `anchor`, `year`.

## Audit outputs

- `outputs/tables/economic_institutional_ties/economic_institutional_summary.json`
- `outputs/tables/economic_institutional_ties/economic_institutional_sensitivity_by_year.csv`
