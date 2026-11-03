## Total merchandise-trade component

- **Status:** Decided
- **Date:** 28 September 2026
- **Owner:** Darren
- **Decision:** Use annual UN Comtrade merchandise imports and exports
  with the United States and China. Prioritise country-reported values
  and use the corresponding anchor-reported mirror observation when a
  country-reported flow is unavailable.
- **Score rule:** Calculate the directional trade score only when all
  four required bilateral flows are available.
- **Missing-data rule:** Retain a flow as missing if neither the country
  nor the relevant anchor reports it. Do not replace missing values
  with zero.
- **Anchor rule:** Do not calculate index scores for the United States
  or China.
- **Rationale:** The approach is symmetric, reproducible, transparent,
  historically extensive, and preserves the distinction between zero
  activity and unavailable data.
- **Evidence:** The 2000-2025 pipeline produced 4,301 valid non-anchor
  scores. Mirror supplementation recovered 345 of 409 initially
  missing flows. All eight unit tests passed.
- **Reopening triggers:** Material revisions to Comtrade data,
  sustained gaps for major economies, evidence that mirror use creates
  material bias, emergence of a superior comparable source, or
  evidence that insignificant bilateral amounts produce misleading
  extreme scores.

  ## UNGA source data and indicator construction

**Status:** Decided
**Date:** 18 October 2026

### Decision

The project-specific UNGA source workbooks will be versioned under
`data/sources/unga/`, while `data/raw/` will remain fully ignored.

The source workbooks are accompanied by provenance documentation, United
Nations attribution, SHA-256 checksums, known data-quality limitations, and
the reproducible processing module `src/data/process_unga.py`.

The baseline UNGA indicator includes resolutions where the United States and
China both cast substantive votes and selected different positions. A strict
Yes-versus-No specification is retained as a robustness measure.

For a qualifying resolution:

- matching the United States is scored `+1`;
- matching China is scored `-1`;
- matching neither anchor is scored `0`;
- absence and non-membership are excluded from the country-specific denominator.

Duplicate resolutions and malformed vote observations are identified through
audit outputs rather than silently corrected. Country-year scores, the
country-resolution panel, coverage statistics, anchor-resolution eligibility,
duplicate records, and ingestion exceptions are written to `data/processed/`.

### Rationale

This design measures revealed relative voting orientation when the two anchor
countries differ, while preserving a transparent robustness specification.

Versioning the redistributable source artefacts makes the result reproducible
without weakening the repository rule that `data/raw/` remains local-only and
ignored.

### Reopening triggers

Revisit this decision if:

- the project migrates fully to an official machine-readable UN voting dataset;
- the baseline treatment of anchor abstentions changes;
- participation thresholds materially affect country rankings;
- source redistribution terms change; or
- validation against the published ideal-point measures reveals a major
  construct or processing problem.

### Diplomatic representation source treatment

- **Status:** Decided, superseding the bilateral-observation-only rule
- **Date:** 3 November 2026
- **Owner:** Darren

### Decision

Use the Diplomatic Representation Database as a directed
country-anchor-year source.

Preserve separately:

- representation maintained by the anchor in the country; and
- representation maintained by the country in the anchor.

Use the Level of Representation (`LOR`) as the principal measure of
directed diplomatic depth.

Within a valid entity-year and a year covered by the source, assign zero
recorded structural depth to an absent directed dyad while retaining an
explicit unobserved-direction flag.

This treatment represents no diplomatic representation recorded by the
source. It must not be interpreted as diplomatic rupture, formal
severance or an observed adverse diplomatic condition.

Preserve an observed `LOR = 0` separately as an adverse source
observation. The source groups events such as recall, withdrawal,
expulsion and severance under this value, so it does not necessarily
establish formal legal severance.

Leave the diplomatic structural score missing when the source year is
unavailable, the entity-year is invalid or an unresolved source or
mapping problem prevents a supported interpretation.

Calculate:

