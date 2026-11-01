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

### Diplomatic representation treatment

**Status:** Provisional
**Date:** 24 October 2026

The Diplomatic Representation Database will be used as a directed
country-anchor-year source. Representation maintained by an anchor in a
country and representation maintained by that country in the anchor will
be preserved separately.

The Level of Representation index (`LOR`) will be the principal
diplomatic-representation measure. The baseline bilateral representation
depth will be calculated only when both directions are observed. A
one-direction-only relationship will retain its directional observation,
but the missing direction will not be assigned zero or imputed.

An absent directed dyad-year will be treated as missing or no recorded
representation, rather than evidence of diplomatic rupture.

Observed annual representation states will apply in the year recorded.
`LOR` values will be grouped into substantive representation bands. A
fall of at least two bands will provisionally constitute a material
diplomatic downgrade.

A unilateral `LOR = 0` record will generate a severely strained
diplomatic-condition signal. Bilateral `LOR = 0` records in the same year
will generate a ruptured diplomatic-condition signal.

Diplomatic representation will remain separate from the overall
relationship condition. The final condition will later combine
source-specific signals, including diplomatic representation and
sanctions, using the highest supported severity.

The treatment of reciprocal one-band downgrades, one-direction-only
estimates, downgrade thresholds, sanctions persistence, and structural
family weights remains subject to empirical testing.

### Diplomatic representation condition signal

**Status:** Provisional baseline
**Date:** 26 October 2026

The Diplomatic Representation Database will contribute separately to
structural diplomatic depth and relationship condition.

Annual Level of Representation (`LOR`) values will measure directed
diplomatic depth. Both country-to-anchor and anchor-to-country records
will be retained. A bilateral mean will be calculated only when both
directions are observed. An unobserved direction will remain missing
rather than being assigned zero.

All valid `LOR` changes may affect structural diplomatic depth. However,
ordinary non-zero changes in embassy rank or mission focus will not
generate a strained relationship condition. Diagnostic testing found
581 non-zero rank downgrades and 541 rank upgrades during 2000–2024.
An extended rank-downgrade rule would classify 565 country-anchor-years
as strained, including broad simultaneous changes that are more
consistent with appointments, vacancies, administrative arrangements,
or source reporting than diplomatic crises.

The conservative DRD condition will therefore use explicit adverse
coding only:

- one observed direction with `LOR = 0` or `Focus = 3`:
  `severely_strained`;
- both observed directions with explicit adverse coding:
  `ruptured`;
- positive observed representation without explicit adversity:
  `normal`;
- neither direction observed:
  `missing`.

The `strained` category will principally be determined from sanctions
and other material adverse measures. Rank and focus changes will remain
available as diagnostic and explanatory fields.

**Decided:** Retain `ruptured` as the highest relationship-condition
state.

`Ruptured` means bilateral operational rupture of diplomatic
representation, identified when both directed DRD observations have
explicit adverse coding in the same country-anchor-year. It does not
necessarily establish formal legal severance because the DRD source
groups severance with recall, withdrawal, and expulsion.

The classification is intentionally operational and source-based so that
it remains reproducible without case-by-case analyst intervention.

# Final run verdict

The relationship-condition production pipeline completed successfully.

- Corrected GSDB panel: passed
- Non-state exclusion audit: passed
- Harmonised evidence panel: passed
- DRD country resolution: passed
- Historical-entity validation: passed
- Symmetric production grid: passed
- Four-state classifier: passed
- Trigger preservation: passed
- Rupture precedence: passed

Final production output:

`data/processed/relationship_condition_country_anchor_year.csv`
