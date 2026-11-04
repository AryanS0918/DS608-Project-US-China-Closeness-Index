# Diplomatic subindex production method

## Purpose

The diplomatic subindex combines signed diplomatic structural ties with relative United Nations General Assembly voting alignment. Positive values indicate greater closeness to the United States and negative values indicate greater closeness to China.

## Baseline period

The complete-data baseline period for the current index edition is 2004-2024. The year 2025 is retained only as a clearly flagged provisional extension because diplomatic-representation data currently end in 2024.

## Components

The signed structural score equals the United States diplomatic structural score minus the China diplomatic structural score. The broad UNGA score is already signed in the same direction.

When both components are available:

`diplomatic_score = 0.5 * diplomatic_structural_signed_score + 0.5 * unga_score_broad`

When only one component is available, the score renormalises to that component. When neither component is available, the score remains missing. Available-component renormalisation does not make a one-component observation compositionally comparable with the two-component baseline.

## UNGA treatment

Provisionally insufficient participation remains included in the baseline with its status and participation rate retained. Exclusion is a formal sensitivity. The strict Yes-versus-No UNGA score is also retained as a robustness specification.

## Production output

`data/processed/diplomatic_subindex_country_year.csv`

Primary key: `country_iso3`, `year`. Expected scope: 4,205 rows, 192 entities, 2004-2025. The output preserves structural availability, UNGA availability, integration status, and comparability status.

## Audit outputs

- `outputs/tables/diplomatic_subindex/diplomatic_subindex_summary.json`
- `outputs/tables/diplomatic_subindex/diplomatic_subindex_sensitivity.csv`
- `outputs/tables/diplomatic_subindex/diplomatic_component_disagreement_cases.csv`

Relationship condition remains contextual and is not folded numerically into the diplomatic subindex.