`mean_depth = (anchor_to_country_depth + country_to_anchor_depth) / 2`

`reciprocity_depth = min(anchor_to_country_depth, country_to_anchor_depth)`

Use the baseline structural score:

`0.75 * mean_depth + 0.25 * reciprocity_depth`

Retain mean-only, equal mean-reciprocity and geometric specifications as
sensitivity analyses.

### Rationale

The source is directional and records cases in which diplomatic
representation above recognition is reported. Within confirmed source
coverage, an absent directed dyad can therefore be interpreted as zero
recorded structural representation, provided that the absence remains
explicitly distinguishable from an observed adverse `LOR = 0`.

This source-aware treatment preserves genuine unilateral diplomatic
structures and allows the reciprocity term to penalise asymmetric
representation. It avoids the information loss and upward selection
that would result from calculating scores only when both directions are
recorded.

At the same time, it is more conservative than unconditional zero
filling because source-unavailable years, invalid entity-years and
unresolved source problems remain missing.

### Evidence and validation

The revised production workflow uses the corrected baseline entity
universe and validity rules.

Production coverage:

- 8,410 country-anchor-years;
- 192 eligible entities;
- 2004–2025;
- 6,783 bilaterally observed rows;
- 561 unilateral recorded-representation rows;
- 684 rows with no representation recorded in either direction;
- 382 source-year-unavailable rows in 2025;
- 8,028 scored rows;
- 382 missing scores;
- zero duplicate keys;
- zero covered-year missing scores;
- zero source-unavailable rows with scores;
- all non-missing scores within `[0, 1]`; and
- 12 focused production tests passed.

The 75% mean-depth and 25% reciprocity-depth specification remains the
production baseline. Alternative scoring formulas remain sensitivity
outputs.

Production output:

`data/processed/diplomatic_structural_ties_country_anchor_year.csv`

Production builder:

`src/data/build_diplomatic_structural_ties.py`

Focused tests:

`tests/test_diplomatic_structural_ties.py`

### Reopening triggers

Revisit this decision if:

- a revised Diplomatic Representation Database changes the meaning of an
  absent directed dyad;
- source documentation shows that absence cannot reasonably represent no
  recorded structural representation;
- source coverage expands to 2025 or later;
- material mapping or ingestion gaps are identified;
- the `LOR` coding changes materially;
- alternative scoring specifications materially change the final
  composite; or
- another source provides more complete and comparable annual directed
  diplomatic-representation data.


## Diplomatic representation condition signal

- **Status:** Decided
- **Date:** 1 November 2026
- **Owner:** Darren

### Decision

Use the Diplomatic Representation Database separately for:

1. structural diplomatic depth; and
2. explicit adverse diplomatic-condition evidence.

All valid `LOR` observations may affect structural diplomatic depth.
Ordinary non-zero changes in embassy rank, representation level or
mission focus do not, by themselves, generate a strained relationship
condition.

Use the following conservative condition rules:

- one observed direction with `LOR = 0` or `Focus = 3`:
  `severely_strained`;
- both observed directions with explicit adverse coding in the same
  country-anchor-year:
  `ruptured`;
- positive observed representation without explicit adverse coding:
  `normal`;
- neither direction observed:
  `missing`.

Retain rank and focus changes as diagnostic and explanatory fields
rather than treating every downgrade as a relationship-condition event.

### Rupture interpretation

Retain `ruptured` as the highest relationship-condition state.

`Ruptured` means an observed bilateral operational rupture in
diplomatic representation. It does not necessarily establish formal
legal severance because the source groups severance with events such as
recall, withdrawal and expulsion.

The classification remains source-based and reproducible rather than
depending on case-by-case analyst judgement.

### Rationale

Diagnostic testing identified:

- 581 non-zero rank downgrades; and
- 541 rank upgrades

during 2000–2024.

