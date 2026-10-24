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