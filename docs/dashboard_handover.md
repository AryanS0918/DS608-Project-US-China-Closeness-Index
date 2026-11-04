# US-China Closeness Index Dashboard Handover

**Prepared:** 5 November 2026  
**Project owner:** Darren  
**Repository:** `DS608-Project-US-China-Closeness-Index`  
**Primary comparable period:** 2004-2024

## 1. Purpose

The dashboard should let users explore country-year orientation between the United States and China through:

- the overall US-China Closeness Index;
- four pillar scores;
- anchor-specific relationship conditions;
- user-selected pillar weights; and
- transparent availability, comparability and evidence status.

The dashboard is a presentation and scenario-exploration layer. It must not silently change the official methods or overwrite the benchmark index.

## 2. Core sign convention

The entire dashboard must use one direction convention:

- positive score = closer to the United States;
- negative score = closer to China;
- zero = balanced;
- score range = `[-1, 1]`.

Do not reverse the technology scores. The corrected technology production output now follows the same US-minus-China convention as the other pillars.

Use a fixed, symmetric diverging colour scale centred exactly at zero. Do not rescale colours independently by year.

## 3. Four pillars

The final index is assembled from:

1. `security_score`;
2. `diplomatic_score`;
3. `economic_score`; and
4. `technology_score`.

The initial technology input is `dva_adjusted_orientation_score` from `data/processed/technology_trade_country_year.csv`.

Do not decompose and independently reweight the internal indicators already combined inside the security, diplomatic and economic pillars unless the project owner explicitly requests an advanced sensitivity view.

## 4. Official benchmark and scenario scores

Keep two concepts visually and semantically separate:

- **Official benchmark index**
- **User-weighted scenario**

The default requested weights are:

- security: 25%;
- diplomatic: 25%;
- economic: 25%;
- technology: 25%.

The notebook currently retains:

- a strict four-pillar equal-weight score; and
- an available-pillar score requiring at least three pillars and renormalising weights over observed pillars.

The official headline choice remains provisional until final coverage and sensitivity review. Do not label the available-pillar formulation as the definitive official index without that decision.

## 5. Slider behaviour

Provide one non-negative slider for each pillar. A practical range is 0-100.

Normalise user selections automatically:

`normalised_weight = selected_weight / sum(selected_weights)`

Therefore, `40, 30, 20, 10` and `0.4, 0.3, 0.2, 0.1` are equivalent.

Required controls and displays:

- four pillar sliders;
- reset-to-equal-weights button;
- displayed selected weight for each pillar;
- displayed normalised weight for each pillar;
- total selected weight;
- clear error if all four sliders are zero; and
- an explicit label that the resulting score is a user-selected scenario.

Recommended behaviour: sliders do not need to be mechanically constrained to sum to 100, because automatic normalisation is simpler and less frustrating for users.

## 6. Missing-pillar behaviour

Never replace a missing pillar with zero.

For a country-year with one missing pillar:

- require at least three available pillars;
- renormalise selected weights over available pillars;
- display the missing pillar;
- display effective row-specific weights;
- flag the score as renormalised; and
- distinguish it from a complete four-pillar observation.

Do not calculate a score where fewer than three pillars are available under the current development rule.

The dashboard should expose:

- `available_pillar_count`;
- `missing_pillars`;
- `requested_weight_coverage`;
- effective security weight;
- effective diplomatic weight;
- effective economic weight;
- effective technology weight; and
- `index_status`.

## 7. Relationship-condition overlay

Relationship condition is not a fifth pillar and must not change the numerical index.

Show the condition toward each anchor separately:

- United States relationship condition;
- China relationship condition;
- severity;
- controlling trigger;
- contributing triggers;
- combined evidence profile; and
- evidence or merge status.

Use the ordered states:

1. `normal`;
2. `strained`;
3. `severely_strained`;
4. `ruptured`.

Display condition using symbols, badges or a separate palette rather than the same colour scale used for index orientation.

A normal condition means no qualifying adverse condition controls the classification within the supported evidence framework. It does not mean positive closeness.

The selected condition must follow the selected year. Describe it as current only when the user has selected the latest supported year.

## 8. Evidence-status requirement

The dashboard must distinguish:

- directly evidenced conditions;
- normal states supported by the evidence framework;
- opposite-anchor rows created through symmetric grid completion; and
- unsupported or incomplete observations.

Do not show these categories as equally evidenced. Use the existing evidence fields where adequate and add a display status if necessary.

## 9. Time treatment

Use 2004-2024 as the principal comparable period.