An extended rule treating ordinary rank downgrades as strained would
classify 565 country-anchor-years as strained. Many of those changes
occurred broadly or simultaneously and were more consistent with
appointments, vacancies, administrative changes or source reporting
than with diplomatic crises.

The conservative rule therefore reserves the relationship-condition
signal for explicit adverse source coding.

### Reopening triggers

Revisit this decision if:

- source documentation distinguishes formal severance from recall,
  withdrawal and expulsion;
- validated event evidence shows that some non-zero `LOR` changes
  consistently identify diplomatic crises;
- the source revises `Focus = 3` or `LOR = 0`;
- the operational interpretation of `ruptured` changes; or
- external validation shows substantial false positives or false
  negatives.


## Overall relationship-condition panel

- **Status:** Decided
- **Date:** 1 November 2026
- **Owner:** Darren

### Decision

Construct a symmetric country-anchor-year relationship-condition panel
using the highest supported severity from the available harmonised
evidence.

Use the ordered states:

1. `normal`;
2. `strained`;
3. `severely_strained`;
4. `ruptured`.

Preserve:

- the controlling condition trigger;
- all supporting triggers;
- source-specific evidence;
- missingness;
- historical-entity eligibility; and
- anchor self-relation exclusions.

Apply rupture precedence whenever the source evidence supports the
`ruptured` state.

Do not infer a normal relationship from complete source absence.

### Rationale

The construction separates the relationship condition from the
structural-ties scores. Structural depth can change gradually, whereas
the condition panel records material adverse states supported by
diplomatic, sanctions or other explicitly adverse evidence.

Using the highest supported severity prevents a severe event from being
diluted by normal observations from another source.

### Validation verdict

The production pipeline completed successfully:

- corrected GSDB panel: passed;
- non-state exclusion audit: passed;
- harmonised evidence panel: passed;
- DRD country resolution: passed;
- historical-entity validation: passed;
- symmetric production grid: passed;
- four-state classifier: passed;
- trigger preservation: passed; and
- rupture precedence: passed.

Production output:

`data/processed/relationship_condition_country_anchor_year.csv`

### Reopening triggers

Revisit this decision if:

- the sanctions persistence rule changes;
- an additional condition source is incorporated;
- new evidence changes the ordering of condition severity;
- external validation reveals systematic classification errors;
- historical-entity validity rules change; or
- the project adopts a probabilistic rather than categorical condition
  model.


## Bilateral investment-treaty ties

- **Status:** Decided
- **Date:** 1 November 2026
- **Owner:** Darren

### Decision

Use the bilateral investment-treaty source workbooks for China and the
United States to construct annual country-anchor-year treaty states.

## Baseline entity universe and historical eligibility

- **Status:** Decided
- **Date:** 3 November 2026
- **Owner:** Darren

### Decision

Use the corrected canonical country master to control entity eligibility
for the baseline index.

Retain source-level observations for all available reporting entities,
but exclude the following special, non-sovereign, de facto, partially
recognised or policy-dependent entities from the baseline headline
index for the current delivery:

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

Mark the following legacy codes as historical entities outside the
baseline project window:

- Byelorussian SSR;
- Czechoslovakia;
- German Democratic Republic;
- Dahomey;
- Upper Volta;
- Rhodesia;
- Soviet Union;
- North Vietnam; and
- Yugoslavia.

Retain Serbia and Montenegro (`SCG`) only within its recorded validity
interval. Within the 2004-2025 Security Institutional panel, this means
eligibility in 2004-2006 only.

Use `preferred_country_name` for modern display labels without replacing
the established `country_name` field used by existing crosswalks.

### Rationale

The policy distinguishes source reporting from baseline-index
eligibility. It preserves available observations without requiring the
current delivery to resolve every sovereignty, recognition or territory
question.

Year-conditioned historical eligibility prevents obsolete entities from
being treated as current for the entire panel while retaining valid
observations where a historical entity overlaps the project period.

### Validation verdict

The corrected canonical master contains:

- 213 entities;
- 191 sovereign-state rows;
- 10 historical-state rows;
- 10 special or policy-dependent rows; and
- 2 anchor-state rows.

The correction audit records 28 changed or policy-affected entities.
The Security Institutional production panel contains `SCG` only in
2004-2006.

### Reopening triggers

Revisit this decision if:

- the project has sufficient time to evaluate special entities across
  all component sources;
- the baseline headline universe is expanded beyond sovereign states;
- an established component requires a different historical validity
  rule; or
- a final assessment instruction prescribes a different entity universe.


## Security institutional ties

- **Status:** Decided
- **Date:** 3 November 2026
- **Owner:** Darren

### Decision

Construct an annual country-anchor-year Security Institutional component
from a verified, normalized membership register rather than directly
from the original wide treaty workbook.

Use the following institutional-depth hierarchy:

1. depth `1`: structured security participation without a binding
   mutual-defence obligation;
2. depth `2`: formal and durable security cooperation without a full
   mutual-defence commitment; and
3. depth `3`: binding mutual-defence, collective-defence or military-
   assistance commitment.

For each country-anchor-year, use the highest verified active depth and
calculate:

`security_institutional_score_raw = maximum_depth / 3`

Retain all supporting arrangements, relationship types and controlling
arrangements for audit. Do not add overlapping arrangements in the
baseline score.

Baseline arrangement treatment includes:

- NATO membership at depth `3` using official accession years;
- the Rio Treaty at depth `3` using verified effective membership
  spells;
- Major Non-NATO Ally status at depth `2`, elevated to depth `3` only
  where a separate mutual-defence treaty supports alliance depth;
- Five Eyes at depth `2`;
- AUKUS at depth `2` from 2021;
- the Quad at depth `1` for 2007-2008 and from 2017 onward;
- US-India GSOMIA at depth `2`;
- the China-DPRK Treaty of Friendship, Cooperation and Mutual
  Assistance at depth `3`;
- full Shanghai Cooperation Organisation membership at depth `1`, with
  observer and dialogue-partner statuses excluded; and
- the China-Solomon Islands Security Cooperation Framework at depth `2`
  from 2022.

Retain the Rio Treaty at depth `2` as a sensitivity specification
because its legal collective-defence commitment is less operationally
integrated than NATO. Descriptive commitment and integration fields may
support interpretation and later sensitivity analysis but do not enter
the baseline numerical score.

### Rationale

Institutional depth measures the strength of formal commitment without
allowing multiple labels for the same security relationship to generate
an artificial score above alliance level.

The hierarchy is anchor-neutral. It preserves the substantive
asymmetry between the dense United States alliance network and China's
preference for fewer alliances and more flexible, non-bloc security
partnerships.

The verified register corrects material errors in the original workbook,
including NATO accession timing, an erroneous Honduras NATO entry,
reversed Rio Treaty withdrawal periods, Quad phases, the AUKUS start
year, omitted Major Non-NATO Allies, and missing China-linked formal
security cooperation.

### Validation verdict

The production builder completed successfully:

- production rows: 8,410;
- rows per anchor: 4,205;
- verified annual evidence rows: 1,659;
- verified membership spells: 96;
- arrangement families: 10;
- duplicate country-anchor-year keys: 0;
- score range and permitted values: passed;
- anchor self-relation exclusion: passed;
- special-entity exclusion: passed;
- historical-year eligibility: passed;
- validated-notebook candidate reproduction: passed; and
- focused production tests: 5 passed.

Production output:

`data/processed/security_institutional_ties_country_anchor_year.csv`

Production builder:

`src/data/build_security_institutional_ties.py`

### Reopening triggers

Revisit this decision if:

- the Rio Treaty sensitivity materially changes the final composite;
- additional verified Chinese formal security agreements are added;
- the project adopts a two-dimensional legal-commitment and operational-
  integration score;
- the baseline entity universe changes;
- SIPRI integration indicates that institutional depth is being double-
  counted; or
