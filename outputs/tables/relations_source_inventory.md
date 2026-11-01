# Formal-relations source inventory

Generated: 2026-11-01T15:36:13

## Scope

- Tracked source root: `data/sources/relations`
- Restricted raw root: `data/raw/relations`
- Files inventoried: **36**
- Tracked source files: **23**
- Restricted raw files: **13**
- Files with read warnings: **0**

## Files

| Storage | File | Type | Size (bytes) | Tabular objects | Warnings |
|---|---|---:|---:|---:|---:|
| restricted_raw | `data/raw/relations/gsdb/CHECKSUMS.sha256` | .sha256 | 1,752 | 0 | 0 |
| restricted_raw | `data/raw/relations/gsdb/downloads/GSDB-FS/GSDB-FS.csv` | .csv | 72,127 | 1 | 0 |
| restricted_raw | `data/raw/relations/gsdb/downloads/GSDB-FS/GSDB-FS_Codebook.pdf` | .pdf | 307,526 | 0 | 0 |
| restricted_raw | `data/raw/relations/gsdb/downloads/GSDB-FS/GSDB-FS_Dyadic.dta` | .dta | 10,192,067 | 1 | 0 |
| restricted_raw | `data/raw/relations/gsdb/downloads/GSDB-R5/GSDB-R5.csv` | .csv | 189,401 | 1 | 0 |
| restricted_raw | `data/raw/relations/gsdb/downloads/GSDB-R5/GSDB-R5_Codebook.pdf` | .pdf | 320,806 | 0 | 0 |
| restricted_raw | `data/raw/relations/gsdb/downloads/GSDB-R5/GSDB-R5_Dyadic.dta` | .dta | 21,883,352 | 1 | 0 |
| restricted_raw | `data/raw/relations/gsdb/financial/GSDB-FS.csv` | .csv | 72,127 | 1 | 0 |
| restricted_raw | `data/raw/relations/gsdb/financial/GSDB-FS_Codebook.pdf` | .pdf | 307,526 | 0 | 0 |
| restricted_raw | `data/raw/relations/gsdb/financial/GSDB-FS_Dyadic.dta` | .dta | 10,192,067 | 1 | 0 |
| restricted_raw | `data/raw/relations/gsdb/r5/GSDB-R5.csv` | .csv | 189,401 | 1 | 0 |
| restricted_raw | `data/raw/relations/gsdb/r5/GSDB-R5_Codebook.pdf` | .pdf | 320,806 | 0 | 0 |
| restricted_raw | `data/raw/relations/gsdb/r5/GSDB-R5_Dyadic.dta` | .dta | 21,883,352 | 1 | 0 |
| tracked_source | `data/sources/relations/Bilateral Investment Treaty with China.xlsx` | .xlsx | 34,255 | 1 | 0 |
| tracked_source | `data/sources/relations/Bilateral Investment Treaty with US.xlsx` | .xlsx | 29,335 | 1 | 0 |
| tracked_source | `data/sources/relations/US-China Index Treaties Sources.docx` | .docx | 27,826 | 0 | 0 |
| tracked_source | `data/sources/relations/US-China Index Treaties.xlsx` | .xlsx | 106,333 | 2 | 0 |
| tracked_source | `data/sources/relations/diplomatic_representation/Diplo Exchange robustness check log1 - Prepost1985_Moyer Turner Meisel_JPR_2020.log` | .log | 92,188 | 0 | 0 |
| tracked_source | `data/sources/relations/diplomatic_representation/Diplo Exchange robustness check log2 - annual data_Moyer Turner Meisel_JPR_2020.log` | .log | 377,290 | 0 | 0 |
| tracked_source | `data/sources/relations/diplomatic_representation/Diplo Exhange replication log_Moyer Turner Mesiel_JPR_2020.smcl` | .smcl | 2,459,321 | 0 | 0 |
| tracked_source | `data/sources/relations/diplomatic_representation/Diplomatic Representation Codebook_V20230829.pdf` | .pdf | 522,312 | 0 | 0 |
| tracked_source | `data/sources/relations/diplomatic_representation/Diplomatic_Exchange_V3.16.16.pdf` | .pdf | 1,001,962 | 0 | 0 |
| tracked_source | `data/sources/relations/diplomatic_representation/Diplometrics_Diplomatic-Representation_1960-2024_20250825.xlsx` | .xlsx | 21,618,624 | 1 | 0 |
| tracked_source | `data/sources/relations/diplomatic_representation/README.md` | .md | 0 | 0 | 0 |
| tracked_source | `data/sources/relations/diplomatic_representation/annual.dta` | .dta | 445,818,007 | 1 | 0 |
| tracked_source | `data/sources/relations/diplomatic_representation/diplomatic_exchange_analysis_replication_Moyer Turner Meisel_JPR_2020.do` | .do | 40,698 | 0 | 0 |
| tracked_source | `data/sources/relations/diplomatic_representation/embassy.tsv` | .tsv | 18,582,186 | 1 | 0 |
| tracked_source | `data/sources/relations/diplomatic_representation/final_5_yr_blocks.tsv` | .tsv | 61,431,759 | 1 | 0 |
| tracked_source | `data/sources/relations/ofac/README.md` | .md | 0 | 0 | 0 |
| tracked_source | `data/sources/relations/ofac/documentation/advanced_xml.xsd` | .xsd | 85,050 | 0 | 0 |
| tracked_source | `data/sources/relations/ofac/documentation/dat_spec.txt` | .txt | 15,153 | 0 | 0 |
| tracked_source | `data/sources/relations/ofac/documentation/xml.xsd` | .xsd | 7,400 | 0 | 0 |
| tracked_source | `data/sources/relations/ofac/non_sdn/CONS_ADVANCED.XML` | .xml | 4,580,537 | 0 | 0 |
| tracked_source | `data/sources/relations/ofac/non_sdn/cons_prim.csv` | .csv | 268,508 | 1 | 0 |
| tracked_source | `data/sources/relations/ofac/sdn/SDN_ADVANCED.XML` | .xml | 127,668,232 | 0 | 0 |
| tracked_source | `data/sources/relations/ofac/sdn/sdn.csv` | .csv | 5,744,136 | 1 | 0 |

