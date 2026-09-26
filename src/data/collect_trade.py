"""Collect annual bilateral merchandise trade from UN Comtrade.

The module retrieves total merchandise imports and exports reported by
all available economies with the United States and China. Missing
reported exports are supplemented with partner-reported mirror imports
where available.

Raw and processed files are saved locally and should not be committed
unless redistribution permission has been established.
"""

from __future__ import annotations

import os
import time
from pathlib import Path

import certifi


# Ensure HTTPS libraries use the maintained certificate bundle.
# This must happen before importing the Comtrade API package.
CERTIFICATE_BUNDLE = certifi.where()

os.environ.setdefault(
    "SSL_CERT_FILE",
    CERTIFICATE_BUNDLE,
)

os.environ.setdefault(
    "REQUESTS_CA_BUNDLE",
    CERTIFICATE_BUNDLE,
)


import comtradeapicall
import pandas as pd
from dotenv import load_dotenv


# ---------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------

START_YEAR = 2000
END_YEAR = 2025

CHINA_CODE = "156"
US_CODE = "842"

ANCHOR_ISO_CODES = {"CHN", "USA"}

API_DELAY_SECONDS = 1.1
MAX_RETRIES = 3

RELATIONSHIPS = {
    "imports_from_china": {
        "partner_code": CHINA_CODE,
        "flow_code": "M",
    },
    "exports_to_china": {
        "partner_code": CHINA_CODE,
        "flow_code": "X",
    },
    "imports_from_us": {
        "partner_code": US_CODE,
        "flow_code": "M",
    },
    "exports_to_us": {
        "partner_code": US_CODE,
        "flow_code": "X",
    },
}

RAW_COLUMNS = [
    "period",
    "reporterCode",
    "reporterISO",
    "reporterDesc",
    "flowCode",
    "flowDesc",
    "partnerCode",
    "partnerISO",
    "partnerDesc",
    "classificationCode",
    "isOriginalClassification",
    "cmdCode",
    "cmdDesc",
    "primaryValue",
    "cifvalue",
    "fobvalue",
    "legacyEstimationFlag",
    "isReported",
    "isAggregate",
]


# ---------------------------------------------------------------------
# Repository paths and credentials
# ---------------------------------------------------------------------

def find_repository_root() -> Path:
    """Find the repository root by locating requirements.txt."""

    current_path = Path(__file__).resolve()

    for parent in current_path.parents:
        if (parent / "requirements.txt").exists():
            return parent

    raise RuntimeError(
        "Repository root could not be identified. "
        "Expected to find requirements.txt in a parent directory."
    )


REPOSITORY_ROOT = find_repository_root()

RAW_DIRECTORY = (
    REPOSITORY_ROOT
    / "data"
    / "raw"
    / "un_comtrade"
    / "total_trade"
)

PROCESSED_DIRECTORY = REPOSITORY_ROOT / "data" / "processed"
TABLE_DIRECTORY = REPOSITORY_ROOT / "outputs" / "tables"


def load_api_key() -> str:
    """Load the Comtrade API key from the repository-root .env file."""

    load_dotenv(REPOSITORY_ROOT / ".env")

    api_key = os.getenv("COMTRADE_API_KEY")

    if not api_key:
        raise RuntimeError(
            "COMTRADE_API_KEY was not found. "
            "Add it to the repository-root .env file."
        )

    return api_key


# ---------------------------------------------------------------------
# API collection
# ---------------------------------------------------------------------

