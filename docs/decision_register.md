# US-China Closeness Index Decision Register

**Last updated:** 5 November 2026  
**Owner:** Darren  
**Primary comparable period:** 2004-2024  
**Direction convention:** Positive values indicate greater closeness to the United States; negative values indicate greater closeness to China; zero indicates balance.

This register consolidates the current production decisions. Later entries supersede inconsistent earlier formulations.

## Total merchandise-trade component

- **Status:** Decided
- **Date:** 28 September 2026; canonical production validation completed 3 November 2026
- **Owner:** Darren

### Decision

Use annual UN Comtrade merchandise imports and exports with the United States and China. Prioritise country-reported values and use the corresponding anchor-reported mirror observation when a country-reported flow is unavailable.

Calculate the signed orientation only when all four required bilateral flows are available:

`trade_orientation_score = (US trade - China trade) / (US trade + China trade)`

Retain a flow as missing if neither the country nor the relevant anchor reports it. Do not replace missing values with zero. Do not calculate index scores for the United States or China.

Interpret provenance labels as reporter-side and mirror-side rather than as definitive claims about the meaning of UN Comtrade's `isReported` metadata. Preserve the underlying metadata in acquisition audits.

### Production validation

- 4,205 country-years;
- 192 eligible entities;
- 2004-2025;
- 3,465 complete four-flow scores;
- 723 country-years with no source row;
- 17 source rows with incomplete bilateral flows;
- 3,332 scores using four reporter-side observations;
- 133 scores using one or more mirror-side recoveries;
- 740 missing scores;
- no duplicate keys;
- no scores without all four required flows; and
- all non-missing scores within `[-1, 1]`.

Use 2004-2024 as the comparable baseline. Retain 2025 only as a provisional extension.

### Production artefacts

- Output: `data/processed/trade_orientation_country_year.csv`
- Builder: `src/data/build_trade_orientation.py`
- Tests: `tests/test_trade_orientation.py`

### Reopening triggers

Revisit if Comtrade materially revises the data, sustained gaps emerge for major economies, mirror use creates material bias, a superior comparable source emerges, or insignificant bilateral values produce misleading extreme scores.

## UN General Assembly source data and indicator construction

- **Status:** Decided
- **Date:** 18 October 2026
- **Owner:** Darren

### Decision

Version the project-specific UNGA source workbooks under `data/sources/unga/`, while keeping `data/raw/` ignored. Retain provenance documentation, United Nations attribution, SHA-256 checksums, known limitations and reproducible processing in `src/data/process_unga.py`.

The baseline includes resolutions where the United States and China both cast substantive but different votes. Retain strict Yes-versus-No voting as a robustness measure.

For a qualifying resolution:

- matching the United States scores `+1`;
- matching China scores `-1`;
- matching neither anchor scores `0`; and
- absence and non-membership are excluded from the country-specific denominator.

Duplicate resolutions and malformed observations are written to audit outputs rather than silently corrected.

### Reopening triggers

Revisit if the project migrates to an official machine-readable dataset, anchor-abstention treatment changes, participation thresholds materially alter rankings, redistribution terms change, or validation reveals a substantial construct or processing problem.

## Baseline entity universe and historical eligibility

- **Status:** Decided
- **Date:** 3 November 2026
- **Owner:** Darren

### Decision

Use the corrected canonical country master to control baseline eligibility. Retain source observations where useful, but exclude the following from the baseline headline index for the current delivery:

- Cook Islands;
- Spanish Sahara;
- Gibraltar;
- Hong Kong;
- Kosovo;
- Montserrat;
- Niue;
- Palestine;
- Taiwan; and
- Holy See.

Exclude the United States and China from anchor self-relations.

Treat Byelorussian SSR, Czechoslovakia, German Democratic Republic, Dahomey, Upper Volta, Rhodesia, Soviet Union, North Vietnam and Yugoslavia as historical entities outside the baseline project window. Retain Serbia and Montenegro (`SCG`) only during 2004-2006.

Use `preferred_country_name` for modern display labels without replacing established crosswalk fields.

### Validation

The canonical master contains 213 entities: 191 sovereign-state rows, 10 historical-state rows, 10 special or policy-dependent rows and 2 anchor-state rows.

### Reopening triggers

Revisit if the baseline universe is expanded, special entities can be evaluated consistently across all pillars, a component requires another historical-validity rule, or assessment instructions prescribe another universe.

## Diplomatic representation source treatment

