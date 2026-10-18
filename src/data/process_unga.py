"""Build the refined US-China UNGA voting indicator.

Complete runnable module.

The module ingests the updated UNGA workbook plus the legacy workbook for years
not included in the update, standardises votes, removes duplicate resolutions,
classifies US-China disagreement votes, and writes country-year indicators and
quality-control reports.
"""
from __future__ import annotations

import argparse
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

VALID_VOTES = {"Y", "N", "A"}
SUMMARY_LABELS = {
    "YES", "NO", "ABSTAIN", "ABSENTEES", "DIDN'T VOTE", "DIDNT VOTE",
    "TOTAL", "CHECK", "CHECK: CHINA AND US VOTED THE SAME WAY",
}
RESOLUTION_PATTERN = re.compile(r"^A/(?:RES|DEC)/", re.IGNORECASE)


@dataclass(frozen=True)
class SourceSpec:
    workbook: Path
    sheet: str
    source_priority: int
    keep_years: tuple[int, ...] | None = None


def text_key(value: object) -> str:
    if pd.isna(value):
        return ""
    text = str(value).strip().upper()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.replace("&", " AND ")
    text = re.sub(r"[^A-Z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


COUNTRY_ALIASES = {
    "ANTIGUA BARBUDA": "ANTIGUA AND BARBUDA",
    "BOLIVIA": "BOLIVIA PLURINATIONAL STATE OF",
    "BRUNEI": "BRUNEI DARUSSALAM",
    "CAPE VERDE": "CABO VERDE",
    "CZECH REPUBLIC": "CZECHIA",
    "CONGO": "REPUBLIC OF THE CONGO",
    "CONGO DEMOCRATIC REPUBLIC": "DEMOCRATIC REPUBLIC OF THE CONGO",
    "COTE D IVOIRE": "COTE D IVOIRE",
    "IVORY COAST": "COTE D IVOIRE",
    "DEMOCRATIC PEOPLE S REPUBLIC OF KOREA": "NORTH KOREA",
    "IRAN": "IRAN ISLAMIC REPUBLIC OF",
    "LAOS": "LAO PEOPLE S DEMOCRATIC REPUBLIC",
    "MICRONESIA FED STATES OF": "FEDERATED STATES OF MICRONESIA",
    "MICRONESIA FEDERATED STATES OF": "FEDERATED STATES OF MICRONESIA",
    "MOLDOVA": "REPUBLIC OF MOLDOVA",
    "NETHERLANDS KINGDOM OF THE": "NETHERLANDS",
    "REPUBLIC OF KOREA": "SOUTH KOREA",
    "RUSSIA": "RUSSIAN FEDERATION",
    "SYRIA": "SYRIAN ARAB REPUBLIC",
    "TANZANIA": "UNITED REPUBLIC OF TANZANIA",
    "TURKEY": "TURKIYE",
    "VENEZUELA": "VENEZUELA BOLIVARIAN REPUBLIC OF",
    "VIETNAM": "VIET NAM",
}


def country_key(value: object) -> str:
    key = text_key(value)
    return COUNTRY_ALIASES.get(key, key)


def clean_resolution(value: object) -> str:
    if pd.isna(value):
        return ""
    text = re.sub(r"\s+", " ", str(value).strip())
    text = re.sub(r"^Resolution\s*", "", text, flags=re.IGNORECASE)
    if text.upper().startswith("/RES/"):
        text = "A" + text
    text = re.sub(r"\s+([AB])$", r"[\1]", text)
    text = text.replace(" [", "[")
    return text.upper()


def standardise_vote(value: object) -> tuple[str | None, str]:
    if pd.isna(value) or str(value).strip() == "":
        return None, "absent"
    vote = str(value).strip().upper()
    if vote in VALID_VOTES:
        return vote, {"Y": "yes", "N": "no", "A": "abstain"}[vote]
    if vote in {"X", "ABSENT", "DIDN'T VOTE", "DIDNT VOTE"}:
        return None, "absent"
    if vote in {"NM", "NOT A MEMBER", "NOT MEMBER"}:
        return None, "not_member"
    return None, "invalid"


def parse_matrix_sheet(spec: SourceSpec) -> tuple[pd.DataFrame, pd.DataFrame]:
    raw = pd.read_excel(spec.workbook, sheet_name=spec.sheet, header=None, engine="openpyxl")
    if raw.shape[0] < 3:
        raise ValueError(f"{spec.sheet}: too few rows")

    resolution_cols = []
    for col in raw.columns:
        resolution = clean_resolution(raw.iat[1, col])
        if RESOLUTION_PATTERN.match(resolution):
            resolution_cols.append(col)
    if not resolution_cols:
        raise ValueError(f"{spec.sheet}: no resolution columns found")

    first_resolution_col = min(resolution_cols)
    country_col = first_resolution_col - 1
    if country_col < 0:
        raise ValueError(f"{spec.sheet}: could not identify country column")

    # Sheet-name year is a reliable fallback for single-year tabs.
    sheet_year = int(spec.sheet) if spec.sheet.isdigit() else None
    year_values = pd.to_numeric(raw.iloc[0], errors="coerce").ffill()

    country_rows = []
    for row in range(2, raw.shape[0]):
        name = raw.iat[row, country_col]
        key = text_key(name)
        if not key:
            continue
        if key in SUMMARY_LABELS:
            break
        # Country rows have vote-like content across the resolution columns.
        row_values = raw.iloc[row, resolution_cols]
        vote_like = row_values.astype("string").str.strip().str.upper().isin(
            ["Y", "N", "A", "X", "NM"]
        ).sum()
        if vote_like == 0:
            continue
        country_rows.append(row)

    records = []
    exceptions = []
    for col in resolution_cols:
        resolution_raw = raw.iat[1, col]
        resolution_id = clean_resolution(resolution_raw)
        year = year_values.iat[col]
        if pd.isna(year):
            year = sheet_year
        if year is None or pd.isna(year):
            exceptions.append({
                "source_workbook": spec.workbook.name,
                "source_sheet": spec.sheet,
                "cell": f"R2C{col+1}",
                "issue": "missing_year",
                "value": resolution_raw,
            })
            continue
        year = int(year)
        if spec.keep_years is not None and year not in spec.keep_years:
            continue

        for row in country_rows:
            country_raw = str(raw.iat[row, country_col]).strip()
            vote_raw = raw.iat[row, col]
            vote, status = standardise_vote(vote_raw)
            if status == "invalid":
                exceptions.append({
                    "source_workbook": spec.workbook.name,
                    "source_sheet": spec.sheet,
                    "cell": f"R{row+1}C{col+1}",
                    "issue": "invalid_vote_code",
                    "value": vote_raw,
                    "country_name_raw": country_raw,
                    "year": year,
                    "resolution_id": resolution_id,
                })
            records.append({
                "year": year,
                "resolution_id": resolution_id,
                "resolution_id_raw": resolution_raw,
                "country_key": country_key(country_raw),
                "country_name_raw": country_raw,
                "vote_raw": vote_raw,
                "vote": vote,
                "vote_status": status,
                "source_workbook": spec.workbook.name,
                "source_sheet": spec.sheet,
                "source_priority": spec.source_priority,
                "source_column": col + 1,
            })

    return pd.DataFrame(records), pd.DataFrame(exceptions)


def build_source_specs(updated: Path, legacy: Path) -> list[SourceSpec]:
    # Updated workbook is authoritative where it explicitly contains data.
    return [
        SourceSpec(updated, "2012-Back", 30, tuple(range(1900, 2013))),
        SourceSpec(legacy, "UNGA Votes By Resolution", 10, tuple(range(2013, 2024))),
        SourceSpec(updated, "2024", 30, (2024,)),
        SourceSpec(updated, "2025", 30, (2025,)),
        SourceSpec(updated, "2026", 30, (2026,)),
    ]


def deduplicate(long_votes: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    long_votes = long_votes.sort_values(
        ["year", "resolution_id", "country_key", "source_priority"],
        ascending=[True, True, True, False],
    )
    group_cols = ["year", "resolution_id", "country_key"]
    duplicated = long_votes[long_votes.duplicated(group_cols, keep=False)].copy()
    audit = pd.DataFrame()
    if not duplicated.empty:
        top_priority = duplicated.groupby(group_cols)["source_priority"].transform("max")
        top = duplicated[top_priority.eq(duplicated["source_priority"])].copy()
        conflict = (
            top.assign(signature=top["vote"].fillna("<NA>") + "|" + top["vote_status"])
            .groupby(group_cols)["signature"].nunique().gt(1)
            .rename("conflict_at_top_priority")
        )
        audit = (
            duplicated.groupby(group_cols).agg(
                rows_found=("country_key", "size"),
                top_priority_rows=("source_priority", lambda s: (s == s.max()).sum()),
                chosen_source=("source_sheet", "first"),
            ).join(conflict).reset_index()
        )
    deduped = long_votes.drop_duplicates(group_cols, keep="first").copy()
    return deduped, audit


def choose_country_names(votes: pd.DataFrame) -> pd.DataFrame:
    names = (
        votes.sort_values(["country_key", "year", "source_priority"], ascending=[True, False, False])
        .drop_duplicates("country_key")[["country_key", "country_name_raw"]]
        .rename(columns={"country_name_raw": "country_name"})
    )
    return names


def classify_resolutions(votes: pd.DataFrame) -> pd.DataFrame:
    anchors = votes[votes["country_key"].isin(["UNITED STATES", "CHINA"])].copy()
    anchor_wide = anchors.pivot_table(
        index=["year", "resolution_id"],
        columns="country_key",
        values="vote",
        aggfunc="first",
        dropna=True,
    ).reset_index()
    for col in ["UNITED STATES", "CHINA"]:
        if col not in anchor_wide.columns:
            anchor_wide[col] = pd.NA
    anchor_wide = anchor_wide.rename(columns={"UNITED STATES": "us_vote", "CHINA": "china_vote"})
    anchor_wide["anchors_valid"] = anchor_wide["us_vote"].isin(VALID_VOTES) & anchor_wide["china_vote"].isin(VALID_VOTES)
    anchor_wide["broad_eligible"] = anchor_wide["anchors_valid"] & (anchor_wide["us_vote"] != anchor_wide["china_vote"])
    anchor_wide["strict_yn_eligible"] = (
        ((anchor_wide["us_vote"] == "Y") & (anchor_wide["china_vote"] == "N"))
        | ((anchor_wide["us_vote"] == "N") & (anchor_wide["china_vote"] == "Y"))
    )
    anchor_wide["exclusion_reason"] = np.select(
        [
            ~anchor_wide["anchors_valid"],
            anchor_wide["anchors_valid"] & (anchor_wide["us_vote"] == anchor_wide["china_vote"]),
        ],
        ["missing_or_invalid_anchor_vote", "anchors_agreed"],
        default="eligible_disagreement",
    )
    return anchor_wide


def score_country_year(votes: pd.DataFrame, anchor_audit: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    enriched = votes.merge(anchor_audit, on=["year", "resolution_id"], how="left", validate="many_to_one")
    enriched["participated"] = enriched["vote"].isin(VALID_VOTES)
    enriched["alignment_score_broad"] = np.where(
        enriched["broad_eligible"] & enriched["participated"],
        np.where(
            enriched["vote"] == enriched["us_vote"],
            1.0,
            np.where(enriched["vote"] == enriched["china_vote"], -1.0, 0.0),
        ),
        np.nan,
    )
    enriched["alignment_score_strict"] = np.where(
        enriched["strict_yn_eligible"] & enriched["participated"],
        np.where(
            enriched["vote"] == enriched["us_vote"],
            1.0,
            np.where(enriched["vote"] == enriched["china_vote"], -1.0, 0.0),
        ),
        np.nan,
    )

    nonanchors = enriched[~enriched["country_key"].isin(["UNITED STATES", "CHINA"])].copy()
    grouped = nonanchors.groupby(["country_key", "year"], observed=True)
    country_year = grouped.agg(
        total_resolutions=("resolution_id", "nunique"),
        broad_eligible_resolutions=("broad_eligible", "sum"),
        strict_yn_eligible_resolutions=("strict_yn_eligible", "sum"),
        broad_participated_votes=("alignment_score_broad", "count"),
        strict_participated_votes=("alignment_score_strict", "count"),
        broad_score_sum=("alignment_score_broad", "sum"),
        strict_score_sum=("alignment_score_strict", "sum"),
        absent_observations=("vote_status", lambda s: (s == "absent").sum()),
        not_member_observations=("vote_status", lambda s: (s == "not_member").sum()),
        invalid_observations=("vote_status", lambda s: (s == "invalid").sum()),
    ).reset_index()

    # Counts have clearer interpretations than summing alone.
    detail = nonanchors[nonanchors["broad_eligible"] & nonanchors["participated"]].copy()
    detail["with_us"] = detail["alignment_score_broad"] == 1
    detail["with_china"] = detail["alignment_score_broad"] == -1
    detail["neutral_third_position"] = detail["alignment_score_broad"] == 0
    counts = detail.groupby(["country_key", "year"]).agg(
        votes_with_us=("with_us", "sum"),
        votes_with_china=("with_china", "sum"),
        neutral_third_position_votes=("neutral_third_position", "sum"),
        abstentions_on_broad_eligible=("vote", lambda s: (s == "A").sum()),
    ).reset_index()
    country_year = country_year.merge(counts, on=["country_key", "year"], how="left")
    count_cols = ["votes_with_us", "votes_with_china", "neutral_third_position_votes", "abstentions_on_broad_eligible"]
    country_year[count_cols] = country_year[count_cols].fillna(0).astype(int)

    country_year["broad_participation_rate"] = np.where(
        country_year["broad_eligible_resolutions"] > 0,
        country_year["broad_participated_votes"] / country_year["broad_eligible_resolutions"],
        np.nan,
    )
    country_year["unga_score_broad"] = np.where(
        country_year["broad_participated_votes"] > 0,
        country_year["broad_score_sum"] / country_year["broad_participated_votes"],
        np.nan,
    )
    country_year["unga_score_strict_yn"] = np.where(
        country_year["strict_participated_votes"] > 0,
        country_year["strict_score_sum"] / country_year["strict_participated_votes"],
        np.nan,
    )
    country_year["score_status"] = np.select(
        [
            country_year["broad_eligible_resolutions"] == 0,
            country_year["broad_participated_votes"] == 0,
            (country_year["broad_participated_votes"] < 10) | (country_year["broad_participation_rate"] < 0.5),
        ],
        ["no_eligible_anchor_disagreements", "no_country_participation", "provisionally_insufficient_participation"],
        default="available",
    )

    names = choose_country_names(votes)
    country_year = country_year.merge(names, on="country_key", how="left", validate="many_to_one")
    ordered = [
        "country_key", "country_name", "year", "unga_score_broad", "unga_score_strict_yn",
        "score_status", "broad_eligible_resolutions", "broad_participated_votes",
        "broad_participation_rate", "votes_with_us", "votes_with_china",
        "neutral_third_position_votes", "abstentions_on_broad_eligible",
        "strict_yn_eligible_resolutions", "strict_participated_votes", "total_resolutions",
        "absent_observations", "not_member_observations", "invalid_observations",
    ]
    country_year = country_year[ordered].sort_values(["year", "country_name"]).reset_index(drop=True)
    return enriched, country_year


def build_coverage(country_year: pd.DataFrame, anchor_audit: pd.DataFrame) -> pd.DataFrame:
    anchor_summary = anchor_audit.groupby("year").agg(
        resolutions=("resolution_id", "nunique"),
        broad_eligible_resolutions=("broad_eligible", "sum"),
        strict_yn_eligible_resolutions=("strict_yn_eligible", "sum"),
        missing_or_invalid_anchor_votes=("exclusion_reason", lambda s: (s == "missing_or_invalid_anchor_vote").sum()),
        anchor_agreement_resolutions=("exclusion_reason", lambda s: (s == "anchors_agreed").sum()),
    ).reset_index()
    score_summary = country_year.groupby("year").agg(
        country_years=("country_key", "size"),
        available_scores=("score_status", lambda s: (s == "available").sum()),
        provisionally_insufficient=("score_status", lambda s: (s == "provisionally_insufficient_participation").sum()),
        missing_scores=("unga_score_broad", lambda s: s.isna().sum()),
        median_participation_rate=("broad_participation_rate", "median"),
    ).reset_index()
    return anchor_summary.merge(score_summary, on="year", how="outer").sort_values("year")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--updated", type=Path, default=Path("Updated UNGA Voting Records .xlsx"))
    parser.add_argument("--legacy", type=Path, default=Path("US-China Closeness Index (1).xlsx"))
    parser.add_argument("--output-dir", type=Path, default=Path("."))
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    frames = []
    exception_frames = []
    for spec in build_source_specs(args.updated, args.legacy):
        frame, exceptions = parse_matrix_sheet(spec)
        frames.append(frame)
        if not exceptions.empty:
            exception_frames.append(exceptions)

    votes = pd.concat(frames, ignore_index=True)
    votes, duplicate_audit = deduplicate(votes)
    anchor_audit = classify_resolutions(votes)
    enriched, country_year = score_country_year(votes, anchor_audit)
    coverage = build_coverage(country_year, anchor_audit)
    exceptions = pd.concat(exception_frames, ignore_index=True) if exception_frames else pd.DataFrame()

    outputs = {
        "unga_votes_long.parquet": enriched,
        "unga_country_year_scores.csv": country_year,
        "unga_anchor_resolution_audit.csv": anchor_audit,
        "unga_coverage_by_year.csv": coverage,
        "unga_ingestion_exceptions.csv": exceptions,
        "unga_duplicate_audit.csv": duplicate_audit,
    }
    for name, frame in outputs.items():
        path = args.output_dir / name
        if path.suffix == ".parquet":
            frame.to_parquet(path, index=False)
        else:
            frame.to_csv(path, index=False)

    # Hard integrity checks.
    assert country_year["unga_score_broad"].dropna().between(-1, 1).all()
    assert country_year["unga_score_strict_yn"].dropna().between(-1, 1).all()
    assert not anchor_audit.duplicated(["year", "resolution_id"]).any()
    assert {"UNITED STATES", "CHINA"}.issubset(set(votes["country_key"]))

    print("Years:", int(country_year.year.min()), "to", int(country_year.year.max()))
    print("Resolution-years:", len(anchor_audit))
    print("Country-years:", len(country_year))
    print("Available baseline scores:", int((country_year.score_status == "available").sum()))
    print("Invalid vote observations:", int((enriched.vote_status == "invalid").sum()))
    print("Duplicate audit rows:", len(duplicate_audit))
    print("Outputs written to:", args.output_dir.resolve())


if __name__ == "__main__":
    main()