- source revisions alter arrangement membership spells.


## Security arms-transfer ties

- **Status:** Decided
- **Date:** 3 November 2026
- **Owner:** Darren

### Decision

Construct an annual country-year Security Arms Transfers component from SIPRI
major-arms transfer TIV data. Use five-year rolling sums and calculate the
baseline score as:

`arms_transfer_score = (us_tiv_5yr - china_tiv_5yr) / global_tiv_5yr`

Use the complete 1996-2025 source history for rolling calculations and retain
2004-2025 as the production period.

Retain the following diagnostics without treating them as separate index
components:

- `direction_score = (us_tiv_5yr - china_tiv_5yr) / anchor_tiv_5yr`;
- `anchor_exposure_raw = anchor_tiv_5yr / global_tiv_5yr`;
- `anchor_tiv_5yr`;
- `low_volume_flag`; and
- `observation_status`.

Treat empty SIPRI annual cells as zero identified deliveries. Represent a
displayed SIPRI `0`, which denotes a positive value below 0.5 million TIV, by
the midpoint `0.25` in the baseline specification. Retain `0` and `0.5`
substitutions as sensitivity specifications.

Use the canonical relationship-condition country master for mapping,
baseline eligibility and historical-year validity. Remove source-marked armed
groups, organisations, totals and unknown recipients from state-level
processing, while preserving policy-dependent geographic entities for
country-master treatment.

Assign:

- a score of `0` when global arms imports are observed but neither anchor
  supplied arms during the rolling window; and
- a missing score when no global arms imports were identified during the
  rolling window.

Retain the 100-TIV low-volume threshold only as a provisional diagnostic. It
does not alter, suppress or weight the baseline score.

### Rationale

The anchor-only directional measure,
`(us_tiv_5yr - china_tiv_5yr) / anchor_tiv_5yr`, answers which anchor
predominates conditional on anchor procurement. Used alone, it can assign an
extreme score to a negligible anchor transfer when most arms imports come
from other suppliers.

Normalising the net anchor difference by global imports measures material
alignment rather than conditional direction alone. Algebraically, the
baseline score equals pure direction multiplied by collective anchor
exposure. This preserves direction while attenuating relationships that are
small within the recipient's overall procurement.

Five-year rolling sums reduce volatility from irregular delivery schedules
and better represent sustained procurement orientation than annual flows.
The 1996 source start provides complete pre-period history for all production
years beginning in 2004.

A score of zero when neither anchor supplied observed global imports means
that neither anchor has a material arms-transfer advantage in that window.
A missing score when no global imports were identified avoids treating absence
of an observed arms-import relationship as neutral alignment.

### Validation verdict

The production builder completed successfully:

- source period: 1996-2025;
- production period: 2004-2025;
- rolling window: 5 years;
- production rows: 4,205;
- production entities: 192;
- non-missing baseline scores: 3,262;
- `available` rows: 2,329;
- `no_observed_anchor_transfers` rows: 933;
- `no_observed_arms_imports` rows: 943;
- duplicate ISO3-year keys: 0;
- unmapped state-like recipient names: 0;
- exposure violations: 0;
- baseline score range: within `[-1, 1]`; and
- focused production tests: 8 passed.

The 100-TIV diagnostic flags 58.8% of scored country-years and is therefore
not adopted as an exclusion, weighting or confidence rule. Displayed-zero
sensitivity affects a small minority of country-years but can materially
affect some very low-volume cases; the midpoint treatment and sensitivity
audit are retained.

Production output:

`data/processed/sipri_arms_country_year.csv`

Production builder:

`src/data/build_sipri_arms_transfers.py`

Development notebook:

`notebooks/13_security_arms_transfers_development.ipynb`

### Reopening triggers

Revisit this decision if:

- SIPRI revises source values or reporting conventions;
- displayed-zero sensitivity materially changes the final composite;
- a different rolling window is selected;
- the baseline entity universe changes;
- low volume is proposed as a formal exclusion or weighting rule;
- security-component integration indicates material double-counting between
  arms transfers and institutional ties; or