- **Status:** Decided
- **Date:** 3 November 2026
- **Owner:** Darren

### Decision

Use the Diplomatic Representation Database as a directed country-anchor-year source. Preserve representation maintained by the anchor in the country and representation maintained by the country in the anchor. Use Level of Representation (`LOR`) as the principal measure.

Within a valid entity-year and source-covered year, assign zero recorded structural depth to an absent directed dyad while retaining an explicit unobserved-direction flag. This means no representation recorded by the source, not diplomatic rupture or formal severance.

Preserve observed `LOR = 0` separately as an adverse source observation. Leave the structural score missing when a source year is unavailable, an entity-year is invalid, or a source or mapping problem prevents supported interpretation.

Calculate:

`mean_depth = (anchor_to_country_depth + country_to_anchor_depth) / 2`

`reciprocity_depth = min(anchor_to_country_depth, country_to_anchor_depth)`

Production baseline:

`structural_score = 0.75 * mean_depth + 0.25 * reciprocity_depth`

Retain mean-only, equal mean-reciprocity and geometric formulations as sensitivities.

### Production validation

- 8,410 country-anchor-years;
- 192 eligible entities;
- 2004-2025;
- 8,028 scored rows;
- 382 source-year-unavailable rows in 2025;
- no duplicate keys; and
- all non-missing scores within `[0, 1]`.

### Production artefacts

- Output: `data/processed/diplomatic_structural_ties_country_anchor_year.csv`
- Builder: `src/data/build_diplomatic_structural_ties.py`
- Tests: `tests/test_diplomatic_structural_ties.py`

## Diplomatic representation condition signal

- **Status:** Decided
- **Date:** 1 November 2026
- **Owner:** Darren

### Decision

Use the diplomatic source separately for structural depth and explicit adverse-condition evidence. Ordinary non-zero changes in rank, representation or mission focus do not generate a strained condition by themselves.

Use the conservative rules:

- one observed direction with `LOR = 0` or `Focus = 3`: `severely_strained`;
- both observed directions with explicit adverse coding: `ruptured`;
- positive observed representation without adverse coding: `normal`;
- neither direction observed: `missing`.

`Ruptured` means an observed bilateral operational rupture in representation. It does not necessarily establish formal legal severance.

## Overall relationship-condition panel and contextual overlay

- **Status:** Decided
- **Date:** 4 November 2026
- **Owner:** Darren

### Decision

Construct a symmetric country-anchor-year relationship-condition panel using the highest supported severity from harmonised evidence. Use the ordered states:

1. `normal`;
2. `strained`;
3. `severely_strained`;
4. `ruptured`.

Preserve the condition separately for each anchor, controlling trigger, all supporting triggers, source-specific evidence, evidence and merge status, missingness, historical eligibility and anchor exclusions. Apply rupture precedence when supported. Do not infer normality from complete source absence.

Relationship condition is a non-numerical contextual overlay. It does not enter the diplomatic pillar or overall index mechanically.

For the selected country-year, the dashboard should show the overall index, pillar scores, relationship condition toward each anchor, controlling and contributing reasons, and evidence-status information. Condition colours and symbols must remain distinct from the US-versus-China orientation scale.

### Production artefact

- Output: `data/processed/relationship_condition_country_anchor_year.csv`

### Dashboard requirement

Distinguish directly evidenced observations, evidence-supported normal states, symmetric grid-completed rows and genuinely unsupported observations. Do not present them as equally evidenced.

## Bilateral investment-treaty ties

- **Status:** Decided
- **Date:** 1 November 2026
- **Owner:** Darren

### Decision

Use the China and United States bilateral investment-treaty source workbooks to construct annual country-anchor-year treaty states. Preserve source and treaty-state evidence for audit and integration into economic institutional orientation.

## Security institutional ties

- **Status:** Decided
- **Date:** 3 November 2026
- **Owner:** Darren

### Decision

Construct annual security-institutional ties from a verified normalised membership register. Use the maximum active institutional depth:

1. structured participation without a binding mutual-defence obligation;
2. formal durable cooperation without full mutual defence; and
3. binding mutual-defence, collective-defence or military-assistance commitment.

Calculate:

`security_institutional_score_raw = maximum_depth / 3`

Retain supporting arrangements and controlling evidence. Do not add overlapping arrangements.

### Production validation

- 8,410 rows;
- 1,659 verified annual evidence rows;
- 96 membership spells;
- 10 arrangement families;
- no duplicate keys; and
- focused tests passed.