## Tabular objects

### `data/raw/relations/gsdb/downloads/GSDB-FS/GSDB-FS.csv`

- Rows: **1,072**
- Columns: **7**
- Duplicate rows: **0**
- Candidate keys: case_id, case_id + sanctioning_state, case_id + sanctioned_state, case_id + begin_year, case_id + end_year
- Temporal fields: `{"begin_year": {"kind": "year", "min": 1950, "max": 2025, "non_missing": 1072}, "end_year": {"kind": "year", "min": 1953, "max": 2025, "non_missing": 1072}}`
- Geographic fields: `{"sanctioning_state": {"non_missing": 1072, "unique": 116}, "sanctioned_state": {"non_missing": 1072, "unique": 191}}`

### `data/raw/relations/gsdb/downloads/GSDB-FS/GSDB-FS_Dyadic.dta`

- Rows: **91,914**
- Columns: **14**
- Duplicate rows: **0**
- Candidate keys: None identified automatically
- Temporal fields: `{"year": {"kind": "date", "min": "1950-01-01", "max": "2025-01-01", "non_missing": 91914}}`
- Geographic fields: `{"sanctioning_state_iso3": {"non_missing": 91914, "unique": 204}, "sanctioning_state": {"non_missing": 91914, "unique": 206}, "sanctioned_state_iso3": {"non_missing": 91914, "unique": 161}, "sanctioned_state": {"non_missing": 91914, "unique": 166}}`

### `data/raw/relations/gsdb/downloads/GSDB-R5/GSDB-R5.csv`

