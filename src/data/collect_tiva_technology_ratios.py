"""Collect OECD TiVA anchor-year technology-sector DVA ratios.

Baseline activity: C26 (computer, electronic and optical products).
Sensitivity: C26_27 (C26 plus electrical equipment).
Raw responses are cached locally under data/raw/oecd_tiva/technology.
"""
from __future__ import annotations
import argparse, random, time
from io import StringIO
from pathlib import Path
import pandas as pd
import requests

BASE_URL = "https://sdmx.oecd.org/sti-public/rest/data/OECD.STI.PIE,DSD_TIVA_MAINLV@DF_MAINLV,1.1"
MEASURES = ("EXGR", "EXGR_DVA")
ANCHORS = ("CHN", "USA")
ACTIVITIES = ("C26", "C26_27")


def find_repository_root() -> Path:
    for p in [Path(__file__).resolve().parent, *Path(__file__).resolve().parents]:
        if (p / "requirements.txt").exists():
            return p
    raise FileNotFoundError("Could not find repository root containing requirements.txt")


def _normalise_columns(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out.columns = [str(c).strip().upper().replace(" ", "_") for c in out.columns]
    return out


def download_tiva(root: Path, start_year: int, end_year: int, refresh: bool=False, max_attempts: int=6) -> pd.DataFrame:
    cache_dir = root / "data" / "raw" / "oecd_tiva" / "technology"
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache = cache_dir / f"tiva_c26_c26_27_anchors_{start_year}_{end_year}.csv"
    if cache.exists() and not refresh:
        return pd.read_csv(cache)
    key = f"{'+'.join(MEASURES)}.{'+'.join(ANCHORS)}.{'+'.join(ACTIVITIES)}.W..A"
    url = f"{BASE_URL}/{key}"
    params = {"startPeriod": str(start_year), "endPeriod": str(end_year),
              "dimensionAtObservation": "AllDimensions", "format": "csvfile"}
    session = requests.Session()
    session.headers.update({"Accept": "text/csv", "User-Agent": "DS608-US-China-Closeness-Index/1.0"})
    for attempt in range(max_attempts):
        response = session.get(url, params=params, timeout=(15, 180))
        if response.status_code == 429:
            delay = float(response.headers.get("Retry-After", min(60, 2**attempt) + random.random()))
            time.sleep(delay); continue
        response.raise_for_status()
        raw = pd.read_csv(StringIO(response.text))
        if raw.empty:
            raise ValueError("OECD returned no observations")
        raw.to_csv(cache, index=False)
        return raw
    raise RuntimeError("OECD request remained rate limited")


def build_ratios(raw: pd.DataFrame, extend_to: int=2024) -> pd.DataFrame:
    df = _normalise_columns(raw)
    aliases = {
        "REF_AREA": ["REF_AREA", "REFERENCE_AREA"], "ACTIVITY": ["ACTIVITY", "ECONOMIC_ACTIVITY"],
        "MEASURE": ["MEASURE"], "TIME_PERIOD": ["TIME_PERIOD"], "OBS_VALUE": ["OBS_VALUE"]}
    resolved = {}
    for key, candidates in aliases.items():
        resolved[key] = next((c for c in candidates if c in df.columns), None)
        if resolved[key] is None: raise ValueError(f"Missing OECD column for {key}; columns={df.columns.tolist()}")
    d = df[[resolved[x] for x in aliases]].copy(); d.columns = list(aliases)
    d["TIME_PERIOD"] = pd.to_numeric(d["TIME_PERIOD"], errors="raise").astype(int)
    d["OBS_VALUE"] = pd.to_numeric(d["OBS_VALUE"], errors="coerce")
    d = d[d["REF_AREA"].isin(ANCHORS) & d["ACTIVITY"].isin(ACTIVITIES) & d["MEASURE"].isin(MEASURES)]
    if d.duplicated(["REF_AREA","ACTIVITY","TIME_PERIOD","MEASURE"]).any():
        raise ValueError("Duplicate OECD observations found")
    wide = d.pivot(index=["REF_AREA","ACTIVITY","TIME_PERIOD"], columns="MEASURE", values="OBS_VALUE").reset_index()
    wide["dva_ratio"] = wide["EXGR_DVA"] / wide["EXGR"]
    wide["validation_status"] = "ok"
    wide.loc[wide["EXGR"].isna() | wide["EXGR_DVA"].isna(), "validation_status"] = "missing_measure"
    wide.loc[wide["EXGR"] <= 0, "validation_status"] = "invalid_gross_exports"
    wide.loc[~wide["dva_ratio"].between(0,1), "validation_status"] = "ratio_out_of_bounds"
    wide = wide.rename(columns={"REF_AREA":"anchor_iso3","ACTIVITY":"tiva_activity_code","TIME_PERIOD":"year",
                                "EXGR":"gross_exports_usd_mn","EXGR_DVA":"domestic_va_usd_mn"})
    wide["ratio_source_year"] = wide["year"]; wide["ratio_source_status"] = "observed"
    additions=[]
    for (anchor, activity), g in wide[wide.validation_status.eq("ok")].groupby(["anchor_iso3","tiva_activity_code"]):
        latest=g.sort_values("year").iloc[-1]
        for year in range(int(latest.year)+1, extend_to+1):
            row=latest.copy(); row["year"]=year; row["ratio_source_year"]=int(latest.year); row["ratio_source_status"]="carried_forward"
            additions.append(row)
    if additions: wide=pd.concat([wide,pd.DataFrame(additions)],ignore_index=True)
    names={"CHN":"China","USA":"United States"}; acts={"C26":"Computer, electronic and optical products","C26_27":"C26 plus electrical equipment"}
    wide["anchor_name"]=wide.anchor_iso3.map(names); wide["tiva_activity_name"]=wide.tiva_activity_code.map(acts)
    cols=["anchor_iso3","anchor_name","year","tiva_activity_code","tiva_activity_name","gross_exports_usd_mn","domestic_va_usd_mn","dva_ratio","ratio_source_year","ratio_source_status","validation_status"]
    return wide[cols].sort_values(["tiva_activity_code","anchor_iso3","year"]).reset_index(drop=True)


def main() -> None:
    p=argparse.ArgumentParser(); p.add_argument("--start-year",type=int,default=2004); p.add_argument("--end-year",type=int,default=2022); p.add_argument("--extend-to",type=int,default=2024); p.add_argument("--refresh",action="store_true")
    args=p.parse_args(); root=find_repository_root(); raw=download_tiva(root,args.start_year,args.end_year,args.refresh); panel=build_ratios(raw,args.extend_to)
    out=root/"data"/"processed"/"tiva_technology_anchor_year.csv"; out.parent.mkdir(parents=True,exist_ok=True); panel.to_csv(out,index=False)
    print(f"Saved {len(panel):,} rows to {out.relative_to(root)}")

if __name__ == "__main__": main()