Do not present 2025 as fully comparable. If 2025 is added later, mark it clearly as provisional and keep it separate from claims requiring constant component composition.

Technology-specific caveats:

- TiVA ratios are directly observed through 2022;
- 2023 and 2024 use carried-forward TiVA ratios and must be flagged;
- 2024 also has reduced reporter coverage.

Economic-period caveats:

- 2004-2008 are before FDI source availability;
- 2009-2017 include the host-official FDI historical extension;
- 2018-2024 are the fixed-regime common period.

## 10. Eligibility and geography

The production dashboard must apply the canonical baseline entity universe.

Exclude anchor self-relations and policy-excluded special entities from the headline index. Historical entities must be shown only within valid years. In particular, `SCG` is eligible only during 2004-2006.

Do not infer eligibility from names alone. Use the canonical country master and established validity fields.

## 11. Recommended views

### Global map

- Year selector
- Official benchmark or user scenario selector
- Fixed `[-1, 1]` colour scale
- Missing data shown distinctly
- Tooltip with overall score, four pillar scores, availability and relationship conditions

### Country profile

- Overall score through time
- Four pillar lines or small multiples
- Relationship-condition transition markers
- Coverage and comparability flags
- User-selected versus official benchmark comparison

### Pillar comparison

- Selected country-year pillar bars
- Zero-centred axis
- Exact values and availability status
- Optional technology sensitivity selector for pooled versus equal-category measures

### Weight explorer

- Four sliders
- Reset button
- Official benchmark displayed alongside the scenario
- Effective weights and missing-pillar warnings
- Optional ranking-change and score-change displays

### Method and coverage panel

- Sign convention
- 2004-2024 comparable period
- 2023-2024 technology caveats
- score-status definitions
- relationship-condition interpretation
- link or expandable text for methodology notes

## 12. Data contract

The primary calculation inputs are:

- country ISO3;
- preferred country name;
- year;
- `security_score`;
- `diplomatic_score`;
- `economic_score`;
- `technology_score`;
- availability fields;
- comparability fields; and
- anchor-specific relationship-condition fields.

The dashboard must calculate user scenarios from full-precision pillar values, not rounded display values.

Recommended output structures from `notebooks/19_final_us_china_closeness_index.ipynb`:

- wide country-year table for maps, profiles and tooltips;
- long country-year-pillar table for component views;
- coverage-by-year table; and
- metadata describing sign convention, default weights, minimum available pillars and relationship-condition role.

The final canonical production paths are not yet settled. Coordinate with Darren before introducing a new directory or duplicating production files.

## 13. Current repository artefacts

Relevant artefacts include:

- `data/processed/security_subindex_country_year.csv`
- `data/processed/diplomatic_subindex_country_year.csv`
- `data/processed/economic_subindex_country_year.csv`
- `data/processed/technology_trade_country_year.csv`
- `data/processed/tiva_technology_anchor_year.csv`
- `data/processed/relationship_condition_country_anchor_year.csv`
- `notebooks/19_final_us_china_closeness_index.ipynb`
- `docs/decision_register.md`

The technology development and diagnostics are in:

- `notebooks/17_technology_trade_development.ipynb`
- `notebooks/18_technology_transition_pilot.ipynb`
- `outputs/tables/technology/`

## 14. Decisions still requiring Darren

Do not silently decide the following:

1. Which analytical formulation becomes the official headline index.
2. Whether three-pillar renormalised observations appear in the headline map or only as flagged extensions.
3. The final canonical production output path for the composite index.
4. The final categorical thresholds, including whether Jenks natural breaks are used.
5. Whether the technology sensitivity selector is included in the first dashboard release.
6. Whether 2025 is displayed at all in the current release.

## 15. Prohibited interpretations

Do not:

- treat missing as zero;
- reverse the sign convention;
- treat relationship condition as a numerical index input;
- describe `normal` relationship condition as positive closeness;
- use year-specific colour rescaling;
- call a user-weighted scenario the official index;
- present 2025 as fully comparable;
- infer entity eligibility or reporter mappings; or
- average all technology sensitivity variants together.

## 16. Immediate dashboard-team starting sequence

1. Pull the merged `main` branch.
2. Open and run `notebooks/19_final_us_china_closeness_index.ipynb`.
3. Verify the four pillar fields and relationship-condition fields.
4. Implement the fixed equal-weight benchmark first.
5. Add slider-driven normalised weights.
6. Add missing-pillar renormalisation and visible effective weights.
7. Add the country-year relationship-condition overlay.
8. Apply canonical entity eligibility before publication.
9. Review the prototype with Darren before fixing thresholds or declaring a headline formulation.