### Production artefacts

- Output: `data/processed/security_institutional_ties_country_anchor_year.csv`
- Builder: `src/data/build_security_institutional_ties.py`

## Security arms-transfer ties

- **Status:** Decided
- **Date:** 3 November 2026
- **Owner:** Darren

### Decision

Use SIPRI major-arms-transfer TIV data with five-year rolling sums:

`arms_transfer_score = (us_tiv_5yr - china_tiv_5yr) / global_tiv_5yr`

Use the complete 1996-2025 source history for rolling calculations and 2004-2025 as the production period. Retain direction, anchor exposure, volume and observation-status diagnostics without treating them as separate index components.

Treat empty annual cells as zero identified deliveries. Represent a displayed SIPRI `0` with midpoint `0.25` in the baseline, retaining `0` and `0.5` as sensitivities.

Assign score zero when global arms imports are observed but neither anchor supplied arms. Leave the score missing when no global arms imports were identified.

### Production validation

- 4,205 rows;
- 3,262 non-missing baseline scores;
- 2,329 available rows;
- 933 no-observed-anchor-transfer rows;
- 943 no-observed-arms-import rows;
- no duplicate keys; and
- score range within `[-1, 1]`.

### Production artefacts

- Output: `data/processed/sipri_arms_country_year.csv`
- Builder: `src/data/build_sipri_arms_transfers.py`
- Notebook: `notebooks/13_security_arms_transfers_development.ipynb`

## Security subindex integration

- **Status:** Decided
- **Date:** 3 November 2026
- **Owner:** Darren

### Decision

Use equal conceptual weights for signed institutional-security ties and arms-transfer ties when both are observed. When SIPRI reports `no_observed_arms_imports`, treat arms as structurally unavailable and renormalise to institutional ties. When SIPRI reports `no_observed_anchor_transfers`, retain the observed arms score of zero at half-weight. Do not zero-fill unavailable evidence.

### Production artefacts

- Output: `data/processed/security_subindex_country_year.csv`
- Builder: `src/data/build_security_subindex.py`
- Notebook: `notebooks/14_security_subindex_integration.ipynb`

## Diplomatic subindex integration

- **Status:** Decided
- **Date:** 3 November 2026
- **Owner:** Darren

### Decision

Combine signed structural ties and broad UNGA alignment with equal conceptual weights. The signed structural score is United States structural score minus China structural score.

When both are available:

`diplomatic_score = 0.5 * structural_score + 0.5 * UNGA_score`

When only one is available, renormalise to it. Do not zero-fill unavailable components. Retain broad UNGA as baseline and strict Yes-versus-No as robustness. Retain one-third/two-thirds weights as sensitivities.

Relationship condition remains a contextual overlay.

### Production artefacts

- Output: `data/processed/diplomatic_subindex_country_year.csv`
- Builder: `src/data/build_diplomatic_subindex.py`
- Notebook: `notebooks/15_diplomatic_subindex_integration.ipynb`
- Tests: `tests/test_diplomatic_subindex.py`

## FDI structural ties

- **Status:** Decided; supersedes anchor-report-only baseline
- **Date:** 4 November 2026
- **Owner:** Darren

### Decision

Use IMF Direct Investment Positions. Assign every country permanently to one official reporting regime.

Assign host-official fixed regime where signed host-reported official positions for both anchors are available in at least 6 of 9 years during 2009-2017 and at least 4 of 7 years during 2018-2024. Assign all others to anchor-official fixed regime.

For host-regime countries, use official host-reported inward positions for both anchors during 2009-2024. For anchor-regime countries, use official anchor-reported outward positions for both anchors during 2018-2024. Do not switch reporting perspective within a country, fill isolated gaps from the other regime, or use counterparty-derived rows in production.

Apply `log1p` to positive positions, scale by the selected anchor-year 95th percentile of positive logged positions and clip at one. Assign zero positive intensity to observed zero and negative positions. Leave unavailable positions missing.

### Period treatment

- 2004-2008: unavailable;
- 2009-2017: host-official historical extension;
- 2018-2024: fixed-regime common period;
- 2025: unavailable and provisional.

### Production validation

- 79 host-regime countries and 112 anchor-regime countries;
- 1,834 signed FDI scores;
- no duplicate keys;
- no within-country perspective switching;
- no scores before 2009 or in 2025; and
- all non-missing intensity scores within `[0, 1]`.

### Production artefacts

