"""Build global gross and TiVA-adjusted ICT-goods sourcing-orientation panels."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

CLASSIFICATION_MAP = {
    "H0": "HS1992", "H1": "HS1996", "H2": "HS2002",
    "H3": "HS2007", "H4": "HS2012", "H5": "HS2017",
    "H6": "HS2022",
}
BASKETS = (
    "include_baseline", "include_three_category",
    "include_broad_ict", "include_narrow_core",
)
ANCHORS = ("CHN", "USA")


def find_repository_root() -> Path:
    for path in [Path(__file__).resolve().parent, *Path(__file__).resolve().parents]:
        if (path / "requirements.txt").exists() and (path / "src").exists():
            return path
    raise FileNotFoundError("Repository root not found")


def orientation(us: pd.Series, china: pd.Series) -> pd.Series:
    """Return US-minus-China orientation on [-1, 1]."""
    denominator = us + china
    return (us - china).div(denominator).where(
        us.notna() & china.notna() & denominator.gt(0)
    )


def load_manifest(root: Path) -> pd.DataFrame:
    path = root / "outputs" / "tables" / "technology" / "technology_collection_manifest.csv"
    manifest = pd.read_csv(path)
    if manifest["status"].astype(str).str.startswith("error").any():
        raise ValueError("Collection manifest contains request errors")
    manifest["year"] = pd.to_numeric(manifest["year"], errors="raise").astype(int)
    manifest["hs_revision"] = manifest["expected_classification"].map(CLASSIFICATION_MAP)
    if manifest["hs_revision"].isna().any():
        bad = manifest.loc[manifest["hs_revision"].isna(), "expected_classification"].unique()
        raise ValueError(f"Unsupported manifest classifications: {bad.tolist()}")
    keys = ["reporter_iso", "year", "anchor_iso3"]
    if manifest.duplicated(keys).any():
        raise ValueError("Duplicate reporter-year-anchor rows in manifest")
    return manifest


def read_raw(root: Path) -> pd.DataFrame:
    files = sorted((root / "data" / "raw" / "un_comtrade" / "technology_trade").glob("*/*.csv"))
    frames = []
    for path in files:
        if not path.read_text(encoding="utf-8").strip():
            continue
        data = pd.read_csv(path, dtype={"cmdCode": str})
        if data.empty:
            continue
        parts = path.stem.split("_imports_from_")
        data["reporter_iso_requested"] = parts[0]
        data["anchor_iso3"] = parts[1].upper()
        data["raw_path"] = str(path.relative_to(root))
        frames.append(data)
    if not frames:
        raise FileNotFoundError("No non-empty technology-trade raw files found")
    return pd.concat(frames, ignore_index=True)


def standardise(raw: pd.DataFrame) -> pd.DataFrame:
    aliases = {
        "year": ["refYear", "period", "requested_year"],
        "reporter_iso": ["reporterISO", "reporter_iso_requested"],
        "classification_code": ["classificationCode"],
        "hs6_code": ["cmdCode"],
        "hs6_description_source": ["cmdDesc"],
        "aggr_level": ["aggrLevel"],
        "trade_value_usd": ["primaryValue"],
        "legacy_estimation_flag": ["legacyEstimationFlag"],
    }
    out = pd.DataFrame(index=raw.index)
    for target, candidates in aliases.items():
        source = next((column for column in candidates if column in raw.columns), None)
        out[target] = raw[source] if source else pd.NA
    out["anchor_iso3"] = raw["anchor_iso3"]
    out["raw_path"] = raw["raw_path"]
    out["year"] = pd.to_numeric(out["year"], errors="coerce").astype("Int64")
    out["hs6_code"] = out["hs6_code"].astype("string").str.replace(r"\.0$", "", regex=True).str.zfill(6)
    out["trade_value_usd"] = pd.to_numeric(out["trade_value_usd"], errors="coerce")
    out["hs_revision"] = out["classification_code"].map(CLASSIFICATION_MAP)
    return out


def attach_classification(long: pd.DataFrame, reference: pd.DataFrame) -> pd.DataFrame:
    ref = reference.copy()
    ref["hs6_code"] = ref["hs6_code"].astype(str).str.zfill(6)
    return long.merge(
        ref, on=["hs_revision", "hs6_code"], how="left",
        validate="many_to_one", indicator="classification_merge",
    )


def expected_counts(reference: pd.DataFrame, basket: str) -> pd.DataFrame:
    mask = reference[basket].astype("boolean").fillna(False)
    return (
        reference.loc[mask]
        .groupby("hs_revision", as_index=False)
        .agg(
            expected_hs6=("hs6_code", "nunique"),
            expected_categories=("ict_category_code", "nunique"),
        )
    )


def aggregate_basket(classified, reference, basket, manifest):
    mask = classified[basket].astype("boolean").fillna(False)
    chosen = classified.loc[mask & classified["classification_merge"].eq("both")].copy()
    keys = ["reporter_iso", "year", "anchor_iso3", "hs_revision"]
    skeleton = manifest[keys].drop_duplicates()

    observed_anchor = (
        chosen.groupby(keys, as_index=False)
        .agg(
            gross_imports_usd=("trade_value_usd", "sum"),
            observed_hs6=("hs6_code", "nunique"),
            observed_categories=("ict_category_code", "nunique"),
            estimated_rows=("legacy_estimation_flag", lambda x: pd.to_numeric(x, errors="coerce").fillna(0).ne(0).sum()),
        )
    )
    anchor = skeleton.merge(observed_anchor, on=keys, how="left", validate="one_to_one")
    for column in ["gross_imports_usd", "observed_hs6", "observed_categories", "estimated_rows"]:
        anchor[column] = anchor[column].fillna(0)
    anchor = anchor.merge(expected_counts(reference, basket), on="hs_revision", how="left", validate="many_to_one")
    anchor["returned_product_rate"] = anchor["observed_hs6"] / anchor["expected_hs6"]

    ref_categories = (
        reference.loc[reference[basket].astype("boolean").fillna(False), ["hs_revision", "ict_category_code", "ict_category_name"]]
        .drop_duplicates()
    )
    category_skeleton = skeleton.merge(ref_categories, on="hs_revision", how="left", validate="many_to_many")
    category_keys = keys + ["ict_category_code", "ict_category_name"]
    observed_category = (
        chosen.groupby(category_keys, as_index=False)
        .agg(category_imports_usd=("trade_value_usd", "sum"), observed_hs6=("hs6_code", "nunique"))
    )
    category = category_skeleton.merge(observed_category, on=category_keys, how="left", validate="one_to_one")
    category[["category_imports_usd", "observed_hs6"]] = category[["category_imports_usd", "observed_hs6"]].fillna(0)
    return anchor, category


def score_panel(anchor, category, ratios, basket, activity):
    idx = ["reporter_iso", "year"]
    wide = anchor.pivot(index=idx, columns="anchor_iso3", values="gross_imports_usd").reset_index()
    for anchor_code in ANCHORS:
        if anchor_code not in wide:
            wide[anchor_code] = 0.0
    wide = wide.rename(columns={"CHN": "china_gross_imports_usd", "USA": "us_gross_imports_usd"})
    wide["gross_orientation_score"] = orientation(wide["us_gross_imports_usd"], wide["china_gross_imports_usd"])

    cat = category.pivot(
        index=idx + ["ict_category_code", "ict_category_name"],
        columns="anchor_iso3", values="category_imports_usd",
    ).reset_index()
    for anchor_code in ANCHORS:
        if anchor_code not in cat:
            cat[anchor_code] = 0.0
    cat = cat.rename(columns={"CHN": "china_category_imports_usd", "USA": "us_category_imports_usd"})
    cat["category_orientation_score"] = orientation(cat["us_category_imports_usd"], cat["china_category_imports_usd"])
    equal = cat.groupby(idx, as_index=False).agg(
        equal_category_gross_score=("category_orientation_score", "mean"),
        available_category_scores=("category_orientation_score", "count"),
    )

    selected = ratios[ratios["tiva_activity_code"].eq(activity) & ratios["validation_status"].eq("ok")]
    ratio_values = selected.pivot(index="year", columns="anchor_iso3", values="dva_ratio").reset_index().rename(columns={"CHN": "china_dva_ratio", "USA": "us_dva_ratio"})
    ratio_status = selected.pivot(index="year", columns="anchor_iso3", values="ratio_source_status").reset_index().rename(columns={"CHN": "china_ratio_status", "USA": "us_ratio_status"})

    out = wide.merge(equal, on=idx, how="left").merge(ratio_values, on="year", how="left").merge(ratio_status, on="year", how="left")
    out["china_dva_imports_usd"] = out["china_gross_imports_usd"] * out["china_dva_ratio"]
    out["us_dva_imports_usd"] = out["us_gross_imports_usd"] * out["us_dva_ratio"]
    out["dva_adjusted_orientation_score"] = orientation(out["us_dva_imports_usd"], out["china_dva_imports_usd"])

    cat = cat.merge(ratio_values, on="year", how="left")
    cat["category_dva_score"] = orientation(
        cat["us_category_imports_usd"] * cat["us_dva_ratio"],
        cat["china_category_imports_usd"] * cat["china_dva_ratio"],
    )
    equal_dva = cat.groupby(idx, as_index=False).agg(equal_category_dva_score=("category_dva_score", "mean"))
    out = out.merge(equal_dva, on=idx, how="left")
    out["basket"] = basket
    out["tiva_activity_code"] = activity
    return out


def build(root: Path):
    manifest = load_manifest(root)
    raw = read_raw(root)
    long = standardise(raw)
    reference = pd.read_csv(root / "data" / "reference" / "unctad_ict_goods_hs6.csv", dtype={"hs6_code": str})
    classified = attach_classification(long, reference)
    ratios = pd.read_csv(root / "data" / "processed" / "tiva_technology_anchor_year.csv")
    unmatched = classified.loc[
        classified["classification_merge"].eq("left_only"),
        ["reporter_iso", "year", "anchor_iso3", "classification_code", "hs_revision", "hs6_code", "hs6_description_source", "aggr_level", "trade_value_usd", "raw_path"],
    ].copy()

    panels, categories, coverage = [], [], []
    for basket in BASKETS:
        if basket not in reference.columns:
            continue
        anchor, category = aggregate_basket(classified, reference, basket, manifest)
        anchor["basket"] = basket
        category["basket"] = basket
        coverage.append(anchor)
        categories.append(category)
        for activity in ["C26", "C26_27"]:
            panels.append(score_panel(anchor, category, ratios, basket, activity))

    sensitivity = pd.concat(panels, ignore_index=True)
    category_panel = pd.concat(categories, ignore_index=True)
    coverage_panel = pd.concat(coverage, ignore_index=True)
    baseline = sensitivity[
        sensitivity["basket"].eq("include_baseline")
        & sensitivity["tiva_activity_code"].eq("C26")
    ].copy()

    expected_country_years = manifest[["reporter_iso", "year"]].drop_duplicates()
    if len(baseline) != len(expected_country_years):
        raise ValueError(f"Baseline rows {len(baseline)} do not match manifest reporter-years {len(expected_country_years)}")

    summary = {
        "raw_rows": len(raw),
        "standardised_rows": len(long),
        "matched_classification_rows": int(classified["classification_merge"].eq("both").sum()),
        "unmatched_classification_rows": len(unmatched),
        "unmatched_trade_value_usd": float(unmatched["trade_value_usd"].sum()),
        "baseline_country_years": len(baseline),
        "baseline_scores": int(baseline["dva_adjusted_orientation_score"].notna().sum()),
        "score_min": float(baseline["dva_adjusted_orientation_score"].min()) if baseline["dva_adjusted_orientation_score"].notna().any() else None,
        "score_max": float(baseline["dva_adjusted_orientation_score"].max()) if baseline["dva_adjusted_orientation_score"].notna().any() else None,
    }
    return baseline, sensitivity, category_panel, coverage_panel, unmatched, summary


def main():
    root = find_repository_root()
    baseline, sensitivity, categories, coverage, unmatched, summary = build(root)
    processed = root / "data" / "processed"
    tables = root / "outputs" / "tables" / "technology"
    processed.mkdir(parents=True, exist_ok=True)
    tables.mkdir(parents=True, exist_ok=True)
    baseline.to_csv(processed / "technology_trade_country_year.csv", index=False)
    sensitivity.to_csv(tables / "technology_basket_sensitivity.csv", index=False)
    categories.to_csv(tables / "technology_category_composition.csv", index=False)
    coverage.to_csv(tables / "technology_product_coverage.csv", index=False)
    unmatched.to_csv(tables / "technology_unmatched_classification_rows.csv", index=False)
    (tables / "technology_summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
