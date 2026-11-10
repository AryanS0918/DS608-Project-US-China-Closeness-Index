# US–China Relative Orientation Index

A country-year index of whether each country's international relationships lean toward the United States or toward China, with an interactive dashboard for exploring it. DS608 group project, Data Analytics for Economics.

## What it measures

Scores run from -1 to +1: **positive means US-oriented, negative means China-oriented, and 0 means balanced.** The comparable period is 2004–2024 and the index covers 192 countries and entities.

| | |
|---|---|
| Official index | Security, diplomatic and economic pillars, weighted one-third each. A country-year needs at least 2 of the 3 pillars; the strict version needs all 3 |
| Coverage | 4,014 country-years with an official score (3,548 under the strict version) |
| Technology | An experimental ICT-goods trade orientation (3,322 country-years). It is shown separately and is not part of the official score |
| Classes | Five fixed classes, never recalculated by year: strongly China-oriented (at or below -0.255), moderately China-oriented, neutral or hedging (between -0.05 and +0.05), moderately US-oriented, strongly US-oriented (at or above +0.271). Exact thresholds are in the decision register |

The reasons for each choice are in [docs/decision_register.md](docs/decision_register.md), [docs/workstream1_findings.md](docs/workstream1_findings.md) and [docs/workstream2_findings.md](docs/workstream2_findings.md).

## Dashboard

Run the dashboard from the repository root:

```bash
python3 -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -r requirements.txt
streamlit run dashboard/app.py
```

It opens at http://localhost:8501. Internet access is needed for the map boundaries.

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
- A missing pillar is never treated as zero; weights are renormalised over the pillars a country has.
- The official benchmark is never replaced by a scenario.

### How it works

![Dashboard architecture: three data files feed core/data.py, which builds one panel; core/weighting.py (built on the production functions in src/data) and core/charts.py work on it; app.py reruns on every interaction and the browser draws the maps and charts](dashboard/docs/architecture.png)

- **Input.** `dashboard/core/data.py` reads `outputs/tables/closeness_index/us_china_relative_orientation_index_classified.csv`, plus the relationship-condition panel and the technology variants from `data/processed/`. It checks the row and entity counts and writes nothing.
- **Scenarios.** `dashboard/core/weighting.py` applies the scenario rules on top of the production functions `weighted_index` and `classify_score` from `src/data`, so the dashboard cannot drift from the official numbers. With the default weights, the scenario equals the official score exactly.
- **Interaction.** Streamlit reruns `dashboard/app.py` from the top on every click or slider move, so changing a weight recalculates the scenario scores and recolours the map.
- **Charts.** `dashboard/core/charts.py` draws the maps and charts with Plotly, using the fixed class colours.

Code structure:

- `dashboard/app.py`: Streamlit entry point
- `dashboard/core/data.py`: loads the canonical index and context
- `dashboard/core/weighting.py`: scenario rules built on the production functions
- `dashboard/core/charts.py`: maps and charts
- `dashboard/assets/`: small-state map markers
- `dashboard/docs/`: architecture diagram
- `.streamlit/config.toml`: theme

## How the index is built

| Pillar | Components | Method notes |
|---|---|---|
| Security | Institutional security ties (treaty and organisation membership) and SIPRI arms transfers, half each | [security_subindex.md](docs/data_acquisition/security_subindex.md) |
| Diplomatic | Diplomatic structural ties and relative UN General Assembly voting alignment, half each | [diplomatic_subindex.md](docs/data_acquisition/diplomatic_subindex.md) |
| Economic | Merchandise trade orientation, FDI structural orientation and economic institutional orientation | [economic_subindex.md](docs/data_acquisition/economic_subindex.md) |
| Technology (experimental) | ICT-goods trade orientation | [technology_trade_implementation_notes.md](docs/data_acquisition/technology_trade_implementation_notes.md) |

At the index level, a missing pillar is never treated as zero: the weights are renormalised over the pillars observed. The final index is built by `src/data/build_closeness_index.py` and classified by `src/data/build_orientation_classification.py`. The development notebooks `notebooks/19_final_us_china_closeness_index.ipynb` and `notebooks/20_orientation_classification.ipynb` record the work.

### Merchandise trade pipeline

The pipeline:

- collects annual bilateral trade with the United States and China;
- covers available observations from 2000 through 2025;
- uses country-reported observations first;
- supplements missing observations using anchor-reported mirror data;
- preserves unresolved observations as missing;
- calculates a bounded directional trade score; and
- produces validation and coverage reports.

### SIPRI arms-transfer pipeline

The pipeline:

- reads SIPRI Arms Transfers Database exports (1996–2025) of arms delivered by the United States, by China and by all suppliers, in trend-indicator values (TIV);
- treats an empty cell as no identified deliveries and a displayed zero as the midpoint 0.25;
- removes non-state recipients, maps recipient names to ISO3 codes and writes audit files, and stops if a state-like name stays unmapped;
- computes five-year rolling sums, using complete windows only, so the first score uses 2000–2004;
- calculates the score as (US TIV - China TIV) / global TIV over the window, bounded between -1 and +1; and
- records a status for each country-year (`available`, `no_observed_anchor_transfers` or `no_observed_arms_imports`) and a low-volume flag below 100 TIV. A missing score means no arms imports were identified, not neutral alignment.

Details are in [docs/data_acquisition/security_arms_transfers.md](docs/data_acquisition/security_arms_transfers.md).

## Repository structure

```
dashboard/        Streamlit dashboard (app.py, core/, assets/, docs/)
src/data/         Collection, build and classification scripts
notebooks/        Development notebooks 01–20, in pipeline order
tests/            Unit tests for the pipeline and the dashboard
data/             raw/, interim/, processed/, reference/, sources/
outputs/tables/   Audit tables and the canonical index outputs
docs/             Decision register, findings, source register, method notes
.streamlit/       Dashboard theme
AI_USAGE.md       Record of AI assistance
CONTRIBUTIONS.md  Contributions by team member
```

## Tests

```bash
python -m pytest -q
```

To run only the index, classification and dashboard tests:

```bash
python -m pytest tests/test_dashboard_weighting.py tests/test_closeness_index.py tests/test_orientation_classification.py -q
```

## Known limitations

- Technology is an experimental ICT-goods trade measure, because trade data cannot attribute foreign value added by origin. It is excluded from the official score.
- Official scores built from only two pillars are thinner than three-pillar scores; the strict three-pillar version is provided for comparison.
- The relationship condition is context only and never changes a score.
- The map boundaries load from the internet, so the dashboard needs a connection.

## Documentation

- [docs/decision_register.md](docs/decision_register.md): decisions and their reasons
- [docs/workstream1_findings.md](docs/workstream1_findings.md) and [docs/workstream2_findings.md](docs/workstream2_findings.md): audit findings behind the official index and classes
- [docs/source_register.md](docs/source_register.md): data sources
- [docs/data_acquisition/](docs/data_acquisition/): method notes for each component
- [CONTRIBUTIONS.md](CONTRIBUTIONS.md) and [AI_USAGE.md](AI_USAGE.md): who did what, and how AI was used

## API credentials

The trade collector requires a personal UN Comtrade API key. Copy `.env.example` to `.env` and add:

```
COMTRADE_API_KEY=replace_with_your_own_key
```

The `.env` file must not be committed.

Run the trade collector from the repository root:

```bash
python -m src.data.collect_trade
```
