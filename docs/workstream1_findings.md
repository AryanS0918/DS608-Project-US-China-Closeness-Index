# Workstream 1 Findings: Baseline Repair

**Date:** 8 November 2026  
**Comparable period:** 2004-2024  
**Direction:** positive = US-oriented; negative = China-oriented

## Decisions supported by the audit

### 1. Official core index

Use security, diplomatic and economic pillars as the official core index. Use equal requested weights. Retain:

- `core_index_complete`: calculated only when all three core pillars are observed;
- `core_index_available`: calculated with at least two core pillars and row-wise weight renormalisation.

The canonical entity master produces 4,014 eligible country-years. The strict core is available for 3,548 observations. The available-pillar core is available for all 4,014 observations.

### 2. Technology status

Reclassify the current technology measure as **experimental ICT-goods trade orientation**. Do not discard it and do not describe it as a complete technology-capability measure.

Across 3,564 paired country-years, adding technology to the equal-weight core:

- has Pearson correlation 0.841 with the three-pillar core;
- has Spearman correlation 0.843;
- shifts scores by 0.142 in absolute value on average;
- shifts the mean by -0.090 and the median by -0.128 toward China; and
- reverses the sign in 852 observations, or 23.91%.

The scale and direction of these changes support experimental rather than baseline status.

In 2024:

- Japan moves from +0.326 in the core to +0.067 with technology;
- South Korea moves from +0.266 to +0.017;
- Australia moves from +0.196 to +0.004;
- India moves from -0.070 to -0.277.

### 3. Missing-weight bug

The prior calculation could return zero where all positively weighted scores were missing. The corrected function:

- uses `sum(axis=1, min_count=1)`;
- requires positive observed weight coverage;
- rejects all-zero requested weights;
- never replaces missing evidence with zero; and
- reports effective weights after renormalisation.

Six focused tests pass.

### 4. Security no-ties zero

There are 1,474 eligible 2004-2024 country-years where:

- the integrated security score is zero;
- institutional orientation is zero; and
- arms orientation is zero or unavailable.

Treating those rows as unavailable comparative security evidence rather than zero:

- retains a sensitivity score for 1,189 rows;
- removes 285 scores under the minimum-two-core-pillar rule;
- changes scores by 0.075 in absolute value on average;
- changes scores by 0.070 at the median; and
- causes no directional reversals among comparable scores.

**Recommended baseline:** retain zero as no net security advantage, but preserve and display `security_no_ties_flag`. Keep the unavailable treatment as a sensitivity. This avoids losing 285 scores while preventing users from reading zero as equally strong ties.

### 5. Relationship condition

The 2024 production panel contains:

- 115 `strained` relationships toward the United States;
- 22 `strained` relationships toward China; and
- 58 anchor rows belonging to country-years where both anchors have adverse classifications.

All 115 US `strained` rows are controlled by `active_sanctions`. Of these, 85 contain partial trade scope and 30 have no trade scope. The production data do not identify sanctioned persons or firms directly, so the audit can distinguish targeted or non-trade profiles only provisionally from family and trade-scope fields.

**Recommendation:** do not revise the production condition classifier from this aggregate panel alone. Retain Aryan's display refinements as provisional diagnostics. A classifier revision requires the underlying sanctions evidence with target type, legal basis, multilateral origin and breadth.

## Files in the implementation package

- `src/data/build_closeness_index.py`
- `tests/test_closeness_index.py`
- `notebooks/19_final_us_china_closeness_index.ipynb`
- `outputs/tables/closeness_index/us_china_relative_orientation_index_country_year.csv`
- `outputs/tables/closeness_index/closeness_index_summary.json`
- coverage, technology-impact, security-sensitivity and relationship-condition audit tables

## Next workstream

Run neutral-band and side-specific Jenks analysis only on the frozen three-pillar continuous core. Keep neutral, hedging and no-score statuses separate even where the map uses a shared neutral colour.