def get_total_trade_slice(
    api_key: str,
    year: int,
    relationship: str,
) -> pd.DataFrame:
    """Retrieve one all-reporter, partner-flow-year trade slice."""

    if relationship not in RELATIONSHIPS:
        raise ValueError(
            f"Unknown relationship: {relationship}"
        )

    parameters = RELATIONSHIPS[relationship]

    last_error = None

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            dataframe = comtradeapicall.getFinalData(
                api_key,
                typeCode="C",
                freqCode="A",
                clCode="HS",
                period=str(year),
                reporterCode=None,
                cmdCode="TOTAL",
                flowCode=parameters["flow_code"],
                partnerCode=parameters["partner_code"],
                partner2Code=None,
                customsCode=None,
                motCode=None,
                maxRecords=100000,
                format_output="JSON",
                aggregateBy=None,
                breakdownMode="classic",
                countOnly=None,
                includeDesc=True,
            )

            if dataframe is None:
                raise ConnectionError(
                    "UN Comtrade returned no DataFrame. "
                    "The underlying request may have failed."
                )

            if not isinstance(dataframe, pd.DataFrame):
                raise TypeError(
                    "UN Comtrade returned an unexpected object: "
                    f"{type(dataframe).__name__}"
                )

            dataframe = dataframe.copy()
            dataframe["relationship"] = relationship
            dataframe["requested_year"] = year

            return dataframe

        except Exception as error:
            last_error = error

            if attempt == MAX_RETRIES:
                break

            wait_seconds = API_DELAY_SECONDS * (2 ** attempt)

            print(
                f"Request failed for {year}, {relationship}. "
                f"Retrying in {wait_seconds:.1f} seconds."
            )

            time.sleep(wait_seconds)

    raise RuntimeError(
        f"Comtrade request failed after {MAX_RETRIES} attempts "
        f"for year={year}, relationship={relationship}."
    ) from last_error


def raw_file_path(
    year: int,
    relationship: str,
) -> Path:
    """Return the raw CSV path for one trade slice."""

    return (
        RAW_DIRECTORY
        / str(year)
        / f"{relationship}.csv"
    )

def mirror_file_path(
    year: int,
    destination_code: str,
) -> Path:
    """Return the raw CSV path for one mirror-import batch."""

    destination_names = {
        CHINA_CODE: "china",
        US_CODE: "us",
    }

    destination_name = destination_names[
        str(destination_code)
    ]

    return (
        RAW_DIRECTORY
        / "mirrors"
        / str(year)
        / (
            f"{destination_name}"
            "_imports_from_all_partners.csv"
        )
    )

def collect_or_load_slice(
    api_key: str,
    year: int,
    relationship: str,
    overwrite: bool = False,
) -> pd.DataFrame:
    """Load an existing slice or retrieve it from Comtrade."""

    file_path = raw_file_path(
        year=year,
        relationship=relationship,
    )

    if file_path.exists() and not overwrite:
        return pd.read_csv(
            file_path,
            dtype={
                "reporterISO": "string",
                "partnerISO": "string",
            },
        )

    dataframe = get_total_trade_slice(
        api_key=api_key,
        year=year,
        relationship=relationship,
    )

    file_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    dataframe.to_csv(
        file_path,
        index=False,
    )

    time.sleep(API_DELAY_SECONDS)

    return dataframe


# ---------------------------------------------------------------------
# Validation and standardisation
# ---------------------------------------------------------------------

def validate_slice(
    dataframe: pd.DataFrame,
    year: int,
    relationship: str,
) -> dict:
    """Calculate validation statistics for one retrieved slice."""

    duplicate_count = dataframe.duplicated(
        subset=[
            "period",
            "reporterCode",
            "relationship",
        ],
        keep=False,
    ).sum()

    return {
        "year": year,
        "relationship": relationship,
        "rows": len(dataframe),
        "unique_reporters": (
            dataframe["reporterCode"].nunique()
            if not dataframe.empty
            else 0
        ),
        "duplicate_rows": int(duplicate_count),
        "missing_iso_rows": int(
            dataframe["reporterISO"].isna().sum()
        ),
        "original_classification_rows": int(
            dataframe[
                "isOriginalClassification"
            ].fillna(False).sum()
        ),
        "reported_rows": int(
            dataframe["isReported"].fillna(False).sum()
        ),
        "aggregate_rows": int(
            dataframe["isAggregate"].fillna(False).sum()
        ),
    }