- Rows: **1,794**
- Columns: **18**
- Duplicate rows: **0**
- Candidate keys: case_id, case_id + sanctioned_state, case_id + sanctioning_state, case_id + begin_year, case_id + end_year, case_id + target_mult, case_id + sender_mult
- Temporal fields: `{"begin_year": {"kind": "year", "min": 1949, "max": 2025, "non_missing": 1794}, "end_year": {"kind": "year", "min": 1951, "max": 2025, "non_missing": 1794}, "sender_mult": {"kind": "date", "min": "1970-01-01", "max": "1970-01-01", "non_missing": 1794}}`
- Geographic fields: `{"sanctioned_state": {"non_missing": 1794, "unique": 241}, "sanctioning_state": {"non_missing": 1794, "unique": 197}, "target_mult": {"non_missing": 1794, "unique": 2}, "sender_mult": {"non_missing": 1794, "unique": 2}}`

### `data/raw/relations/gsdb/downloads/GSDB-R5/GSDB-R5_Dyadic.dta`

- Rows: **170,563**
- Columns: **17**
- Duplicate rows: **0**
- Candidate keys: None identified automatically
- Temporal fields: `{"year": {"kind": "date", "min": "1950-01-01", "max": "2025-01-01", "non_missing": 170563}, "sender_mult": {"kind": "date", "min": "1970-01-01", "max": "1970-01-01", "non_missing": 170563}}`
- Geographic fields: `{"sanctioning_state_iso3": {"non_missing": 170563, "unique": 210}, "sanctioning_state": {"non_missing": 170563, "unique": 212}, "sanctioned_state_iso3": {"non_missing": 170563, "unique": 190}, "sanctioned_state": {"non_missing": 170563, "unique": 196}, "target_mult": {"non_missing": 170563, "unique": 2}, "sender_mult": {"non_missing": 170563, "unique": 2}}`

### `data/raw/relations/gsdb/financial/GSDB-FS.csv`

- Rows: **1,072**
- Columns: **7**
- Duplicate rows: **0**
- Candidate keys: case_id, case_id + sanctioning_state, case_id + sanctioned_state, case_id + begin_year, case_id + end_year
- Temporal fields: `{"begin_year": {"kind": "year", "min": 1950, "max": 2025, "non_missing": 1072}, "end_year": {"kind": "year", "min": 1953, "max": 2025, "non_missing": 1072}}`
- Geographic fields: `{"sanctioning_state": {"non_missing": 1072, "unique": 116}, "sanctioned_state": {"non_missing": 1072, "unique": 191}}`

### `data/raw/relations/gsdb/financial/GSDB-FS_Dyadic.dta`

- Rows: **91,914**
- Columns: **14**
- Duplicate rows: **0**
- Candidate keys: None identified automatically
- Temporal fields: `{"year": {"kind": "date", "min": "1950-01-01", "max": "2025-01-01", "non_missing": 91914}}`
- Geographic fields: `{"sanctioning_state_iso3": {"non_missing": 91914, "unique": 204}, "sanctioning_state": {"non_missing": 91914, "unique": 206}, "sanctioned_state_iso3": {"non_missing": 91914, "unique": 161}, "sanctioned_state": {"non_missing": 91914, "unique": 166}}`

### `data/raw/relations/gsdb/r5/GSDB-R5.csv`

- Rows: **1,794**
- Columns: **18**
- Duplicate rows: **0**
- Candidate keys: case_id, case_id + sanctioned_state, case_id + sanctioning_state, case_id + begin_year, case_id + end_year, case_id + target_mult, case_id + sender_mult
- Temporal fields: `{"begin_year": {"kind": "year", "min": 1949, "max": 2025, "non_missing": 1794}, "end_year": {"kind": "year", "min": 1951, "max": 2025, "non_missing": 1794}, "sender_mult": {"kind": "date", "min": "1970-01-01", "max": "1970-01-01", "non_missing": 1794}}`
- Geographic fields: `{"sanctioned_state": {"non_missing": 1794, "unique": 241}, "sanctioning_state": {"non_missing": 1794, "unique": 197}, "target_mult": {"non_missing": 1794, "unique": 2}, "sender_mult": {"non_missing": 1794, "unique": 2}}`

