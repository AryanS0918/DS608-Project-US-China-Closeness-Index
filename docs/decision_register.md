## Total merchandise-trade component

- **Status:** Decided
- **Date:** 28 September 2026
- **Owner:** Darren

### Decision

Use annual UN Comtrade merchandise imports and exports with the United States and China. Prioritise country-reported values and use the corresponding anchor-reported mirror observation when a country-reported flow is unavailable.

Calculate the directional trade score only when all four required bilateral flows are available. Retain a flow as missing if neither the country nor the relevant anchor reports it. Do not replace missing values with zero. Do not calculate index scores for the United States or China.

### Rationale and evidence

The approach is symmetric, reproducible, transparent, historically extensive, and preserves the distinction between zero activity and unavailable data.

The 2000–2025 pipeline produced 4,301 valid non-anchor scores. Mirror supplementation recovered 345 of 409 initially missing flows. All eight unit tests passed.

### Reopening triggers

Revisit this decision if there are material revisions to Comtrade data, sustained gaps for major economies, evidence that mirror use creates material bias, emergence of a superior comparable source, or evidence that insignificant bilateral amounts produce misleading extreme scores.

## UNGA source data and indicator construction

- **Status:** Decided
- **Date:** 18 October 2026
- **Owner:** Darren

### Decision

Version the project-specific UNGA source workbooks under `data/sources/unga/`, while keeping `data/raw/` fully ignored.

Accompany the source workbooks with provenance documentation, United Nations attribution, SHA-256 checksums, known data-quality limitations, and the reproducible processing module `src/data/process_unga.py`.

The baseline UNGA indicator includes resolutions where the United States and China both cast substantive votes and selected different positions. Retain a strict Yes-versus-No specification as a robustness measure.

For a qualifying resolution:

- matching the United States is scored `+1`;
- matching China is scored `-1`;
- matching neither anchor is scored `0`; and
- absence and non-membership are excluded from the country-specific denominator.

Identify duplicate resolutions and malformed vote observations through audit outputs rather than silently correcting them. Write country-year scores, the country-resolution panel, coverage statistics, anchor-resolution eligibility, duplicate records, and ingestion exceptions to `data/processed/`.

### Rationale

This design measures revealed relative voting orientation when the two anchor countries differ, while preserving a transparent robustness specification. Versioning the redistributable source artefacts makes the result reproducible without weakening the rule that `data/raw/` remains local-only and ignored.

### Reopening triggers

Revisit this decision if the project migrates fully to an official machine-readable UN voting dataset, the treatment of anchor abstentions changes, participation thresholds materially affect rankings, source redistribution terms change, or validation against published ideal-point measures reveals a major construct or processing problem.

## Diplomatic representation source treatment

- **Status:** Decided
- **Date:** 1 November 2026
- **Owner:** Darren

### Decision

Use the Diplomatic Representation Database as a directed country-anchor-year source. Preserve separately representation maintained by the anchor in the country and representation maintained by the country in the anchor.

Use the Level of Representation (`LOR`) as the principal measure of directed diplomatic depth. Calculate a bilateral measure only when both directed observations are available. Do not assign zero to an unobserved direction or impute it. Treat an absent directed dyad-year as missing or no recorded representation, not by itself as evidence of rupture.

### Rationale and evidence

Diplomatic representation is directional. Preserving both directions prevents unilateral and reciprocal representation from being treated as equivalent and prevents source non-observation from being interpreted as a crisis.

The development workflow preserved both directions, audited one-direction-only cases, examined `LOR`, rank, and mission-focus changes, separated structural depth from adverse condition evidence, and produced:

`data/processed/diplomatic_structural_ties_country_anchor_year.csv`

### Reopening triggers

Revisit this decision if source revisions change the interpretation of missing directions, evidence supports a valid treatment of one-direction-only cases, `LOR` coding changes materially, or a superior comparable annual source becomes available.

## Diplomatic representation condition signal

- **Status:** Decided
- **Date:** 1 November 2026
- **Owner:** Darren

### Decision