def standardise_slice(
    dataframe: pd.DataFrame,
    year: int,
    relationship: str,
) -> pd.DataFrame:
    """Retain and standardise the fields required downstream."""

    available_columns = [
        column
        for column in RAW_COLUMNS
        if column in dataframe.columns
    ]

    standardised = dataframe[
        available_columns
    ].copy()

    standardised["year"] = year
    standardised["relationship"] = relationship
    standardised["value_source"] = "reporter"

    standardised = standardised.rename(
        columns={
            "reporterCode": "reporter_code",
            "reporterISO": "reporter_iso",
            "reporterDesc": "reporter_name",
            "partnerCode": "partner_code",
            "partnerISO": "partner_iso",
            "partnerDesc": "partner_name",
            "flowCode": "flow_code",
            "flowDesc": "flow_name",
            "classificationCode": "classification_code",
            "isOriginalClassification": (
                "is_original_classification"
            ),
            "cmdCode": "commodity_code",
            "cmdDesc": "commodity_name",
            "primaryValue": "trade_value_usd",
            "cifvalue": "cif_value_usd",
            "fobvalue": "fob_value_usd",
            "legacyEstimationFlag": (
                "legacy_estimation_flag"
            ),
            "isReported": "is_reported",
            "isAggregate": "is_aggregate",
        }
    )

    return standardised


# ---------------------------------------------------------------------
# Mirror-data fallback
# ---------------------------------------------------------------------

def identify_missing_exports(
    wide_dataframe: pd.DataFrame,
) -> pd.DataFrame:
    """Identify missing export observations requiring mirror queries."""

    missing_records = []

    relationship_destination = {
        "exports_to_china": {
            "destination_code": CHINA_CODE,
            "destination_name": "china",
        },
        "exports_to_us": {
            "destination_code": US_CODE,
            "destination_name": "us",
        },
    }

    for _, row in wide_dataframe.iterrows():
        if row["reporter_iso"] in ANCHOR_ISO_CODES:
            continue

        for relationship, destination in (
            relationship_destination.items()
        ):
            if pd.isna(row.get(relationship)):
                missing_records.append(
                    {
                        "year": int(row["year"]),
                        "reporter_code": int(
                            row["reporter_code"]
                        ),
                        "reporter_iso": row[
                            "reporter_iso"
                        ],
                        "reporter_name": row[
                            "reporter_name"
                        ],
                        "missing_relationship": (
                            relationship
                        ),
                        "destination_code": destination[
                            "destination_code"
                        ],
                        "destination_name": destination[
                            "destination_name"
                        ],
                    }
                )

    return pd.DataFrame(missing_records)


def get_destination_imports_from_all_partners(
    api_key: str,
    year: int,
    destination_code: str,
) -> pd.DataFrame:
    """Retrieve destination-reported imports from all partners."""

    last_error = None

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            dataframe = comtradeapicall.getFinalData(
                api_key,
                typeCode="C",
                freqCode="A",
                clCode="HS",
                period=str(year),
                reporterCode=str(destination_code),
                cmdCode="TOTAL",
                flowCode="M",
                partnerCode=None,
                partner2Code=None,
                customsCode=None,
                motCode=None,
                maxRecords=100000,
                format_output="JSON",
                aggregateBy=None,
                breakdownMode="classic",
                countOnly=None,
                includeDesc=True,
            )

            if dataframe is None:
                raise ConnectionError(
                    "UN Comtrade returned no DataFrame "
                    "for the mirror-batch request."
                )

            if not isinstance(dataframe, pd.DataFrame):
                raise TypeError(
                    "UN Comtrade returned an unexpected "
                    "mirror-batch object: "
                    f"{type(dataframe).__name__}"
                )

            return dataframe

        except Exception as error:
            last_error = error

            if attempt == MAX_RETRIES:
                break

            wait_seconds = (
                API_DELAY_SECONDS * (2 ** attempt)
            )

            print(
                f"Mirror-batch request failed for "
                f"year={year}, "
                f"destination={destination_code}. "
                f"Retrying in {wait_seconds:.1f} seconds."
            )

            time.sleep(wait_seconds)

    raise RuntimeError(
        "Mirror-batch request failed after "
        f"{MAX_RETRIES} attempts for "
        f"year={year}, "
        f"destination={destination_code}."
    ) from last_error

