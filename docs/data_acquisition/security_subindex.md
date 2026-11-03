# Security subindex production method

## Purpose

The security subindex combines institutional-security ties and operational arms-transfer ties into one signed country-year score. Positive values indicate greater closeness to the United States; negative values indicate greater closeness to China.

## Production inputs

- `data/processed/security_institutional_ties_country_anchor_year.csv`
- `data/processed/sipri_arms_country_year.csv`

The panels join one-to-one on `iso3` and `year` after the institutional anchor panel is pivoted and converted to `US - China`.

## Baseline formula

When the SIPRI arms-transfer score is observed, including an observed zero:

`security_score = 0.5 * institutional_signed_score + 0.5 * arms_transfer_score`

When `observation_status == no_observed_arms_imports`, the arms component is structurally unavailable and the baseline renormalises to:

`security_score = institutional_signed_score`

An observed zero is not treated as missing. It retains half-weight because it records observed imports with no material transfer advantage for either anchor.

## Output

`data/processed/security_subindex_country_year.csv`

Primary key: `iso3`, `year`. Expected scope: 4,205 rows, 192 entities, 2004-2025.

## Sensitivity audits

Alternative one-third/two-thirds component weights are written to `outputs/tables/security_subindex/security_weighting_sensitivity.csv`. Component disagreements are written separately and are not production score fields.
