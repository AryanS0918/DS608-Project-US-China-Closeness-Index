# Global Sanctions Data Base

## Datasets

The project uses:

1. Global Sanctions Data Base – Release 5 (GSDB-R5)
2. Global Sanctions Data Base – Financial Sanctions (GSDB-FS)

Both datasets cover 1949–2025.

GSDB-R5 contains 1,794 sanctions cases. GSDB-FS contains 1,072
financial-sanctions cases and distinguishes six types of financial
sanctions.

Each release contains:

- a case-level CSV file;
- a bilateral/dyadic STATA file; and
- a PDF codebook.

The two releases are compatible and may be merged one-to-one using
`case_id`.

## Acquisition

The files were obtained directly from the GSDB team following a data
request submitted through:

https://www.globalsanctionsdatabase.com/data/

Download date: [insert date]
Dataset release: Release 5

## Storage

The source files are stored locally under:

`data/raw/relations/gsdb/`

The directory is ignored by Git.

The source files are not committed or redistributed because the GSDB
team requests that users direct interested researchers to obtain their
own copies through the official request page.

## Intended use

The project will use the datasets to identify material adverse
state-to-state measures involving the United States or China.

The source records will support an annual relationship-condition
classification:

- normal;
- strained;
- severely strained; or
- ruptured.

The classification methodology will be determined only after the
variables, categories, dyadic structure, overlapping cases, sender
coalitions, and temporal coverage have been audited.

## Citations

For GSDB-R5:

Felbermayr, G., A. Kirilakha, C. Syropoulos, E. Yalcin, and
Y. V. Yotov. 2020. “The Global Sanctions Data Base.”
European Economic Review, 129.

For GSDB-FS:

Yotov, Y. V., G. Felbermayr, H. Kariem, A. Kirilakha, O. Kwon,
C. Syropoulos, and E. Yalcin. 2026. “Financial Sanctions and
International Trade: Insights from New Data.” Working Papers 2026014,
Center for Global Policy Analysis, LeBow College of Business,
Drexel University.

## Redistribution

The original files must not be uploaded to the repository or shared
directly. Researchers should request access from the official GSDB
website.