def collect_or_load_mirror_batch(
    api_key: str,
    year: int,
    destination_code: str,
    overwrite: bool = False,
) -> pd.DataFrame:
    """Load or retrieve one destination-year mirror batch."""

    file_path = mirror_file_path(
        year=year,
        destination_code=destination_code,
    )

    if file_path.exists() and not overwrite:
        return pd.read_csv(
            file_path,
            dtype={
                "reporterISO": "string",
                "partnerISO": "string",
            },
        )

    dataframe = (
        get_destination_imports_from_all_partners(
            api_key=api_key,
            year=year,
            destination_code=destination_code,
        )
    )

    file_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    dataframe.to_csv(
        file_path,
        index=False,
    )

    time.sleep(API_DELAY_SECONDS)

    return dataframe

def collect_mirror_values(
    api_key: str,
    missing_exports: pd.DataFrame,
    overwrite: bool = False,
) -> pd.DataFrame:
    """Resolve missing exports using batched mirror-import data."""

    if missing_exports.empty:
        return pd.DataFrame()

    required_batches = (
        missing_exports[
            [
                "year",
                "destination_code",
                "destination_name",
            ]
        ]
        .drop_duplicates()
        .sort_values(
            [
                "year",
                "destination_code",
            ]
        )
        .reset_index(drop=True)
    )

    print(
        "Mirror batches required:",
        len(required_batches),
    )

    batch_frames = []

    for _, batch in required_batches.iterrows():
        year = int(batch["year"])
        destination_code = str(
            batch["destination_code"]
        )
        destination_name = batch[
            "destination_name"
        ]

        print(
            f"  {year}: "
            f"{destination_name} imports "
            "from all partners"
        )

        dataframe = collect_or_load_mirror_batch(
            api_key=api_key,
            year=year,
            destination_code=destination_code,
            overwrite=overwrite,
        )

        if dataframe.empty:
            continue

        batch_subset = dataframe[
            [
                "period",
                "reporterCode",
                "reporterISO",
                "reporterDesc",
                "partnerCode",
                "partnerISO",
                "partnerDesc",
                "classificationCode",
                "primaryValue",
                "legacyEstimationFlag",
                "isReported",
                "isAggregate",
            ]
        ].copy()

        batch_subset["year"] = year
        batch_subset[
            "destination_code"
        ] = destination_code

        batch_subset = batch_subset.rename(
            columns={
                "reporterCode": (
                    "mirror_reporter_code"
                ),
                "reporterISO": (
                    "mirror_reporter_iso"
                ),
                "reporterDesc": (
                    "mirror_reporter"
                ),
                "partnerCode": (
                    "reporter_code"
                ),
                "partnerISO": (
                    "mirror_partner_iso"
                ),
                "partnerDesc": (
                    "mirror_partner"
                ),
                "classificationCode": (
                    "mirror_classification"
                ),
                "primaryValue": (
                    "mirror_value_usd"
                ),
                "legacyEstimationFlag": (
                    "mirror_legacy_estimation_flag"
                ),
                "isReported": (
                    "mirror_is_reported"
                ),
                "isAggregate": (
                    "mirror_is_aggregate"
                ),
            }
        )

        batch_subset["reporter_code"] = pd.to_numeric(
            batch_subset["reporter_code"],
            errors="coerce",
        ).astype("Int64")

        batch_frames.append(batch_subset)

    if not batch_frames:
        result = missing_exports.copy()
        result["mirror_value_usd"] = pd.NA
        result["mirror_reporter"] = pd.NA
        result["mirror_partner"] = pd.NA
        result["mirror_classification"] = pd.NA

        return result

    all_mirror_imports = pd.concat(
        batch_frames,
        ignore_index=True,
    )

    missing_exports_to_merge = (
        missing_exports.copy()
    )

    missing_exports_to_merge[
        "reporter_code"
    ] = pd.to_numeric(
        missing_exports_to_merge["reporter_code"],
        errors="coerce",
    ).astype("Int64")

    mirror_values = missing_exports_to_merge.merge(
        all_mirror_imports,
        how="left",
        on=[
            "year",
            "destination_code",
            "reporter_code",
        ],
        validate="many_to_one",
    )

    return mirror_values