- Output: `data/processed/fdi_structural_ties_country_anchor_year.csv`
- Builder: `src/data/build_fdi_structural_ties.py`
- Tests: `tests/test_fdi_structural_ties.py`
- Regime audit: `outputs/tables/fdi/fdi_reporting_regime_assignment.csv`
- Sensitivity: `outputs/tables/fdi/fdi_regime_assignment_sensitivity_by_year.csv`
- Summary: `outputs/tables/fdi/fdi_structural_ties_summary.json`

## Economic subindex

- **Status:** Decided
- **Date:** 4 November 2026
- **Owner:** Darren

### Decision

Combine signed merchandise trade, FDI structural orientation and economic institutional orientation. Positive is US-oriented; negative is China-oriented.

When all three are available, assign one-third weight to each. When exactly two are available, renormalise equal weights over those two. Require at least two components. Leave institutional-only observations unavailable. Do not zero-fill missing components.

### Period interpretation

- 2004-2008: pre-FDI source-period extension;
- 2009-2017: fixed-regime historical extension;
- 2018-2024: fixed-regime common period;
- 2025: provisional extension.

### Production validation

- 4,205 country-years;
- 3,670 available scores;
- 535 unavailable scores;
- 1,629 three-component scores;
- 2,041 two-component scores;
- no duplicate keys; and
- score range `-0.817393730317271` to `0.7120178416940932`.

### Production artefacts

- Output: `data/processed/economic_subindex_country_year.csv`
- Builder: `src/data/build_economic_subindex.py`
- Notebook: `notebooks/16_economic_subindex_integration.ipynb`
- Tests: `tests/test_economic_subindex.py`
- Summary: `outputs/tables/economic_subindex/economic_subindex_summary.json`
- Sensitivity: `outputs/tables/economic_subindex/economic_subindex_sensitivity.csv`
- Disagreement audit: `outputs/tables/economic_subindex/economic_component_disagreement_cases.csv`

## Technology-trade native HS classifications and coverage handling

- **Status:** Decided
- **Date:** 4 November 2026
- **Owner:** Darren

### Decision

Use every reporter-year's native HS classification:

- `H0` = `HS1992`
- `H1` = `HS1996`
- `H2` = `HS2002`
- `H3` = `HS2007`
- `H4` = `HS2012`
- `H5` = `HS2017`
- `H6` = `HS2022`

Retain official revision-specific ICT-goods lists. Do not union revisions, invent concordances, infer reporter codes or impute native classifications.

Of 192 baseline-eligible countries, 183 have established reporter codes. Equatorial Guinea, Liechtenstein, Monaco, Marshall Islands, Nauru, North Korea, San Marino, Somalia and Chad remain explicitly unavailable where no established code exists.

Use statuses:

- `available`;
- `unavailable_missing_reporter_code`; and
- `unavailable_missing_native_classification`.

Only available reporter-years are submitted to Comtrade.

### Coverage artefact

- `outputs/tables/technology/technology_reporter_year_coverage.csv`

## Technology HS1992-to-HS1996 transition pilot

- **Status:** Decided
- **Date:** 4 November 2026
- **Owner:** Darren

### Decision

The Lesotho 2004-2005 and Suriname 2008-2009 pilot confirmed native HS1992 and HS1996 collection. Seven of eight reporter-anchor requests returned non-empty data; the remaining request was a successful empty response, not an API error.

Successful empty responses must be preserved as valid zero-trade evidence using readable cache structure and explicit metadata. Do not represent them only as zero-byte files.

## Global technology-trade panel and baseline specification

- **Status:** Decided, with 2023-2024 extension flags
- **Date:** 5 November 2026
- **Owner:** Darren

### Decision

The production panel uses native reporter-year HS classifications and the pooled, TiVA-adjusted technology-trade orientation.

**Correct production sign convention:**

`technology_score = (US DVA-adjusted imports - China DVA-adjusted imports) / (US DVA-adjusted imports + China DVA-adjusted imports)`

Positive values indicate stronger US orientation. Negative values indicate stronger China orientation. Zero indicates balance.

This supersedes the earlier China-minus-US formula and all narrative statistics stated under that earlier sign convention. The revised builder and executed development notebook use the project-wide US-minus-China convention.

Retain these alternatives for sensitivity and dashboard comparison:

- `gross_orientation_score`;
- `equal_category_gross_score`; and
- `equal_category_dva_score`.

The pooled-value score remains the baseline because it preserves the economic importance of observed trade values. Equal-category weighting remains a sensitivity because it reverses direction in 225 of 3,322 valid comparisons, or 6.77%.

