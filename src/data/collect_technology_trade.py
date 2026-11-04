"""Collect annual reporter-side HS6 ICT imports from China and the United States.

Requests are grouped by year, native HS classification, anchor and product batch.
All reporters sharing the same year/classification are requested together, then the
response is split into country-specific cache files. Cache metadata makes interrupted
runs restart-safe without accepting files produced under a different basket or code list.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import time
from pathlib import Path

import certifi

os.environ.setdefault("SSL_CERT_FILE", certifi.where())
os.environ.setdefault("REQUESTS_CA_BUNDLE", certifi.where())

import comtradeapicall
import pandas as pd
from dotenv import load_dotenv

ANCHORS = {"CHN": "156", "USA": "842"}
PILOT = ("JPN", "MYS", "SGP", "VNM")
CLASSIFICATION_MAP = {
    "H0": "HS1992",
    "H1": "HS1996",
    "H2": "HS2002",
    "H3": "HS2007",
    "H4": "HS2012",
    "H5": "HS2017",
    "H6": "HS2022",
}
DEFAULT_BATCH_SIZE = 100


def find_repository_root() -> Path:
    """Find the repository root by locating requirements.txt."""

    for path in [Path(__file__).resolve().parent, *Path(__file__).resolve().parents]:
        if (path / "requirements.txt").exists():
            return path

    raise FileNotFoundError("Repository root not found")


def load_api_key(root: Path) -> str:
    """Load the Comtrade API key from the repository-root .env file."""

    load_dotenv(root / ".env")
    key = os.getenv("COMTRADE_API_KEY")

    if not key:
        raise RuntimeError(
            "COMTRADE_API_KEY not found in repository-root .env"
        )

    return key


def load_reporters(root: Path, pilot: bool) -> pd.DataFrame:
    """Load eligible reporters and their established Comtrade codes."""

    master = pd.read_csv(
        root
        / "outputs"
        / "tables"
        / "relations_condition"
        / "relationship_condition_country_master.csv"
    )
    master = master[
        master["baseline_index_eligible"].fillna(False)
    ].copy()

    if pilot:
        master = master[master["iso3"].isin(PILOT)]

    trade = (
        pd.read_csv(
            root / "data" / "processed" / "trade_total_country_year.csv",
            usecols=["reporter_iso", "reporter_code"],
        )
        .dropna()
        .drop_duplicates("reporter_iso")
    )
    trade["reporter_code"] = (
        trade["reporter_code"].astype(int).astype(str)
    )

    reporters = (
        master[["iso3", "country_name"]]
        .rename(columns={"iso3": "reporter_iso"})
        .merge(
            trade,
            on="reporter_iso",
            how="left",
            validate="one_to_one",
        )
    )

    reporters["technology_trade_available"] = reporters["reporter_code"].notna()
    reporters["technology_trade_unavailable_reason"] = pd.NA
    reporters.loc[
        reporters["reporter_code"].isna(),
        "technology_trade_unavailable_reason",
    ] = "no_established_comtrade_reporter_code"

    return reporters


def load_classification_lookup(
    root: Path,
    start_year: int,
    end_year: int,
    reporter_isos: set[str],
) -> pd.DataFrame:
    """Load native HS classifications only for requested reporter-years."""

    path = root / "data" / "processed" / "trade_total_long.csv"

    if not path.exists():
        raise FileNotFoundError(
            "Required native-classification lookup is missing: "
            "data/processed/trade_total_long.csv"
        )

    dataframe = pd.read_csv(
        path,
        usecols=["year", "reporter_iso", "classification_code"],
    )
    dataframe = dataframe[
        dataframe["year"].between(start_year, end_year)
        & dataframe["reporter_iso"].isin(reporter_isos)
    ].dropna().drop_duplicates()

    counts = dataframe.groupby(
        ["year", "reporter_iso"]
    )["classification_code"].nunique()

    if counts.gt(1).any():
        bad = counts[counts.gt(1)].index.tolist()[:10]
        raise ValueError(
            "Multiple native classifications for requested reporter-years: "
            f"{bad}"
        )

    dataframe = dataframe.drop_duplicates(["year", "reporter_iso"])
    dataframe["hs_revision"] = dataframe["classification_code"].map(
        CLASSIFICATION_MAP
    )

    unsupported = dataframe[dataframe["hs_revision"].isna()]

    if not unsupported.empty:
        details = unsupported[
            ["reporter_iso", "year", "classification_code"]
        ].sort_values(["year", "reporter_iso"])
        raise ValueError(
            "Requested reporter-years use unsupported HS classifications:\n"
            + details.to_string(index=False)
        )

    return dataframe


def load_products(root: Path, basket: str) -> pd.DataFrame:
    """Load products selected for the requested technology basket."""

    reference = pd.read_csv(
        root / "data" / "reference" / "unctad_ict_goods_hs6.csv",
        dtype={"hs6_code": str},
    )
    required = {
        "hs_revision",
        "hs6_code",
        "ict_category_code",
        "ict_category_name",
        basket,
    }

    if not required.issubset(reference.columns):
        raise ValueError(
            f"Reference missing: {sorted(required - set(reference.columns))}"
        )

    reference["hs6_code"] = reference["hs6_code"].str.zfill(6)
    mask = reference[basket].astype("boolean").fillna(False)
    return reference.loc[mask].copy()


def product_batches(codes: list[str], batch_size: int) -> list[list[str]]:
    """Split product codes into deterministic API request batches."""

    if batch_size < 1:
        raise ValueError("batch_size must be positive")

    return [
        codes[position : position + batch_size]
        for position in range(0, len(codes), batch_size)
    ]


def request_signature(
    year: int,
    classification_code: str,
    anchor_iso3: str,
    basket: str,
    codes: list[str],
) -> str:
    """Create a stable signature for cache compatibility checks."""

    payload = {
        "year": int(year),
        "classification_code": classification_code,
        "anchor_iso3": anchor_iso3,
        "basket": basket,
        "codes": sorted(codes),
    }
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def raw_file_path(
    raw_root: Path,
    year: int,
    reporter_iso: str,
    anchor_iso3: str,
) -> Path:
    """Return the country-specific raw cache path."""

    return (
        raw_root
        / str(year)
        / f"{reporter_iso}_imports_from_{anchor_iso3.lower()}.csv"
    )


def metadata_file_path(raw_path: Path) -> Path:
    """Return the metadata sidecar path for a raw cache file."""

    return raw_path.with_suffix(".meta.json")


def cache_is_compatible(raw_path: Path, signature: str) -> bool:
    """Return whether a cache file and its metadata match this request."""

    metadata_path = metadata_file_path(raw_path)

    if not raw_path.exists() or not metadata_path.exists():
        return False

    try:
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False

    return metadata.get("request_signature") == signature


def query_group(
    api_key: str,
    year: int,
    reporter_codes: list[str],
    partner_code: str,
    codes: list[str],
    max_retries: int,
) -> pd.DataFrame:
    """Retrieve one grouped reporter-year-anchor-product-batch slice."""

    last_error = None

    for attempt in range(1, max_retries + 1):
        try:
            dataframe = comtradeapicall.getFinalData(
                api_key,
                typeCode="C",
                freqCode="A",
                clCode="HS",
                period=str(year),
                reporterCode=",".join(reporter_codes),
                cmdCode=",".join(codes),
                flowCode="M",
                partnerCode=partner_code,
                partner2Code=None,
                customsCode="C00",
                motCode="0",
                maxRecords=100000,
                format_output="JSON",
                aggregateBy=None,
                breakdownMode="classic",
                countOnly=None,
                includeDesc=True,
            )

            if dataframe is None:
                raise ConnectionError("Comtrade returned no DataFrame")

            if not isinstance(dataframe, pd.DataFrame):
                raise TypeError(
                    "Comtrade returned an unexpected object: "
                    f"{type(dataframe).__name__}"
                )

            return dataframe.copy()

        except Exception as error:
            last_error = error

            if attempt < max_retries:
                time.sleep(2**attempt)

    raise RuntimeError(
        f"Comtrade request failed after {max_retries} attempts"
    ) from last_error


def write_manifest(manifest: list[dict], output_path: Path) -> None:
    """Write the current collection manifest atomically."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = output_path.with_suffix(".tmp.csv")
    pd.DataFrame(manifest).to_csv(temporary_path, index=False)
    temporary_path.replace(output_path)