# ---------------------------------------------------------------------
# Annual and historical panel construction
# ---------------------------------------------------------------------

def build_annual_wide_table(
    annual_long: pd.DataFrame,
) -> pd.DataFrame:
    """Reshape one year of reporter observations into four flows."""

    key_columns = [
        "year",
        "reporter_code",
        "reporter_iso",
        "reporter_name",
    ]

    duplicate_mask = annual_long.duplicated(
        subset=[
            "year",
            "reporter_code",
            "relationship",
        ],
        keep=False,
    )

    if duplicate_mask.any():
        duplicates = annual_long.loc[
            duplicate_mask,
            [
                "year",
                "reporter_code",
                "reporter_iso",
                "relationship",
            ],
        ]

        raise ValueError(
            "Duplicate reporter-year-relationship rows "
            f"were found:\n{duplicates}"
        )

    wide = (
        annual_long.pivot(
            index=key_columns,
            columns="relationship",
            values="trade_value_usd",
        )
        .reset_index()
    )

    wide.columns.name = None

    for relationship in RELATIONSHIPS:
        if relationship not in wide.columns:
            wide[relationship] = pd.NA

    return wide


def apply_mirror_values(
    wide_dataframe: pd.DataFrame,
    mirror_dataframe: pd.DataFrame,
) -> pd.DataFrame:
    """Fill missing export observations using available mirror values."""

    result = wide_dataframe.copy()

    for relationship in [
        "exports_to_china",
        "exports_to_us",
    ]:
        result[
            f"{relationship}_source"
        ] = result[relationship].notna().map(
            {
                True: "reporter",
                False: "missing",
            }
        )

    if mirror_dataframe.empty:
        return result

    for _, mirror in mirror_dataframe.iterrows():
        relationship = mirror[
            "missing_relationship"
        ]
        value = mirror["mirror_value_usd"]

        mask = (
            (result["year"] == mirror["year"])
            & (
                result["reporter_code"]
                == mirror["reporter_code"]
            )
        )

        if pd.notna(value):
            result.loc[
                mask,
                relationship,
            ] = value

            result.loc[
                mask,
                f"{relationship}_source",
            ] = "mirror"

    return result


def calculate_trade_measures(
    dataframe: pd.DataFrame,
) -> pd.DataFrame:
    """Calculate bilateral totals, completeness, and orientation."""

    result = dataframe.copy()

    result["china_total_trade_usd"] = (
        result["imports_from_china"]
        + result["exports_to_china"]
    )

    result["us_total_trade_usd"] = (
        result["imports_from_us"]
        + result["exports_to_us"]
    )

    required_flows = list(RELATIONSHIPS.keys())

    result["available_flow_count"] = (
        result[required_flows]
        .notna()
        .sum(axis=1)
    )

    result["complete_four_flow_record"] = (
        result["available_flow_count"] == 4
    )

    denominator = (
        result["us_total_trade_usd"]
        + result["china_total_trade_usd"]
    )

    result["trade_orientation_score"] = (
        (
            result["us_total_trade_usd"]
            - result["china_total_trade_usd"]
        )
        / denominator
    )

    result.loc[
        denominator == 0,
        "trade_orientation_score",
    ] = pd.NA

    result["is_anchor_country"] = (
        result["reporter_iso"].isin(
            ANCHOR_ISO_CODES
        )
    )

    result.loc[
        result["is_anchor_country"],
        [
            "complete_four_flow_record",
            "trade_orientation_score",
        ],
    ] = pd.NA

    return result


# ---------------------------------------------------------------------
# Main historical collection operation
# ---------------------------------------------------------------------