Use the Diplomatic Representation Database separately for structural diplomatic depth and explicit adverse diplomatic-condition evidence. Ordinary non-zero changes in embassy rank, representation level, or mission focus do not by themselves generate a strained condition.

Use these conservative rules:

- one observed direction with `LOR = 0` or `Focus = 3`: `severely_strained`;
- both observed directions with explicit adverse coding in the same country-anchor-year: `ruptured`;
- positive observed representation without explicit adversity: `normal`; and
- neither direction observed: `missing`.

Retain rank and focus changes as diagnostic fields. Retain `ruptured` as the highest state. It denotes observed bilateral operational rupture, not necessarily formal legal severance.

### Rationale and evidence

Diagnostic testing identified 581 non-zero rank downgrades and 541 rank upgrades during 2000–2024. An extended rank-downgrade rule would classify 565 country-anchor-years as strained, including many changes more consistent with appointments, vacancies, administration, or reporting than crises.

### Reopening triggers

Revisit this decision if source documentation distinguishes formal severance more precisely, validated event evidence supports some non-zero changes as crisis signals, the meaning of `Focus = 3` or `LOR = 0` changes, or external validation shows substantial classification error.

## Overall relationship-condition panel

- **Status:** Decided
- **Date:** 1 November 2026
- **Owner:** Darren

### Decision

Construct a symmetric country-anchor-year panel using the highest supported severity from harmonised evidence. Use the ordered states `normal`, `strained`, `severely_strained`, and `ruptured`.

Preserve the controlling trigger, all supporting triggers, source-specific evidence, missingness, historical-entity eligibility, and anchor self-relation exclusions. Apply rupture precedence when supported. Do not infer normality from complete source absence.

### Validation verdict

The corrected GSDB panel, non-state exclusion audit, harmonised evidence panel, DRD country resolution, historical-entity validation, symmetric production grid, four-state classifier, trigger preservation, and rupture precedence all passed.

Production output:

`data/processed/relationship_condition_country_anchor_year.csv`

### Reopening triggers

Revisit this decision if sanctions persistence changes, another condition source is added, severity ordering changes, external validation reveals systematic errors, historical-entity validity changes, or the project adopts a probabilistic condition model.

## Bilateral investment-treaty ties

- **Status:** Decided
- **Date:** 1 November 2026
- **Owner:** Darren

### Decision

Use the China and United States bilateral investment-treaty workbooks to construct annual country-anchor-year treaty states. Preserve signature, entry into force, termination, and post-termination status separately.

Use the project country master and reviewed crosswalk:

`outputs/tables/bilateral_investment_treaties/bit_counterparty_crosswalk.csv`

Expand a source entity into multiple countries only when the source explicitly represents a multi-country counterparty and the expansion is recorded in the audit.

Production output:

`data/processed/bilateral_investment_treaties_country_anchor_year.csv`

### Reopening triggers

Revisit this decision if the workbooks are revised, treaty succession or survival clauses require different treatment, multi-country mapping changes, or a superior authoritative machine-readable source becomes available.

## Trade-agreement ties

- **Status:** Decided
- **Date:** 1 November 2026
- **Owner:** Darren

### Decision

Construct annual country-anchor-year trade-agreement ties from the reviewed agreement register. Preserve the distinction between bilateral free-trade agreements, regional agreements, and sectoral or limited-scope agreements.

Retain reconstructed pre-source-period memberships only when supported by the reviewed register and explicit validity dates. Do not infer membership from merchandise-trade activity.

Production output:

`data/processed/trade_agreement_ties_country_anchor_year.csv`

### Reopening triggers

Revisit this decision if membership or effective dates are revised, agreement-family treatment changes, overlapping agreements create material double-counting, or a more complete authoritative database is adopted.

## Economic institutional ties

- **Status:** Decided for the current specification
- **Date:** 1 November 2026
- **Owner:** Darren

### Decision

Combine bilateral investment-treaty and trade-agreement indicators into a country-anchor-year economic institutional-ties component. Retain the underlying indicators so the combined score remains auditable.