def write_reporter_cache(
    dataframe: pd.DataFrame,
    raw_path: Path,
    metadata: dict,
) -> None:
    """Write a reporter cache and compatible metadata sidecar atomically."""

    raw_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_csv = raw_path.with_suffix(".tmp.csv")
    temporary_metadata = metadata_file_path(raw_path).with_suffix(
        ".tmp.json"
    )

    cache_dataframe = dataframe.copy()
    if cache_dataframe.empty and len(cache_dataframe.columns) == 0:
        cache_dataframe = pd.DataFrame(
            columns=[
                "reporterCode",
                "partnerCode",
                "period",
                "flowCode",
                "cmdCode",
                "primaryValue",
            ]
        )
    cache_dataframe.to_csv(temporary_csv, index=False)
    temporary_metadata.write_text(
        json.dumps(metadata, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary_csv.replace(raw_path)
    temporary_metadata.replace(metadata_file_path(raw_path))


def collect(
    root: Path,
    start_year: int,
    end_year: int,
    pilot: bool,
    basket: str,
    refresh: bool,
    delay: float,
    batch_size: int,
    max_retries: int,
) -> pd.DataFrame:
    """Collect technology imports with grouped, restart-safe API requests."""

    api_key = load_api_key(root)
    reporter_universe = load_reporters(root, pilot)
    reporters = reporter_universe.loc[
        reporter_universe["technology_trade_available"]
    ].copy()
    classifications = load_classification_lookup(
        root,
        start_year,
        end_year,
        set(reporters["reporter_iso"]),
    )
    products = load_products(root, basket)

    coverage = (
        reporter_universe.assign(_key=1)
        .merge(
            pd.DataFrame(
                {"year": range(start_year, end_year + 1), "_key": 1}
            ),
            on="_key",
        )
        .drop(columns="_key")
        .merge(
            classifications,
            on=["year", "reporter_iso"],
            how="left",
            validate="one_to_one",
        )
    )
    coverage["technology_trade_status"] = "available"
    coverage.loc[
        coverage["reporter_code"].isna(),
        "technology_trade_status",
    ] = "unavailable_missing_reporter_code"
    coverage.loc[
        coverage["reporter_code"].notna() & coverage["hs_revision"].isna(),
        "technology_trade_status",
    ] = "unavailable_missing_native_classification"
    coverage_path = (
        root / "outputs" / "tables" / "technology"
        / "technology_reporter_year_coverage.csv"
    )
    coverage_path.parent.mkdir(parents=True, exist_ok=True)
    coverage.to_csv(coverage_path, index=False)

    grid = (
        reporters.merge(
            classifications,
            on="reporter_iso",
            how="inner",
            validate="one_to_many",
        )
        .sort_values(["year", "reporter_iso"])
        .reset_index(drop=True)
    )

    if grid.empty:
        raise ValueError("No reporter-years have supported native classifications")

    raw_root = (
        root / "data" / "raw" / "un_comtrade" / "technology_trade"
    )
    manifest_path = (
        root
        / "outputs"
        / "tables"
        / "technology"
        / "technology_collection_manifest.csv"
    )
    manifest: list[dict] = []

    groups = list(
        grid.groupby(
            ["year", "classification_code", "hs_revision"],
            sort=True,
        )
    )
    request_plan = []

    for (year, classification_code, hs_revision), group in groups:
        codes = sorted(
            products.loc[
                products["hs_revision"].eq(hs_revision),
                "hs6_code",
            ].unique()
        )

        if not codes:
            raise ValueError(
                f"No {basket} codes for {hs_revision}"
            )

        for anchor_iso3, partner_code in ANCHORS.items():
            signature = request_signature(
                year,
                classification_code,
                anchor_iso3,
                basket,
                codes,
            )
            pending_rows = []

            for row in group.itertuples(index=False):
                path = raw_file_path(
                    raw_root,
                    year,
                    row.reporter_iso,
                    anchor_iso3,
                )

                if not refresh and cache_is_compatible(path, signature):
                    cached = pd.read_csv(path, dtype={"cmdCode": str}) if path.read_text(encoding="utf-8").strip() else pd.DataFrame(columns=["reporterCode", "partnerCode", "period", "flowCode", "cmdCode", "primaryValue"])
                    manifest.append(
                        {
                            "year": year,
                            "reporter_iso": row.reporter_iso,
                            "anchor_iso3": anchor_iso3,
                            "expected_classification": classification_code,
                            "hs_revision": hs_revision,
                            "basket": basket,
                            "requested_hs6": len(codes),
                            "status": "cached",
                            "rows": len(cached),
                            "returned_hs6": (
                                cached["cmdCode"].astype(str).nunique()
                                if "cmdCode" in cached.columns
                                else 0
                            ),
                            "raw_path": str(path.relative_to(root)),
                        }
                    )
                else:
                    pending_rows.append(row)

            if pending_rows:
                request_plan.append(
                    {
                        "year": year,
                        "classification_code": classification_code,
                        "hs_revision": hs_revision,
                        "anchor_iso3": anchor_iso3,
                        "partner_code": partner_code,
                        "codes": codes,
                        "signature": signature,
                        "rows": pending_rows,
                    }
                )

    write_manifest(manifest, manifest_path)
    total_calls = sum(
        len(product_batches(item["codes"], batch_size))
        for item in request_plan
    )
    completed_calls = 0

    print(
        f"Planned API calls: {total_calls:,}; "
        f"compatible cached slices: {len(manifest):,}"
    )

    for item in request_plan:
        reporter_codes = [row.reporter_code for row in item["rows"]]
        batches = product_batches(item["codes"], batch_size)
        frames = []
        group_failed = None

        for batch_number, batch in enumerate(batches, start=1):
            completed_calls += 1
            print(
                f"[{completed_calls}/{total_calls}] "
                f"{item['year']} {item['classification_code']} "
                f"imports from {item['anchor_iso3']} | "
                f"{len(reporter_codes)} reporters | "
                f"product batch {batch_number}/{len(batches)}"
            )

            try:
                frames.append(
                    query_group(
                        api_key,
                        item["year"],
                        reporter_codes,
                        item["partner_code"],
                        batch,
                        max_retries,
                    )
                )
            except Exception as error:
                group_failed = error
                break

            if delay > 0 and completed_calls < total_calls:
                time.sleep(delay)

        if group_failed is not None:
            for row in item["rows"]:
                path = raw_file_path(
                    raw_root,
                    item["year"],
                    row.reporter_iso,
                    item["anchor_iso3"],
                )
                manifest.append(
                    {
                        "year": item["year"],
                        "reporter_iso": row.reporter_iso,
                        "anchor_iso3": item["anchor_iso3"],
                        "expected_classification": item[
                            "classification_code"
                        ],
                        "hs_revision": item["hs_revision"],
                        "basket": basket,
                        "requested_hs6": len(item["codes"]),
                        "status": f"error:{type(group_failed).__name__}",
                        "rows": 0,
                        "returned_hs6": 0,
                        "raw_path": str(path.relative_to(root)),
                    }
                )
            write_manifest(manifest, manifest_path)
            continue

        combined = (
            pd.concat(frames, ignore_index=True)
            if frames
            else pd.DataFrame()
        )

        if not combined.empty and "reporterCode" not in combined.columns:
            raise ValueError(
                "Grouped Comtrade response lacks reporterCode"
            )

        for row in item["rows"]:
            path = raw_file_path(
                raw_root,
                item["year"],
                row.reporter_iso,
                item["anchor_iso3"],
            )
            reporter_code = int(row.reporter_code)

            if combined.empty:
                reporter_data = combined.copy()
            else:
                reporter_data = combined[
                    pd.to_numeric(
                        combined["reporterCode"],
                        errors="coerce",
                    ).eq(reporter_code)
                ].copy()

            status = (
                "downloaded"
                if not reporter_data.empty
                else "downloaded_empty"
            )
            metadata = {
                "request_signature": item["signature"],
                "year": int(item["year"]),
                "reporter_iso": row.reporter_iso,
                "reporter_code": row.reporter_code,
                "anchor_iso3": item["anchor_iso3"],
                "classification_code": item["classification_code"],
                "hs_revision": item["hs_revision"],
                "basket": basket,
                "requested_hs6": len(item["codes"]),
                "status": status,
            }
            write_reporter_cache(reporter_data, path, metadata)
            manifest.append(
                {
                    "year": item["year"],
                    "reporter_iso": row.reporter_iso,
                    "anchor_iso3": item["anchor_iso3"],
                    "expected_classification": item[
                        "classification_code"
                    ],
                    "hs_revision": item["hs_revision"],
                    "basket": basket,
                    "requested_hs6": len(item["codes"]),
                    "status": status,
                    "rows": len(reporter_data),
                    "returned_hs6": (
                        reporter_data["cmdCode"].astype(str).nunique()
                        if "cmdCode" in reporter_data.columns
                        else 0
                    ),
                    "raw_path": str(path.relative_to(root)),
                }
            )

        write_manifest(manifest, manifest_path)

    result = pd.DataFrame(manifest).sort_values(
        ["year", "reporter_iso", "anchor_iso3"]
    ).reset_index(drop=True)
    write_manifest(result.to_dict("records"), manifest_path)
    return result


def main() -> None:
    """Run the command-line collector."""

    parser = argparse.ArgumentParser()
    parser.add_argument("--start-year", type=int, default=2022)
    parser.add_argument("--end-year", type=int, default=2022)
    parser.add_argument("--full-universe", action="store_true")
    parser.add_argument("--basket", default="include_broad_ict")
    parser.add_argument("--refresh", action="store_true")
    parser.add_argument("--delay", type=float, default=1.1)
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE)
    parser.add_argument("--max-retries", type=int, default=3)
    arguments = parser.parse_args()

    root = find_repository_root()
    result = collect(
        root,
        arguments.start_year,
        arguments.end_year,
        not arguments.full_universe,
        arguments.basket,
        arguments.refresh,
        arguments.delay,
        arguments.batch_size,
        arguments.max_retries,
    )
    print(result["status"].value_counts(dropna=False).to_string())


if __name__ == "__main__":
    main()