def collect_trade_history(
    start_year: int = START_YEAR,
    end_year: int = END_YEAR,
    overwrite: bool = False,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Collect, validate, mirror-fill, and process all requested years."""

    api_key = load_api_key()

    RAW_DIRECTORY.mkdir(
        parents=True,
        exist_ok=True,
    )

    PROCESSED_DIRECTORY.mkdir(
        parents=True,
        exist_ok=True,
    )

    TABLE_DIRECTORY.mkdir(
        parents=True,
        exist_ok=True,
    )

    all_long_data = []
    validation_records = []
    annual_wide_tables = []

    years = range(start_year, end_year + 1)

    for year in years:
        print(f"\nCollecting {year}")

        annual_slices = []

        for relationship in RELATIONSHIPS:
            print(f"  {relationship}")

            raw_slice = collect_or_load_slice(
                api_key=api_key,
                year=year,
                relationship=relationship,
                overwrite=overwrite,
            )

            validation_records.append(
                validate_slice(
                    dataframe=raw_slice,
                    year=year,
                    relationship=relationship,
                )
            )

            standardised = standardise_slice(
                dataframe=raw_slice,
                year=year,
                relationship=relationship,
            )

            annual_slices.append(standardised)
            all_long_data.append(standardised)

        annual_long = pd.concat(
            annual_slices,
            ignore_index=True,
        )

        annual_wide = build_annual_wide_table(
            annual_long
        )

        annual_wide_tables.append(annual_wide)

    trade_long = pd.concat(
        all_long_data,
        ignore_index=True,
    )

    trade_wide = pd.concat(
        annual_wide_tables,
        ignore_index=True,
    )

    missing_exports = identify_missing_exports(
        trade_wide
    )

    print(
        "\nMissing exports requiring mirror checks:",
        len(missing_exports),
    )

    mirror_values = collect_mirror_values(
    api_key=api_key,
    missing_exports=missing_exports,
    overwrite=overwrite,
    )

    trade_wide = apply_mirror_values(
        wide_dataframe=trade_wide,
        mirror_dataframe=mirror_values,
    )

    trade_panel = calculate_trade_measures(
        trade_wide
    )

    validation_report = pd.DataFrame(
        validation_records
    )

    coverage_report = (
        trade_panel[
            ~trade_panel["is_anchor_country"]
        ]
        .groupby("year")
        .agg(
            reporters_represented=(
                "reporter_code",
                "nunique",
            ),
            complete_four_flow_records=(
                "complete_four_flow_record",
                "sum",
            ),
            average_available_flows=(
                "available_flow_count",
                "mean",
            ),
        )
        .reset_index()
    )

    reporter_exports = [
        "exports_to_china_source",
        "exports_to_us_source",
    ]

    source_summary = (
        trade_panel[
            ~trade_panel["is_anchor_country"]
        ][
            ["year", *reporter_exports]
        ]
        .melt(
            id_vars="year",
            value_vars=reporter_exports,
            var_name="relationship",
            value_name="value_source",
        )
        .groupby(
            [
                "year",
                "relationship",
                "value_source",
            ],
            dropna=False,
        )
        .size()
        .reset_index(name="observations")
    )

    trade_long.to_csv(
        PROCESSED_DIRECTORY
        / "trade_total_long.csv",
        index=False,
    )

    trade_panel.to_csv(
        PROCESSED_DIRECTORY
        / "trade_total_country_year.csv",
        index=False,
    )

    mirror_values.to_csv(
        PROCESSED_DIRECTORY
        / "trade_total_mirror_values.csv",
        index=False,
    )

    validation_report.to_csv(
        TABLE_DIRECTORY
        / "trade_api_validation_report.csv",
        index=False,
    )

    coverage_report.to_csv(
        TABLE_DIRECTORY
        / "trade_coverage_by_year.csv",
        index=False,
    )

    source_summary.to_csv(
        TABLE_DIRECTORY
        / "trade_value_source_by_year.csv",
        index=False,
    )

    print("\nCollection complete.")
    print(
        "Processed panel rows:",
        len(trade_panel),
    )
    print(
        "Years:",
        trade_panel["year"].min(),
        "to",
        trade_panel["year"].max(),
    )

    return (
        trade_panel,
        coverage_report,
        validation_report,
    )


if __name__ == "__main__":
    collect_trade_history()