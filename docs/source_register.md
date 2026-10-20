## UN Comtrade: total merchandise trade

- **Pillar:** Economic relationships
- **Indicator:** Total bilateral merchandise trade
- **Source organisation:** United Nations Statistics Division
- **Dataset:** UN Comtrade
- **Access method:** Authenticated API using `comtradeapicall`
- **Current extraction period:** 2000-2025
- **Frequency:** Annual
- **Reporter coverage:** Varies by year
- **Partners:** United States and China
- **Flows:** Imports and exports
- **Product coverage:** All commodities
- **Monetary field:** `primaryValue`
- **Primary identifiers:** Reporter code, reporter ISO-3, partner code,
  year, and flow
- **Project status:** Included in the core economic pillar
- **Collector:** `src/data/collect_trade.py`
- **Tests:** `tests/test_trade_processing.py`

### Transformation

For country \(i\) and year \(t\):

US total bilateral trade equals imports from the United States plus
exports to the United States.

China total bilateral trade equals imports from China plus exports to
China.

The directional trade score is:

A_trade = (US total trade - China total trade)
          / (US total trade + China total trade)

The intended score range is -1 to +1.

### Missing-data rule

1. Use the reporting country's own observation where available.
2. If the observation is missing, use the corresponding US- or
   China-reported mirror value where available.
3. Record whether each flow is reporter-sourced, mirror-sourced, or
   missing.
4. If neither side reports the flow, retain the observation as missing.
5. Calculate the trade score only when all four required flows are
   available.
6. Do not assign scores to the United States or China because these
   countries define the two index anchors.

### Validation results

The current extraction produced:

- 4,411 country-year observations;
- 205 unique reporter codes;
- 4,301 valid non-anchor trade scores;
- 409 missing flows checked against mirror records;
- 345 mirror values recovered;
- 64 unresolved flows;
- 58 unresolved country-years;
- zero duplicated reporter-year-relationship rows;
- zero missing reporter ISO identifiers;
- zero scores outside the permitted range; and
- eight passing unit tests.

### Limitations

- Import and export values may follow different CIF and FOB valuation
  conventions.
- Gross trade can reflect re-exports and transshipment, especially for
  trading hubs.
- Mirror statistics can differ from reporter statistics.
- Reporter availability is incomplete for the latest years.
- Extreme directional scores can be based on economically small
  bilateral relationships.
- The final index country universe has not yet been determined.
- Raw UN Comtrade data are excluded from Git.
- Public redistribution of processed values will follow the applicable
  UN Comtrade conditions and any clarification obtained from UNSD.