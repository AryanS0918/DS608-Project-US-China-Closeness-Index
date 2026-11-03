# SIPRI security arms-transfer data

## Purpose

This component measures the material direction of each eligible country's
major-arms imports between the United States and China. It complements the
Security Institutional component, which captures formal and structured
security ties.

The baseline country-year score is the net United States-versus-China share
of global major-arms imports over a five-year rolling window:

```text
arms_transfer_score =
    (us_tiv_5yr - china_tiv_5yr) / global_tiv_5yr
```

Positive values indicate a net United States orientation, negative values
indicate a net China orientation, and zero indicates no net advantage for
either anchor in observed global imports.

## Source

The source files are exports from the SIPRI Arms Transfers Database covering
1996-2025:

- `data/raw/us_transfers.csv`;
- `data/raw/cn_transfers.csv`; and
- `data/raw/global_transfers.csv`.

All three files report volumes of transfers of major arms in millions of
SIPRI trend-indicator values (TIVs). The exports were generated on
26 October 2026.

The source notes distinguish two cases:

- an empty annual cell means that no deliveries were identified; and
- a displayed `0` means that the identified delivery volume was greater
  than zero but below 0.5 million TIV.

## Source-value treatment

The baseline process applies the following rules:

- empty annual cells are treated as zero identified deliveries;
- displayed zeroes are represented by the interval midpoint, `0.25`;
- positive numeric values are retained as reported; and
- unexpected non-numeric values cause the build to fail.

The value-treatment audit records the number of blank, displayed-zero and
positive numeric cells for each source file. A sensitivity analysis compares
displayed-zero substitutions of `0`, `0.25` and `0.5`.

## Recipient treatment

The pipeline separates source-marked non-state records from geographic
entities before country mapping.

Records are removed from state-level processing when SIPRI identifies them
as:

- armed groups or organisations through a trailing asterisk;
- total rows beginning with `Total `; or
- unknown-recipient rows.

Policy-dependent geographic entities are not removed by this source rule.
They are mapped where possible and governed by the project's canonical
country-master policy.

## Country mapping and entity universe

The canonical country master is:

`outputs/tables/relations_condition/relationship_condition_country_master.csv`

The pipeline maps SIPRI recipient labels using both `country_name` and
`preferred_country_name`, supplemented by explicit source-specific aliases.
It fails if any state-like recipient remains unmapped and aggregates records
after mapping to ensure one ISO3-year record.

The production universe is derived from the country master rather than from
the set of recipients appearing in SIPRI. This ensures that:

- baseline eligibility is consistent across components;
- the United States and China are excluded as anchor self-relations;
- special and policy-dependent entities follow the decided baseline policy;
- eligible entities with no observed delivery remain represented; and
- historical entities are included only within their valid years.

## Rolling construction

Annual source evidence covers 1996-2025. Five-year rolling sums require all
five annual observations. The production panel is then restricted to
2004-2025, so the 2004 observation uses the complete 2000-2004 window.

For country `i` and year `t`, define:

```text
us_tiv_5yr     = sum of United States TIV during t-4 to t
china_tiv_5yr  = sum of China TIV during t-4 to t
global_tiv_5yr = sum of global TIV during t-4 to t
anchor_tiv_5yr = us_tiv_5yr + china_tiv_5yr
```

## Baseline and diagnostic measures

### Baseline score

```text
arms_transfer_score =
    (us_tiv_5yr - china_tiv_5yr) / global_tiv_5yr
```

This measures the net anchor advantage as a share of all observed major-arms
imports. It avoids assigning an extreme component score to a small anchor
transfer when other suppliers dominate the recipient's procurement.

### Pure direction

```text
direction_score =
    (us_tiv_5yr - china_tiv_5yr) / anchor_tiv_5yr
```

This diagnostic measures which anchor predominates conditional on receiving
arms from at least one anchor.

### Anchor exposure

```text
anchor_exposure_raw = anchor_tiv_5yr / global_tiv_5yr
```

This diagnostic measures how much of the recipient's global procurement came
from the two anchors collectively.

Where both diagnostics are defined:

```text
arms_transfer_score = direction_score * anchor_exposure_raw
```

## Observation status

The production panel distinguishes three cases:

- `available`: at least one anchor supplied arms and all measures are
  available;
- `no_observed_anchor_transfers`: global imports were identified, but neither
  anchor supplied arms; the baseline score is `0`, while pure direction is
  undefined; and
- `no_observed_arms_imports`: no global deliveries were identified during the
  five-year window; the baseline score is missing.

A missing score therefore does not assert neutral alignment. It records the
absence of an observed global arms-import relationship during the window.

## Low-volume diagnostic

`low_volume_flag` records whether positive combined anchor TIV is below the
provisional threshold of 100 during the five-year window. It does not alter,
suppress or weight the baseline score.

Thresholds of 25, 50, 100 and 250 are retained in the sensitivity audit. The
100-TIV threshold is a provisional diagnostic, not a substantive boundary.

## Validation

The completed production build generated:

- 4,205 country-year rows;
- 192 entities represented across the production period;
- 3,262 non-missing baseline scores;
- 2,329 `available` observations;
- 933 `no_observed_anchor_transfers` observations;
- 943 `no_observed_arms_imports` observations;
- zero duplicate ISO3-year keys;
- zero unmapped state-like recipient names;
- zero anchor-exposure violations; and
- scores bounded within `[-1, 1]`.

The focused test suite contains eight passing tests covering source-value
treatment, non-state removal, mapping, duplicate aggregation, entity
eligibility, rolling calculations, status semantics, score identities and
score bounds.

## Outputs

Production panel:

`data/processed/sipri_arms_country_year.csv`

Production builder:

`src/data/build_sipri_arms_transfers.py`

Development notebook:

`notebooks/13_security_arms_transfers_development.ipynb`

Focused tests:

`tests/test_sipri_arms_transfers.py`

Audit directory:

`outputs/tables/security_arms_transfers/`

The audit directory contains annual evidence, source metadata, value-treatment
counts, removed recipients, mapping references, mapped source names, exposure
violations, threshold sensitivity and a machine-readable build summary.

## Reproducibility

Run from the repository root:

```bash
python src/data/build_sipri_arms_transfers.py
python -m pytest tests/test_sipri_arms_transfers.py -q
```

## Reopening triggers

Revisit the method if:

- SIPRI revises the source data or TIV reporting conventions;
- displayed-zero sensitivity materially affects the final composite;
- the baseline entity universe changes;
- a different rolling window is selected for the final index;
- the low-volume diagnostic is proposed as an exclusion or weighting rule;
- arms-transfer and institutional-security components show problematic
  double-counting during integration; or
- the overall index adopts a different treatment of structurally unavailable
  component scores.