No general HS-transition correction or smoothing is applied. Across 3,092 consecutive-year comparisons, mean absolute DVA-adjusted movement was 0.136961 without a revision change and 0.135602 with a revision change.

TiVA ratios are directly observed through 2022. Scores for 2023 and 2024 use carried-forward TiVA ratios and must be flagged. The 2024 extension must also be flagged for reduced reporter coverage.

### Production validation

- 3,360 available reporter-years;
- 180 countries;
- 6,720 reporter-year-anchor observations;
- 114 valid empty responses;
- no collection errors;
- no duplicate production keys; and
- no unmatched classification rows or trade values.

### Production artefacts

- Output: `data/processed/technology_trade_country_year.csv`
- TiVA ratios: `data/processed/tiva_technology_anchor_year.csv`
- Builder: `src/data/build_technology_trade.py`
- Collector: `src/data/collect_technology_trade.py`
- Global runner: `src/data/run_global_technology_trade.py`
- Development notebook: `notebooks/17_technology_trade_development.ipynb`
- Transition notebook: `notebooks/18_technology_transition_pilot.ipynb`
- Outputs: `outputs/tables/technology/`

### Reopening triggers

Revisit if TiVA releases alter ratios materially, 2023-2024 observed ratios become available, reduced 2024 coverage changes substantive conclusions, equal-category results become preferred, product definitions change, or the technology pillar is broadened beyond ICT goods trade.

## Final four-pillar US-China Closeness Index

- **Status:** Provisional production design; benchmark selection pending final sensitivity review
- **Date:** 5 November 2026
- **Owner:** Darren

### Decision

Assemble the final index from four completed top-level pillars:

1. `security_score`;
2. `diplomatic_score`;
3. `economic_score`; and
4. `technology_score`, using `dva_adjusted_orientation_score` as the initial baseline technology input.

Do not separately reweight indicators already integrated within a pillar.

Use the common sign convention:

- positive = closer to the United States;
- negative = closer to China;
- zero = balanced.

Retain two analytical formulations during final validation:

1. **Strict equal-weight benchmark:** 25% per pillar and calculated only when all four pillars are observed.
2. **Available-pillar formulation:** equal requested weights, renormalised over observed pillars, with at least three pillars required.

Do not zero-fill a missing pillar. Record available-pillar count, missing pillars, requested-weight coverage, effective row-specific weights and calculation status.

### Dashboard weighting contract

Allow users to select non-negative pillar weights through sliders. Normalise selected weights automatically:

`normalised_weight = selected_weight / sum(selected_weights)`

If all selected weights are zero, do not calculate a score. Where a pillar is unavailable, renormalise over available pillars and display the effective weights. Keep the official benchmark distinct from the user-selected scenario. User-selected scores do not replace the official index.

### Relationship-condition integration

Attach anchor-specific relationship-condition fields to dashboard-ready data but do not treat relationship condition as a fifth pillar or modify the numerical index.

### Initial development validation

The development notebook assembled:

- 4,014 country-year rows for 2004-2024;
- 192 source identifiers before final eligibility filtering;
- 3,306 complete four-pillar observations;
- 3,564 observations with at least three pillars; and
- no duplicate country-year keys.

The final production builder must apply the canonical baseline-eligibility rule before publication so that excluded special entities and anchor states do not appear in the headline index.

### Development artefact

- Notebook: `notebooks/19_final_us_china_closeness_index.ipynb`

### Open decisions

- select the official headline formulation after coverage and sensitivity review;
- confirm the canonical production output path and build a stable production builder;
- decide final publication treatment for three-pillar observations;
- select categorical thresholds only after validating the continuous score; and
- complete final dashboard evidence-status treatment.

### Reopening triggers

Revisit if a pillar definition changes, missing-pillar treatment materially alters results, alternative weights materially alter the headline interpretation, the baseline entity universe changes, or the dashboard requires another official scenario.

## Incomplete latest-year data

- **Status:** Provisional project-wide default
- **Date:** 3 November 2026
- **Owner:** Darren

### Decision

Use 2004-2024 as the complete-data baseline. Retain 2025 observations for continuity and future updates, but treat 2025 as provisional wherever required inputs are incomplete or not comparable.

Do not apply available-component renormalisation automatically to a new pillar or the final composite without reviewing the specific source coverage and implications. Exclude 2025 from claims requiring constant composition until complete and validated coverage exists.
