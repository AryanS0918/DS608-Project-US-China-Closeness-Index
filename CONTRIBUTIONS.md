## Darren TAY Teck Yong

Completed contributions to date:

- led the project concept and index-methodology development;
- established and managed the UN Comtrade API access;
- implemented and reviewed the merchandise-trade ingestion pipeline;
- validated bilateral-flow and mirror-data mappings;
- monitored and improved API-call efficiency;
- ran coverage and missing-data diagnostics;
- verified the trade-scoring calculations;
- implemented unit tests for the trade-processing logic; and
- documented trade-data sources, limitations, and reproduction steps.

  

## Aryan Singh

Completed contributions to date:

- re-extracted and ingested historical SIPRI arms transfer data (1996–2025);
- developed the reproducible `process_sipri.py` data-processing pipeline;
- implemented ISO3 country name mapping and non-state entity filtering;
- established rigorous 5-year rolling windows with full-period validation;
- computed the bounded signed score formula transitioning from the legacy 0–100 scale;
- added volume thresholds and robust data status coding;
- generated audit logs for unmapped names and removed entities; and
- documented SIPRI source parameters, data limitations, and reproduction steps.
- Designed and built the Streamlit dashboard in dashboard/: world map with fixed class colours, weight sliders, single-year and range selection, country profile, pillar comparison, weight explorer and methodology tab.
- Reviewed the pipeline and raised five issues (weighting of missing pillars, technology dominance, ambiguity of a security score of 0, unscored key countries, and over-labelled strained relationships), which fed into the revised production treatments.
- Updated the dashboard to the canonical classified output, using the production weighting and classification functions rather than re-implementing them.
- Added tests (tests/test_dashboard_weighting.py) checking that the default scenario reproduces the official scores and classes.