### `data/raw/relations/gsdb/r5/GSDB-R5_Dyadic.dta`

- Rows: **170,563**
- Columns: **17**
- Duplicate rows: **0**
- Candidate keys: None identified automatically
- Temporal fields: `{"year": {"kind": "date", "min": "1950-01-01", "max": "2025-01-01", "non_missing": 170563}, "sender_mult": {"kind": "date", "min": "1970-01-01", "max": "1970-01-01", "non_missing": 170563}}`
- Geographic fields: `{"sanctioning_state_iso3": {"non_missing": 170563, "unique": 210}, "sanctioning_state": {"non_missing": 170563, "unique": 212}, "sanctioned_state_iso3": {"non_missing": 170563, "unique": 190}, "sanctioned_state": {"non_missing": 170563, "unique": 196}, "target_mult": {"non_missing": 170563, "unique": 2}, "sender_mult": {"non_missing": 170563, "unique": 2}}`

### `data/sources/relations/Bilateral Investment Treaty with China.xlsx :: Treaties`

- Rows: **150**
- Columns: **13**
- Duplicate rows: **0**
- Candidate keys: Parties + Date of signature, Date of signature + Amendment protocols
- Temporal fields: `{"Date of signature": {"kind": "date", "min": "1982-03-29", "max": "2025-06-16", "non_missing": 150}, "Date of entry into force": {"kind": "date", "min": "1982-03-29", "max": "2025-12-01", "non_missing": 131}, "Date of termination": {"kind": "date", "min": "2004-08-01", "max": "2025-12-01", "non_missing": 24}}`
- Geographic fields: `{"Parties": {"non_missing": 150, "unique": 132}, "Date of termination": {"non_missing": 24, "unique": 24}, "Type of termination": {"non_missing": 24, "unique": 2}}`

### `data/sources/relations/Bilateral Investment Treaty with US.xlsx :: Treaties`

- Rows: **53**
- Columns: **13**
- Duplicate rows: **3**
- Candidate keys: None identified automatically
- Temporal fields: `{"Date of signature": {"kind": "date", "min": "1982-10-27", "max": "2008-02-19", "non_missing": 47}, "Date of entry into force": {"kind": "date", "min": "1989-03-03", "max": "2012-01-01", "non_missing": 41}, "Date of termination": {"kind": "date", "min": "2012-06-10", "max": "2018-05-18", "non_missing": 2}}`
- Geographic fields: `{"Parties": {"non_missing": 47, "unique": 47}, "Date of termination": {"non_missing": 2, "unique": 2}, "Type of termination": {"non_missing": 2, "unique": 1}}`

### `data/sources/relations/US-China Index Treaties.xlsx :: Sheet2`

- Rows: **27**
- Columns: **5**
- Duplicate rows: **3**
- Candidate keys: None identified automatically
- Temporal fields: `{}`
- Geographic fields: `{}`

### `data/sources/relations/US-China Index Treaties.xlsx :: Treaties`

- Rows: **211**
- Columns: **507**
- Duplicate rows: **5**
- Candidate keys: None identified automatically
- Temporal fields: `{}`
- Geographic fields: `{}`

### `data/sources/relations/diplomatic_representation/Diplometrics_Diplomatic-Representation_1960-2024_20250825.xlsx :: Diplometrics_Diplomatic-Represe`

- Rows: **453,775**
- Columns: **12**
- Duplicate rows: **0**
- Candidate keys: None identified automatically
- Temporal fields: `{"Year": {"kind": "year", "min": 1960, "max": 2024, "non_missing": 453775}}`
- Geographic fields: `{"Destination": {"non_missing": 453775, "unique": 204}, "DestinationRegion": {"non_missing": 453775, "unique": 5}, "DestinationSubregion": {"non_missing": 453775, "unique": 17}, "SendingCountry": {"non_missing": 453775, "unique": 206}, "Location": {"non_missing": 453775, "unique": 204}}`

