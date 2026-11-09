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
- relies on the final panel merge to assign a `no_observed_relationship` status to countries in the master universe that never appear in the SIPRI database.
  
The security, diplomatic, economic and experimental technology pillars are complete. The official US-China Relative Orientation Index uses the security, diplomatic and economic pillars with equal weights and fixed five-class classification (see [docs/decision_register.md](docs/decision_register.md)); the Streamlit dashboard is in `dashboard/`.

## Dashboard

Run the dashboard from the repository root:

```bash
python3 -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -r requirements.txt
streamlit run dashboard/app.py
```

It opens at http://localhost:8501. Internet access is needed for the map boundaries.

### Data input

The dashboard reads `outputs/tables/closeness_index/us_china_relative_orientation_index_classified.csv`, plus the relationship-condition panel and technology sensitivity variants from `data/processed/`. It reads these files and writes nothing.

| Tab | Contents |
|---|---|
| Global map | Five fixed classes; views for Official, Your scenario, Difference, Single pillar and Relationship condition; zoom, region presets, small-state markers, hover and click |
| Country profile | Country-level index, pillar, relationship-condition and coverage detail |
| Pillar comparison | Side-by-side comparison of countries and pillar values |
| Weight explorer | Scenario weights, comparison with the official benchmark and class transitions |
| Methodology & coverage | Index specification, fixed classification, hedging rule and data coverage |

Scenario rules:

- Reset weights are one-third each for security, diplomatic and economic, and 0 for technology.
- Any positive technology weight makes the scenario an "Experimental user-weighted scenario".
- The official benchmark is never replaced by a scenario.

Run the dashboard tests:

```bash
python -m pytest tests/test_dashboard_weighting.py tests/test_closeness_index.py tests/test_orientation_classification.py -q
```

Code structure:

- `dashboard/app.py` — Streamlit entry point
- `dashboard/core/data.py` — loads the canonical index and context
- `dashboard/core/weighting.py` — scenario rules built on the production functions
- `dashboard/core/charts.py` — maps and charts
- `dashboard/assets/` — small-state map markers
- `.streamlit/config.toml` — theme

## API credentials

The trade collector requires a personal UN Comtrade API key.

Copy `.env.example` to `.env` and add:

COMTRADE_API_KEY=replace_with_your_own_key

The `.env` file must not be committed.

Run the trade collector from the repository root:

python -m src.data.collect_trade
