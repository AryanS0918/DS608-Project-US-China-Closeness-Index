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

## Diplomatic representation source treatment

- **Status:** Decided
- **Date:** 1 November 2026
- **Owner:** Darren

### Decision

Use the Diplomatic Representation Database as a directed
country-anchor-year source.

Preserve separately:

- representation maintained by the anchor in the country; and
- representation maintained by the country in the anchor.

Use the Level of Representation (`LOR`) as the principal measure of
directed diplomatic depth.

Calculate a bilateral diplomatic-representation measure only when both
directed observations are available. Do not assign zero to an
unobserved direction and do not impute the missing direction.

Treat an absent directed dyad-year as missing or as no recorded
representation. Do not interpret an absent record by itself as evidence
of diplomatic rupture.

### Rationale

Diplomatic representation is directional. Preserving both directions
prevents the analysis from treating unilateral and reciprocal
representation as equivalent.

Keeping missing directions distinct from observed zero-valued adverse
coding also prevents source non-observation from being interpreted as a
diplomatic crisis.

### Evidence

The diplomatic-representation development workflow:

- preserved the two directed observations separately;
- audited one-direction-only cases;
- examined changes in `LOR`, representation rank and mission focus;
- separated structural diplomatic depth from adverse relationship
  conditions; and
- produced a validated country-anchor-year diplomatic structural-ties
  panel.

Production output:

`data/processed/diplomatic_structural_ties_country_anchor_year.csv`

### Reopening triggers

Revisit this decision if:

- a revised Diplomatic Representation Database changes the interpretation
  of missing directed observations;
- evidence shows that one-direction-only cases can be combined without
  imposing an unsupported zero or imputation;
- the `LOR` coding changes materially; or
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