### `data/sources/relations/diplomatic_representation/annual.dta`

- Rows: **1,542,564**
- Columns: **61**
- Duplicate rows: **0**
- Candidate keys: None identified automatically
- Temporal fields: `{"year": {"kind": "year", "min": 1970, "max": 2005, "non_missing": 1542564}, "neu_powerpc_sender_ann": {"kind": "date", "min": "1969-12-31", "max": "1970-01-01", "non_missing": 1162512}, "neu_lngdppc_sender_ann": {"kind": "date", "min": "1970-01-01", "max": "1970-01-01", "non_missing": 1184868}, "neu_lngdppc_sender": {"kind": "date", "min": "1970-01-01", "max": "1970-01-01", "non_missing": 220869}, "neu_dr_at_sender_dum": {"kind": "date", "min": "1970-01-01", "max": "1970-01-01", "non_missing": 213366}, "neu_independence_sender": {"kind": "year", "min": 1816, "max": 1993, "non_missing": 298080}, "neu_powerpc_sender": {"kind": "date", "min": "1969-12-31", "max": "1970-01-01", "non_missing": 207207}, "neu_bilattradegdp_sender": {"kind": "date", "min": "1970-01-01", "max": "1970-01-01", "non_missing": 211387}, "EmbassyNew_sender": {"kind": "date", "min": "1970-01-01", "max": "1970-01-01", "non_missing": 229566}, "binemb_sender": {"kind": "date", "min": "1970-01-01", "max": "1970-01-01", "non_missing": 290612}, "sender_merge": {"kind": "date", "min": "1970-01-01", "max": "1970-01-01", "non_missing": 333005}, "dup_sender": {"kind": "date", "min": "1970-01-01", "max": "1970-01-01", "non_missing": 333005}, "neu_dr_sender_ann": {"kind": "date", "min": "1970-01-01", "max": "1970-01-01", "non_missing": 929190}, "binemb_neubirth_send": {"kind": "date", "min": "1970-01-01", "max": "1970-01-01", "non_missing": 933442}}`
- Geographic fields: `{"countrya": {"non_missing": 1542564, "unique": 207}, "countryb": {"non_missing": 1542564, "unique": 207}, "neu_powerpc_sender_ann": {"non_missing": 1162512, "unique": 5616}, "neu_lngdppc_sender_ann": {"non_missing": 1184868, "unique": 5593}, "neu_samedyad_ann": {"non_missing": 1542564, "unique": 2}, "neu_lngdppc_sender": {"non_missing": 220869, "unique": 978}, "neu_dr_at_sender_dum": {"non_missing": 213366, "unique": 2}, "dyadid": {"non_missing": 342792, "unique": 42849}, "neu_samedyad": {"non_missing": 342792, "unique": 2}, "neu_independence_sender": {"non_missing": 298080, "unique": 70}, "neu_powerpc_sender": {"non_missing": 207207, "unique": 1001}, "neu_bilattradegdp_sender": {"non_missing": 211387, "unique": 101700}, "neu_countryid": {"non_missing": 342792, "unique": 207}, "EmbassyNew_sender": {"non_missing": 229566, "unique": 6}, "binemb_sender": {"non_missing": 290612, "unique": 2}, "sender_merge": {"non_missing": 333005, "unique": 3}, "dup_sender": {"non_missing": 333005, "unique": 1}, "countryaidn": {"non_missing": 1542564, "unique": 207}, "dyadidn": {"non_missing": 1542564, "unique": 42849}, "dyadidn1": {"non_missing": 968760, "unique": 26910}, "dyadidn2": {"non_missing": 573804, "unique": 15939}, "neu_dr_sender_ann": {"non_missing": 929190, "unique": 2}, "Corrected_samedyad": {"non_missing": 1542564, "unique": 2}}`