- the overall index adopts a different rule for structurally unavailable
  component scores.

## Security subindex integration

**Status: Decided**

Adopt equal conceptual weights for institutional-security ties and arms-transfer ties when both are observed. The production score is the arithmetic mean of the institutional signed score and SIPRI arms-transfer score.

When SIPRI reports `no_observed_arms_imports`, treat the arms component as structurally unavailable and renormalise to the institutional score. Do not zero-fill unavailable arms evidence. When SIPRI reports `no_observed_anchor_transfers`, retain the observed arms score of zero at half-weight.

The equal-weight baseline is retained because the components represent distinct structural and operational concepts, no compelling theoretical basis currently favours one, and one-third/two-thirds sensitivity specifications leave results highly correlated with the baseline with few directional changes. Alternative weights and zero-fill treatment remain audit sensitivities rather than production fields.

Production output:

`data/processed/security_subindex_country_year.csv`

Production builder:

`src/data/build_security_subindex.py`

Development notebook:

`notebooks/14_security_subindex_integration.ipynb`

### Reopening triggers

Revisit this decision if the final composite displays material sensitivity to security-component weights, component availability rules change across the index, the institutional or SIPRI method changes, or evidence emerges that the two security components materially double-count the same underlying relationship.

## Incomplete latest-year data

- **Status:** Provisional project-wide default
- **Date:** 3 November 2026
- **Owner:** Darren

### Decision

Use 2004–2024 as the complete-data baseline period for the current
edition of the US–China Closeness Index.

Retain 2025 observations where available to support continuity, source
monitoring and future updates, but treat 2025 as a provisional extension
whenever one or more required components lack complete and comparable
coverage.

Where a 2025 component is structurally unavailable, the likely default
is to calculate a clearly flagged available-component score rather than
zero-fill the missing component. This provisional treatment must not be
presented as directly comparable with the complete-data baseline period.

Do not apply this rule automatically to a new component or to the final
composite. Confirm the proposed treatment with Darren after reviewing the
specific source coverage and implications.

### Reporting rule

Unless subsequently decided otherwise:

- baseline estimation, validation and substantive trend analysis use
  2004–2024;
- 2025 is presented separately as provisional;
- 2025 values are excluded from claims requiring consistent component
  composition across years; and
- the provisional flag is removed only after all required sources have
  complete and validated 2025 coverage.

### Reopening triggers

Revisit this decision when:

- complete 2025 data become available for all required components;
- the final index adopts a different latest-year publication policy;
- available-component renormalisation materially distorts 2025 scores or
  rankings; or
- a component-specific source requires a different treatment.

## Incomplete latest-year data

- **Status:** Provisional project-wide default
- **Date:** 3 November 2026
- **Owner:** Darren

### Decision

Use 2004–2024 as the complete-data baseline period for the current
edition of the US–China Closeness Index.

Retain 2025 observations where available to support continuity, source
monitoring and future updates, but treat 2025 as a provisional extension
whenever one or more required components lack complete and comparable
coverage.

Where a 2025 component is structurally unavailable, the likely default
is to calculate a clearly flagged available-component score rather than
zero-fill the missing component. This provisional treatment must not be
presented as directly comparable with the complete-data baseline period.

Do not apply this rule automatically to a new component or to the final
composite. Confirm the proposed treatment with Darren after reviewing
the specific source coverage and implications.

### Reporting rule

Unless subsequently decided otherwise:

- baseline estimation, validation and substantive trend analysis use
  2004–2024;
- 2025 is presented separately as provisional;
- 2025 values are excluded from claims requiring consistent component
  composition across years; and
- the provisional flag is removed only after all required sources have
  complete and validated 2025 coverage.

### Reopening triggers

Revisit this decision when:

- complete 2025 data become available for all required components;
- the final index adopts a different latest-year publication policy;
- available-component renormalisation materially distorts 2025 scores or
  rankings; or
