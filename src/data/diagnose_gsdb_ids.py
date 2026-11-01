"""Diagnose GSDB case-ID construction and Stata year encoding.

Complete runnable example.
Run from repository root:
    python -u src/data/diagnose_gsdb_ids.py
"""
from pathlib import Path
import json
import re
import pandas as pd

SOURCES = {
    "R5": (
        Path("data/raw/relations/gsdb/r5/GSDB-R5.csv"),
        Path("data/raw/relations/gsdb/r5/GSDB-R5_Dyadic.dta"),
    ),
    "FS": (
        Path("data/raw/relations/gsdb/financial/GSDB-FS.csv"),
        Path("data/raw/relations/gsdb/financial/GSDB-FS_Dyadic.dta"),
    ),
}
OUT = Path("outputs/tables/gsdb")
OUT.mkdir(parents=True, exist_ok=True)


def base_candidates(value):
    text = str(value).strip()
    candidates = {text}
    candidates.add(re.sub(r"\.0$", "", text))
    numbers = re.findall(r"\d+", text)
    candidates.update(numbers)
    if numbers:
        candidates.add(numbers[0])
    for separator in ["_", "-", ".", ":", "/"]:
        if separator in text:
            candidates.add(text.split(separator)[0])
    return {candidate for candidate in candidates if candidate != ""}


summaries = []
pattern_rows = []
match_rows = []
for name, (case_path, dyad_path) in SOURCES.items():
    case = pd.read_csv(case_path, low_memory=False)
    dyad = pd.read_stata(dyad_path, convert_categoricals=False)

    case_ids = {re.sub(r"\.0$", "", str(value).strip()) for value in case["case_id"].dropna()}
    dyad_unique = pd.Series(dyad["case_id"].dropna().astype(str).unique(), name="dyad_case_id")

    matches = []
    for value in dyad_unique:
        candidates = base_candidates(value)
        found = sorted(candidates & case_ids)
        matches.append(found[0] if found else None)
        pattern_rows.append({
            "dataset": name,
            "dyad_case_id": value,
            "candidate_base_ids": " | ".join(sorted(candidates)),
            "matched_case_id": found[0] if found else None,
        })

    matched = pd.Series(matches)
    year = dyad["year"]
    if pd.api.types.is_datetime64_any_dtype(year):
        calendar_year = year.dt.year
        year_encoding = "datetime"
    else:
        numeric = pd.to_numeric(year, errors="coerce")
        if numeric.between(1800, 2200).any():
            calendar_year = numeric
            year_encoding = "numeric_year"
        else:
            parsed = pd.to_datetime(year, errors="coerce")
            calendar_year = parsed.dt.year
            year_encoding = "parsed_datetime"

    summaries.append({
        "dataset": name,
        "case_id_dtype": str(case["case_id"].dtype),
        "dyad_case_id_dtype": str(dyad["case_id"].dtype),
        "case_ids": len(case_ids),
        "dyad_ids": len(dyad_unique),
        "dyad_ids_matching_by_candidate_base": int(matched.notna().sum()),
        "dyad_ids_unmatched": int(matched.isna().sum()),
        "matched_distinct_case_ids": int(matched.dropna().nunique()),
        "year_dtype": str(year.dtype),
        "year_encoding": year_encoding,
        "year_min": int(calendar_year.min()),
        "year_max": int(calendar_year.max()),
        "year_unique": int(calendar_year.nunique()),
    })

pd.DataFrame(summaries).to_csv(OUT / "gsdb_id_year_diagnostic_summary.csv", index=False)
pd.DataFrame(pattern_rows).to_csv(OUT / "gsdb_id_pattern_diagnostic.csv", index=False)
(OUT / "gsdb_id_year_diagnostic_summary.json").write_text(
    json.dumps(summaries, indent=2), encoding="utf-8"
)
print(json.dumps(summaries, indent=2))
print("Outputs written to:", OUT.resolve())
