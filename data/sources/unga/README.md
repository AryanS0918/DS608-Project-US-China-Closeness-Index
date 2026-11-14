# United Nations General Assembly voting data

## Purpose

This directory contains the source workbooks used to construct the project's
United Nations General Assembly voting indicator.

The project measures a country's revealed relative voting orientation between
the United States and China when the two countries cast different UNGA votes.

## Files

### Updated UNGA Voting Records .xlsx

Project-specific compilation of UN General Assembly voting records covering
the historical voting panel and updated records through 2026.

The workbook contains country-level vote choices by resolution. Vote codes are
standardised by the processing pipeline before the indicator is calculated.

### US-China Closeness Index (1).xlsx

Legacy project workbook used to supply UNGA voting records for years that are
not yet fully represented in the updated workbook.

Only the "UNGA Votes By Resolution" worksheet is used by the current processing
pipeline. The workbook also contains unrelated legacy project sheets that are
not used in the calculation of the current UNGA indicator.

## Source and attribution

Underlying voting records are derived from:

United Nations Dag Hammarskjöld Library  
United Nations Digital Library  
https://digitallibrary.un.org/

Copyright © United Nations.

The underlying data are used for non-commercial academic purposes with
attribution, subject to the United Nations Digital Library terms of use.

These Excel workbooks are project-specific compilations and are not official
United Nations publications. Any restructuring, cleaning, transcription, or
processing errors introduced in these files are the responsibility of the
project authors.

## Processing

The workbooks are processed by:

    src/data/process_unga.py

Example execution from the project root:

    python -u src/data/process_unga.py \
      --updated "data/raw/unga/Updated UNGA Voting Records .xlsx" \
      --legacy "data/raw/unga/US-China Closeness Index (1).xlsx" \
      --output-dir "data/processed"

The script:

1. Reads the country-resolution vote matrices.
2. Standardises country names, resolution identifiers, and vote codes.
3. Distinguishes substantive votes, absences, and non-membership.
4. Removes exact duplicate resolution records.
5. Identifies resolutions on which the United States and China differed.
6. Calculates country-resolution and country-year voting indicators.
7. Produces data-quality and coverage reports.

## Vote codes

The source workbooks may contain the following codes:

- `Y`: Yes
- `N`: No
- `A`: Abstain
- `X` or blank: Did not vote or no recorded vote
- `NM`: Not a member
- Other values: Invalid until investigated

The processing script retains invalid values in the exception report rather
than guessing their intended meaning.

## Known data-quality matters

The current pipeline reports:

- One exact duplicated resolution, A/RES/62/143 in 2007, retained once.
- Three malformed historical vote entries that are excluded pending review.
- Incomplete 2026 coverage because only the resolutions currently available in
  the updated workbook are included.
- Country-name variants that are harmonised through an explicit alias mapping.

Consult the generated files below for current details:

- `data/processed/unga_duplicate_audit.csv`
- `data/processed/unga_ingestion_exceptions.csv`
- `data/processed/unga_coverage_by_year.csv`
- `data/processed/unga_anchor_resolution_audit.csv`

## Reproducibility

The source workbooks are versioned input artefacts. Changes to their contents
may change the processed indicator.

SHA-256 checksums should be recorded below whenever an accepted source
workbook is replaced.

### Current checksums

51a90be6f1dc42a85d6f4e7d7f38cad97287738fca96e86ae67ab738eb53d8ac  data/sources/unga/Updated UNGA Voting Records .xlsx
577d35a4c8f7abc1c21f9ad780ceeb3dd37d320a2c75e8e700cb016c071c02aa  data/sources/unga/US-China Closeness Index (1).xlsx

Checksums recorded on 18 October 2026 using SHA-256.

## Redistribution and use

The workbooks are included to support reproducibility of this non-commercial
academic project. Users remain responsible for complying with the applicable
United Nations terms of use and for acknowledging the original data source.