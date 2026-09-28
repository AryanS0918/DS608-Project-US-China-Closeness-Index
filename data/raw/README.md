## UN Comtrade merchandise-trade data

The project uses the UN Comtrade API to collect annual bilateral
merchandise-trade data between reporting economies and the United
States and China.

Raw UN Comtrade files are not tracked in Git. They are downloaded
locally because:

- the files can be regenerated through the API;
- API credentials must not be committed;
- raw data may be too large for ordinary Git tracking; and
- UN Comtrade places conditions on data use and redistribution.

### Data collected

The current collector retrieves annual data from 2000 through 2025
for:

- imports from China;
- exports to China;
- imports from the United States; and
- exports to the United States.

The requested product category is total merchandise trade.

### API access

Each user must obtain a personal API key from the UN Comtrade
Developer Portal.

Create a file named `.env` in the repository root and add:

COMTRADE_API_KEY=replace_with_your_own_key

The `.env` file is excluded from Git and must not be committed.

A safe template is provided in `.env.example`.

### Reproducing the extraction

From the repository root:

1. Install the Python dependencies:

   python -m pip install -r requirements.txt

2. Confirm that `.env` contains a valid API key.

3. Run the collector:

   python -m src.data.collect_trade

The collector caches completed API responses locally. Subsequent runs
reuse cached files unless overwrite mode is explicitly enabled.

### Missing-data treatment

Country-reported bilateral flows are used whenever available.

If a country-reported flow is missing, the pipeline searches for the
corresponding mirror observation:

- missing country imports from China are matched to China-reported
  exports to that country;
- missing country exports to China are matched to China-reported
  imports from that country;
- missing country imports from the United States are matched to
  US-reported exports to that country; and
- missing country exports to the United States are matched to
  US-reported imports from that country.

If neither side reports the flow, the observation remains missing.
Missing observations are never silently replaced with zero.

### Local output

Downloaded responses are stored under:

data/raw/un_comtrade/total_trade/

These files should remain outside version control.