- a component-specific source requires a different treatment.

## Diplomatic subindex integration

- **Status:** Decided
- **Date:** 3 November 2026
- **Owner:** Darren

### Decision

Combine signed diplomatic structural ties and broad UN General Assembly
voting alignment with equal conceptual weights when both components are
available.

The signed structural score is:

`United States structural score - China structural score`

When both components are available:

`diplomatic_score = 0.5 * structural_score + 0.5 * UNGA_score`

When only one component is available, renormalise to the available
component. Do not zero-fill an unavailable component. When neither
component is available, retain a missing diplomatic score.

Use 2004–2024 as the comparable complete-data baseline period. Retain
2025 only as a clearly flagged provisional extension because the
diplomatic-representation source currently ends in 2024.

Retain provisionally insufficient UNGA participation in the baseline
with participation status and rate preserved. Retain exclusion of those
observations as a formal sensitivity.

Use the broad UNGA specification as the baseline and retain the strict
Yes-versus-No specification as a robustness measure.

Retain one-third/two-thirds component-weight specifications as prominent
sensitivities because component weighting materially affects some
directions and rankings.

Keep relationship condition as a contextual layer rather than inserting
it numerically into the diplomatic subindex.

### Production artefacts

Production output:

`data/processed/diplomatic_subindex_country_year.csv`

Production builder:

`src/data/build_diplomatic_subindex.py`

Development notebook:

`notebooks/15_diplomatic_subindex_integration.ipynb`

Focused tests:

`tests/test_diplomatic_subindex.py`

### Reopening triggers

Revisit this decision if:

- complete and validated diplomatic-representation data become available
  for 2025;
- the final composite adopts a different latest-year policy;
- alternative component weights materially affect the final composite;
- UNGA participation treatment materially changes final rankings;
- either component undergoes a methodological revision; or
- relationship condition is proposed as a numerical diplomatic input.

### Canonical production validation

The regenerated UN Comtrade panel is mapped to the corrected baseline
entity universe through a separate canonical production builder.

The production panel contains:

- 4,205 country-years;
- 192 eligible entities;
- 2004–2025;
- 3,465 complete four-flow scores;
- 723 country-years with no source row;
- 17 source rows with incomplete bilateral flows;
- 3,332 scores using four reporter-side observations;
- 133 scores using one or more mirror-side recoveries;
- 740 missing scores;
- no duplicate keys;
- no scores without all four required flows; and
- all non-missing scores within `[-1, 1]`.

Use 2004–2024 as the comparable baseline period. Retain 2025 only as a
provisional extension, with 122 available scores and 69 unavailable
scores.

Interpret provenance labels as reporter-side and mirror-side rather than
as definitive claims about the meaning of UN Comtrade's `isReported`
metadata. Preserve the underlying Comtrade metadata in acquisition
audits.

Production output:

`data/processed/trade_orientation_country_year.csv`

Production builder:

`src/data/build_trade_orientation.py`

Focused tests:

`tests/test_trade_orientation.py`

## FDI structural ties

- **Status:** Decided
- **Date:** 3 November 2026
- **Owner:** Darren

### Decision

Use IMF Direct Investment Positions to measure each anchor's outward
direct-investment position in each eligible country.

Use only:

- anchor-reported observations;
- anchor-to-country economic direction;
- reported official data;
- China and the United States as anchors; and
- 2018–2024 as the comparable FDI source period.

Exclude country-reported inward positions and values derived using
counterparty information from the baseline.

For each anchor-year, calculate the positive-position intensity as:

1. `log1p(outward position)`;
2. divide by the anchor-year 95th percentile of positive logged
   positions; and
3. cap the score at one.

Assign zero structural intensity to an observed zero position or an
observed negative net position.

Leave the score missing when the official outward position is
unobserved. Do not convert missing positions to zero.

