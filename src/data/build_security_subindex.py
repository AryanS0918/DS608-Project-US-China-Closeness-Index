"""Build the country-year security subindex from production component panels."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import numpy as np
import pandas as pd

VALID_ARMS_STATUSES = {
    "available",
    "no_observed_anchor_transfers",
    "no_observed_arms_imports",
}

def _require_columns(df: pd.DataFrame, required: set[str], label: str) -> None:
    missing = sorted(required - set(df.columns))
    if missing:
        raise ValueError(f"{label} missing required columns: {missing}")

def validate_institutional(df: pd.DataFrame) -> None:
    required = {"country_iso3", "preferred_country_name", "anchor", "year", "security_institutional_score_raw"}
    _require_columns(df, required, "Institutional panel")
    if df.duplicated(["country_iso3", "year", "anchor"]).any():
        raise ValueError("Duplicate institutional country-year-anchor keys detected.")
    if df["security_institutional_score_raw"].isna().any():
        raise ValueError("Institutional scores contain missing values.")
    if not df["security_institutional_score_raw"].between(0, 1).all():
        raise ValueError("Institutional scores fall outside [0, 1].")

def validate_arms(df: pd.DataFrame) -> None:
    required = {"iso3", "preferred_country_name", "year", "arms_transfer_score", "observation_status"}
    _require_columns(df, required, "Arms panel")
    if df.duplicated(["iso3", "year"]).any():
        raise ValueError("Duplicate arms country-year keys detected.")
    unexpected = sorted(set(df["observation_status"].dropna()) - VALID_ARMS_STATUSES)
    if unexpected:
        raise ValueError(f"Unexpected arms statuses: {unexpected}")
    available_bad = df["observation_status"].eq("available") & df["arms_transfer_score"].isna()
    zero_bad = df["observation_status"].eq("no_observed_anchor_transfers") & (df["arms_transfer_score"].isna() | df["arms_transfer_score"].ne(0))
    missing_bad = df["observation_status"].eq("no_observed_arms_imports") & df["arms_transfer_score"].notna()
    if available_bad.any() or zero_bad.any() or missing_bad.any():
        raise ValueError("Arms observation-status validation failed.")
    observed = df["arms_transfer_score"].dropna()
    if not observed.between(-1, 1).all():
        raise ValueError("Observed arms scores fall outside [-1, 1].")

def build_security_subindex(institutional_raw: pd.DataFrame, arms_raw: pd.DataFrame) -> pd.DataFrame:
    validate_institutional(institutional_raw)
    validate_arms(arms_raw)
    inst = institutional_raw.copy()
    inst["anchor_standard"] = inst["anchor"].astype("string").str.strip().str.lower().map({
        "united states": "US", "united states of america": "US", "us": "US", "usa": "US",
        "china": "China", "people's republic of china": "China", "prc": "China",
    })
    if inst["anchor_standard"].isna().any():
        bad=sorted(inst.loc[inst["anchor_standard"].isna(), "anchor"].astype(str).unique())
        raise ValueError(f"Unrecognised institutional anchor labels: {bad}")
    wide = inst.pivot(index=["country_iso3", "preferred_country_name", "year"], columns="anchor_standard", values="security_institutional_score_raw").reset_index()
    if not {"US", "China"}.issubset(wide.columns):
        raise ValueError("Institutional panel must contain US and China anchor scores.")
    wide = wide.rename(columns={"country_iso3":"iso3", "US":"us_institutional_score", "China":"china_institutional_score"})
    wide["institutional_signed_score"] = wide["us_institutional_score"] - wide["china_institutional_score"]
    merged = wide.merge(
        arms_raw[["iso3","preferred_country_name","year","arms_transfer_score","observation_status"]].rename(columns={"preferred_country_name":"arms_country_name"}),
        on=["iso3","year"], how="outer", indicator=True, validate="one_to_one"
    )
    if not merged["_merge"].eq("both").all():
        raise ValueError(f"Component keys do not align: {merged['_merge'].value_counts().to_dict()}")
    if not merged["preferred_country_name"].eq(merged["arms_country_name"]).all():
        raise ValueError("Preferred country names disagree across component panels.")
    merged["arms_observation_status"] = merged["observation_status"]
    merged["security_integration_status"] = np.select(
        [merged["arms_observation_status"].eq("available"), merged["arms_observation_status"].eq("no_observed_anchor_transfers"), merged["arms_observation_status"].eq("no_observed_arms_imports")],
        ["institutional_and_arms_available", "institutional_plus_observed_zero_arms", "institutional_only_no_observed_arms_imports"],
        default="invalid"
    )
    observed = merged["arms_transfer_score"].notna()
    merged["security_score"] = np.where(observed, 0.5*merged["institutional_signed_score"] + 0.5*merged["arms_transfer_score"], merged["institutional_signed_score"])
    out = merged[["iso3","preferred_country_name","year","institutional_signed_score","arms_transfer_score","arms_observation_status","security_integration_status","security_score"]].sort_values(["iso3","year"]).reset_index(drop=True)
    if out.duplicated(["iso3","year"]).any() or out["security_score"].isna().any() or not out["security_score"].between(-1,1).all():
        raise ValueError("Final security panel validation failed.")
    return out

def write_audits(out: pd.DataFrame, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    summary = {
        "rows": int(len(out)), "entities": int(out["iso3"].nunique()),
        "first_year": int(out["year"].min()), "last_year": int(out["year"].max()),
        "duplicate_country_years": int(out.duplicated(["iso3","year"]).sum()),
        "missing_security_scores": int(out["security_score"].isna().sum()),
        "score_min": float(out["security_score"].min()), "score_max": float(out["security_score"].max()),
        "integration_status_counts": {k:int(v) for k,v in out["security_integration_status"].value_counts().items()},
    }
    (output_dir/"security_subindex_summary.json").write_text(json.dumps(summary, indent=2)+"\n")
    observed=out["arms_transfer_score"].notna()
    sensitivity=out[["iso3","preferred_country_name","year","security_score"]].copy()
    sensitivity["security_score_institutional_emphasis"] = np.where(observed, (2/3)*out["institutional_signed_score"]+(1/3)*out["arms_transfer_score"], out["institutional_signed_score"])
    sensitivity["security_score_arms_emphasis"] = np.where(observed, (1/3)*out["institutional_signed_score"]+(2/3)*out["arms_transfer_score"], out["institutional_signed_score"])
    sensitivity.to_csv(output_dir/"security_weighting_sensitivity.csv", index=False)
    disagreements=out.loc[observed].copy()
    disagreements["component_gap"]=(disagreements["institutional_signed_score"]-disagreements["arms_transfer_score"]).abs()
    zero=disagreements["institutional_signed_score"].eq(0)|disagreements["arms_transfer_score"].eq(0)
    disagreements["component_sign_agreement"] = np.select([zero, np.sign(disagreements["institutional_signed_score"])==np.sign(disagreements["arms_transfer_score"])], ["at_least_one_zero","same_sign"], default="opposite_sign")
    disagreements.sort_values("component_gap",ascending=False).to_csv(output_dir/"security_component_disagreement_cases.csv",index=False)

def main() -> None:
    p=argparse.ArgumentParser()
    p.add_argument("--institutional", type=Path, default=Path("data/processed/security_institutional_ties_country_anchor_year.csv"))
    p.add_argument("--arms", type=Path, default=Path("data/processed/sipri_arms_country_year.csv"))
    p.add_argument("--output", type=Path, default=Path("data/processed/security_subindex_country_year.csv"))
    p.add_argument("--audit-dir", type=Path, default=Path("outputs/tables/security_subindex"))
    a=p.parse_args()
    out=build_security_subindex(pd.read_csv(a.institutional), pd.read_csv(a.arms))
    a.output.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(a.output,index=False)
    write_audits(out,a.audit_dir)
    print(f"Wrote {len(out):,} rows to {a.output}")
if __name__ == "__main__": main()