Treat an observed state of no active agreement as zero rather than missing when source coverage supports that state. Preserve missingness when source coverage or country mapping is insufficient.

Production output:

`data/processed/economic_institutional_ties_country_anchor_year.csv`

### Reopening triggers

Revisit this decision if the BIT or trade-agreement construction changes, component weights change, sensitivity shows domination by one family, agreement depth becomes consistently measurable, or another institutional family is added.

## FDI source selection and reporting perspective

- **Status:** Decided
- **Date:** 1 November 2026
- **Owner:** Darren

### Decision

Use IMF Direct Investment Positions as the production source. Use only official asset-owner reporting with economic direction `anchor_to_country`, reporting perspective `anchor_report`, and data type `Reported official data`.

Do not use rows labelled `Derived using counterparty information` as an independent mirror fallback.

### Evidence and country universe

The audit found 5,191 official observations, 5,191 derived representations, 5,191 paired observations, zero derived-only observations, and zero non-identical pairs. The derived rows are duplicate metadata representations rather than independent evidence.

The crosswalk maps 170 IMF names to project entities and classifies 89 remaining names as aggregates, confidential or unspecified categories, or entities outside the project master.

Use `outputs/tables/relations_condition/relationship_condition_country_master.csv` as the canonical master. Exclude aggregates, confidential or unspecified categories, entities outside the master, historically ineligible entities, and anchor self-relations.

### Reopening triggers

Revisit this decision if IMF metadata meaning changes, official coverage changes materially, a more comparable source becomes available, national-source validation reveals systematic problems, or the project country universe changes.

## FDI structural-ties formulation

- **Status:** Decided for the current index specification
- **Date:** 1 November 2026
- **Owner:** Darren

### Statistical object and period

Measure each destination's relative importance within an anchor's annual outward-investment portfolio. The score does not compare untransformed dollar magnitudes across anchors.

Use 2018–2024. Official Chinese anchor-to-country positions are unavailable in the selected IMF representation before 2018. Do not backfill pre-2018 observations with zero.

### Score rule

For observed position `P(i,a,t)` in USD millions:

```text
P_positive(i,a,t) = max(P(i,a,t), 0)
L(i,a,t) = log(1 + P_positive(i,a,t))
Q95(a,t) = 95th percentile of positive L(i,a,t) values
FDI(i,a,t) = min(L(i,a,t) / Q95(a,t), 1)
```

Apply these data rules:

- positive position: apply the log-p95 score;
- observed zero: score zero;
- observed negative net position: score zero while retaining the value and flag;
- missing position: retain a missing score;
- never replace missing with zero; and
- never take the absolute value of a negative position.

### Rationale and evidence

The method preserves magnitude ordering, compresses the concentrated right tail, limits domination by financial centres, avoids replacing magnitudes with ranks, and gives a transparent 0–1 score. Portfolio-share, percentile, and log-p95 alternatives produced almost identical rankings.

The panel contains 2,828 rows for two anchors over 2018–2024, with 202 eligible observations per anchor-year after excluding self-relations. The production builder reproduced the Notebook 11 candidate exactly. Focused tests passed (`3 passed in 0.25s`), followed by the full suite (`11 passed in 0.38s`).

Production implementation and outputs:

- `src/data/build_fdi_structural_ties.py`
- `tests/test_fdi_structural_ties.py`
- `data/processed/fdi_structural_ties_country_anchor_year.csv`
- `outputs/tables/fdi/fdi_structural_ties_summary.json`

Method identifier:

`official_outward_positive_log1p_scaled_to_anchor_year_p95`

### Interpretation constraint

Normalization is separate within each anchor-year. A score of `0.8` means relatively high intensity within that anchor's annual portfolio. Equal US and Chinese scores do not imply equal dollar positions.

### Reopening triggers

Revisit this decision if the IMF series extends consistently before 2018, treatment of negative positions changes, the 95th-percentile cap materially affects conclusions, anchor-year normalization obscures important differences, a common external denominator is adopted, financial-centre concentration needs separate treatment, missingness materially affects the composite, or final weighting requires another scale.
