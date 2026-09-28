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