### `data/sources/relations/diplomatic_representation/embassy.tsv`

- Rows: **424,368**
- Columns: **8**
- Duplicate rows: **0**
- Candidate keys: None identified automatically
- Temporal fields: `{"year": {"kind": "year", "min": 1960, "max": 2013, "non_missing": 424368}}`
- Geographic fields: `{"countrya": {"non_missing": 424368, "unique": 201}, "countryb": {"non_missing": 424368, "unique": 202}}`

### `data/sources/relations/diplomatic_representation/final_5_yr_blocks.tsv`

- Rows: **342,792**
- Columns: **44**
- Duplicate rows: **0**
- Candidate keys: year + neu_dyadid
- Temporal fields: `{"year": {"kind": "year", "min": 1970, "max": 2005, "non_missing": 342792}, "neu_dr_at_sender_dum": {"kind": "date", "min": "1970-01-01", "max": "1970-01-01", "non_missing": 213366}, "neu_independence_sender": {"kind": "year", "min": 1816, "max": 1993, "non_missing": 298080}, "neu_lngdppc_sender": {"kind": "date", "min": "1970-01-01", "max": "1970-01-01", "non_missing": 220869}, "neu_powerpc_sender": {"kind": "date", "min": "1969-12-31", "max": "1970-01-01", "non_missing": 207207}, "neu_bilattradegdp_sender": {"kind": "date", "min": "1970-01-01", "max": "1970-01-01", "non_missing": 211387}, "EmbassyNew_sender": {"kind": "date", "min": "1970-01-01", "max": "1970-01-01", "non_missing": 50734}, "binemb_sender": {"kind": "date", "min": "1970-01-01", "max": "1970-01-01", "non_missing": 62316}, "sender_merge": {"kind": "date", "min": "1970-01-01", "max": "1970-01-01", "non_missing": 71856}, "dup_sender": {"kind": "date", "min": "1970-01-01", "max": "1970-01-01", "non_missing": 71856}, "binemb_neubirth_send": {"kind": "date", "min": "1970-01-01", "max": "1970-01-01", "non_missing": 213858}}`
- Geographic fields: `{"countrya": {"non_missing": 342792, "unique": 207}, "countryb": {"non_missing": 342792, "unique": 207}, "neu_dr_at_sender_dum": {"non_missing": 213366, "unique": 2}, "neu_dyadid": {"non_missing": 342792, "unique": 42849}, "neu_samedyad": {"non_missing": 342792, "unique": 2}, "neu_independence_sender": {"non_missing": 298080, "unique": 70}, "neu_lngdppc_sender": {"non_missing": 220869, "unique": 978}, "neu_powerpc_sender": {"non_missing": 207207, "unique": 1001}, "neu_bilattradegdp_sender": {"non_missing": 211387, "unique": 101700}, "neu_countryid": {"non_missing": 342792, "unique": 207}, "EmbassyNew_sender": {"non_missing": 50734, "unique": 6}, "binemb_sender": {"non_missing": 62316, "unique": 2}, "sender_merge": {"non_missing": 71856, "unique": 3}, "dup_sender": {"non_missing": 71856, "unique": 1}, "Corrected_samedyad": {"non_missing": 342792, "unique": 2}}`

### `data/sources/relations/ofac/non_sdn/cons_prim.csv`

- Rows: **486**
- Columns: **12**
- Duplicate rows: **0**
- Candidate keys: None identified automatically
- Temporal fields: `{}`
- Geographic fields: `{}`

### `data/sources/relations/ofac/sdn/sdn.csv`

- Rows: **19,471**
- Columns: **12**
- Duplicate rows: **0**
- Candidate keys: None identified automatically
- Temporal fields: `{}`
- Geographic fields: `{}`

## Interpretation note

Candidate keys and inferred temporal/geographic fields are diagnostics only. They must be reviewed against each dataset's codebook before production use.
