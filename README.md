# DS608-Project-US-China-Closeness-Index
Dashboard showing country alignments between the US and China

## Current project status

The total merchandise-trade collection and scoring pipeline is
complete and under review.

The current pipeline:

- collects annual bilateral trade with the United States and China;
- covers available observations from 2000 through 2025;
- uses country-reported observations first;
- supplements missing observations using anchor-reported mirror data;
- preserves unresolved observations as missing;
- calculates a bounded directional trade score; and
- produces validation and coverage reports.

The security pillar (arms transfers) collection and processing pipeline is complete:

- extracts annual Trend-Indicator Value (TIV) arms transfer data from SIPRI (1996–2025);
- processes full 5-year rolling windows with mandatory full-period requirements;
- filters out non-state entities and generates structured audit logs;
- maps recipient names to standardized ISO3 country codes;
- calculates a bounded signed score ranging from -1 to +1; and
- applies low-volume threshold flags and observational status codes.
  
Other pillars and the Streamlit dashboard remain under development.

## API credentials

The trade collector requires a personal UN Comtrade API key.

Copy `.env.example` to `.env` and add:

COMTRADE_API_KEY=replace_with_your_own_key

The `.env` file must not be committed.

Run the trade collector from the repository root:

python -m src.data.collect_trade