Map IMF legal-form country names explicitly to the canonical project
country master. Exclude aggregates, territories, anchors and
baseline-ineligible entities.

Retain the full 2004–2025 canonical panel, but leave:

- 2004–2017 as pre-FDI-source-period unavailable; and
- 2025 as provisional latest-year source unavailable.

### Rationale

The method uses a consistent anchor-reported outward-investment
perspective and preserves the distinction between:

- positive investment intensity;
- an observed zero position;
- an observed negative net position; and
- an unavailable official position.

The logarithmic transformation limits domination by very large
positions. Anchor-year 95th-percentile scaling produces a bounded
relative-intensity score while reducing sensitivity to extreme values.

### Production validation

The canonical production panel contains:

- 8,410 country-anchor-years;
- 192 eligible entities;
- 2004–2025;
- 2,467 scored observations during 2018–2024;
- 207 unobserved official positions during 2018–2024;
- 2,173 observed positive positions;
- 240 observed zero positions;
- 54 observed negative net positions;
- 5,736 source-year-unavailable rows;
- no duplicate keys;
- no scores outside the comparable source period;
- no scores without an observed position; and
- all non-missing scores within `[0, 1]`.

Production output:

`data/processed/fdi_structural_ties_country_anchor_year.csv`

Production builder:

`src/data/build_fdi_structural_ties.py`

Focused tests:

`tests/test_fdi_structural_ties.py`

Crosswalk audit:

`outputs/tables/fdi/fdi_country_crosswalk_production_audit.csv`

### Reopening triggers

Revisit this decision if:

- comparable official Chinese outward-position data become available
  before 2018 or after 2024;
- revised IMF data materially change coverage or positions;
- the treatment of negative net positions requires reconsideration;
- a different scaling rule materially changes the economic subindex;
- repaired country mappings are shown to be incorrect; or
- another source provides more complete and comparable bilateral FDI
  positions.

  ## Economic institutional ties

- **Status:** Decided
- **Date:** 3 November 2026
- **Owner:** Darren

### Decision

Combine trade-agreement ties and bilateral investment-treaty ties as:

`economic_institutional_score
    = 0.75 * trade_agreement_score
    + 0.25 * BIT_score`

The trade-agreement score uses:

- 60% bilateral FTA;
- 35% regional trade agreement; and
- 5% sectoral trade agreement.

The effective family weights are therefore:

- bilateral FTA: 0.4500;
- regional trade agreement: 0.2625;
- sectoral trade agreement: 0.0375; and
- BIT: 0.2500.

Treat absence from the exhaustive agreement registers as a valid zero
institutional state, not as unavailable evidence. Preserve BIT states
as `none`, `historical_terminated`, `signed_not_in_force`, or
`in_force`.

Use directly reconstructed register states for 2004–2024.

Analyst review found no establishment, entry into force, termination,
replacement, or other change in the relevant trade-agreement or BIT
states during 2025. Carry the validated 31 December 2024 states into
2025 and label those rows `verified_unchanged_carry_forward`.

This carry-forward is limited to 2024–2025. Do not extend it
automatically to later years.

### Production validation

The canonical panel contains:

- 8,410 country-anchor-years;
- 192 eligible entities;
- 8,028 directly reconstructed rows;
- 382 verified-unchanged 2025 rows;
- no missing component scores;
- no missing BIT states;
- no duplicate keys;
- no score-bound or formula failures; and
- no 2024-to-2025 carry-forward mismatches.

Production output:

`data/processed/economic_institutional_ties_country_anchor_year.csv`

Production builder:

`src/data/build_economic_institutional_ties.py`

Focused tests:

`tests/test_economic_institutional_ties.py`

### Reopening triggers

Revisit this decision if:

- later evidence identifies a 2025 treaty-state change;
- the underlying trade-agreement or BIT registers are revised;
- alternative institutional weights materially change the economic
  subindex;
- the interpretation of an absent register state changes; or
- the index adopts a different treatment of verified carry-forward data.