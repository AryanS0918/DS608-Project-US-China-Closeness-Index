"""Inventory formal-relations source files without exposing source records.

Complete runnable example.

Run from the repository root:
    python -u src/data/inventory_relations_sources.py

Optional arguments:
    python -u src/data/inventory_relations_sources.py \
        --sources data/sources/relations \
        --restricted data/raw/relations \
        --output outputs/tables/relations_source_inventory

Outputs:
    <output>.csv       one row per source file
    <output>.json      detailed machine-readable inventory
    <output>.md        concise human-readable report
    <output>_columns.csv one row per tabular field

The script records metadata, coverage, schemas, keys suggested by uniqueness,
missingness, and workbook/sheet structure. It does not write source rows or
values into the outputs.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import zipfile
from collections import Counter
from datetime import date, datetime
from pathlib import Path
from typing import Any, Iterable

import pandas as pd

try:
    from openpyxl import load_workbook
except ImportError:
    load_workbook = None


TABULAR_EXTENSIONS = {".csv", ".tsv", ".dta", ".xlsx", ".xls"}
DOCUMENT_EXTENSIONS = {".pdf", ".docx", ".txt", ".md"}
ARCHIVE_EXTENSIONS = {".zip"}
STRUCTURED_EXTENSIONS = {".xml", ".xsd"}
YEAR_NAME_PATTERN = re.compile(r"(?:^|[^0-9])((?:18|19|20)\d{2})(?:[^0-9]|$)")
COUNTRY_HINTS = (
    "country", "economy", "state", "sender", "target", "party", "parties",
    "ccode", "iso", "location", "nation", "dyad",
)
DATE_HINTS = (
    "date", "year", "month", "start", "end", "entry", "signature",
    "termination", "effective", "begin",
)
ID_HINTS = ("id", "code", "key", "case", "treaty", "agreement", "dyad")
MISSING_TOKENS = {"", "na", "n/a", "nan", "none", "null", ".", "..", "..."}


def serialise(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (datetime, date, pd.Timestamp)):
        return value.isoformat()
    if hasattr(value, "item"):
        try:
            return value.item()
        except Exception:
            pass
    if pd.isna(value):
        return None
    return value


def sha256(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def path_class(path: Path, sources_root: Path, restricted_root: Path) -> str:
    try:
        path.relative_to(sources_root)
        return "tracked_source"
    except ValueError:
        pass
    try:
        path.relative_to(restricted_root)
        return "restricted_raw"
    except ValueError:
        return "other"


def normalise_name(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(value).strip().lower()).strip("_")


def infer_candidate_keys(frame: pd.DataFrame, max_combinations: int = 25) -> list[str]:
    if frame.empty:
        return []
    names = [str(c) for c in frame.columns]
    preferred = [
        c for c in names
        if any(hint in normalise_name(c) for hint in ID_HINTS + COUNTRY_HINTS + DATE_HINTS)
    ]
    preferred = preferred[:12]
    candidates: list[str] = []

    for column in preferred:
        series = frame[column]
        if series.notna().all() and series.nunique(dropna=False) == len(frame):
            candidates.append(column)

    combinations_checked = 0
    for i, first in enumerate(preferred):
        for second in preferred[i + 1:]:
            if combinations_checked >= max_combinations:
                return candidates
            combinations_checked += 1
            columns = [first, second]
            subset = frame[columns]
            if subset.notna().all(axis=1).all() and not subset.duplicated().any():
                candidates.append(" + ".join(columns))
    return candidates


def infer_temporal_coverage(frame: pd.DataFrame) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for column in frame.columns:
        name = normalise_name(column)
        if not any(hint in name for hint in DATE_HINTS):
            continue
        series = frame[column]
        numeric = pd.to_numeric(series, errors="coerce")
        plausible_years = numeric[(numeric >= 1800) & (numeric <= 2200)]
        if plausible_years.notna().any():
            result[str(column)] = {
                "kind": "year",
                "min": int(plausible_years.min()),
                "max": int(plausible_years.max()),
                "non_missing": int(plausible_years.notna().sum()),
            }
            continue
        parsed = pd.to_datetime(series, errors="coerce")
        if parsed.notna().any():
            result[str(column)] = {
                "kind": "date",
                "min": parsed.min().date().isoformat(),
                "max": parsed.max().date().isoformat(),
                "non_missing": int(parsed.notna().sum()),
            }
    return result


def infer_geographic_fields(frame: pd.DataFrame) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for column in frame.columns:
        name = normalise_name(column)
        if any(hint in name for hint in COUNTRY_HINTS):
            series = frame[column].astype("string").str.strip()
            result[str(column)] = {
                "non_missing": int(series.notna().sum()),
                "unique": int(series.dropna().nunique()),
            }
    return result


def summarise_frame(frame: pd.DataFrame, file_ref: str, sheet: str | None = None) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    frame = frame.copy()
    frame.columns = [str(c).strip() for c in frame.columns]
    summary = {
        "file_ref": file_ref,
        "sheet": sheet,
        "rows": int(len(frame)),
        "columns": int(len(frame.columns)),
        "duplicate_rows": int(frame.duplicated().sum()) if len(frame.columns) else 0,
        "candidate_keys": infer_candidate_keys(frame),
        "temporal_coverage": infer_temporal_coverage(frame),
        "geographic_fields": infer_geographic_fields(frame),
    }
    columns: list[dict[str, Any]] = []
    for column in frame.columns:
        series = frame[column]
        as_text = series.astype("string").str.strip().str.lower()
        missing = series.isna() | as_text.isin(MISSING_TOKENS)
        columns.append({
            "file_ref": file_ref,
            "sheet": sheet,
            "column": str(column),
            "dtype": str(series.dtype),
            "rows": int(len(series)),
            "missing": int(missing.sum()),
            "missing_pct": round(float(missing.mean() * 100), 3) if len(series) else 0.0,
            "unique_non_missing": int(series[~missing].nunique(dropna=True)),
        })
    return summary, columns


def read_tabular(
    path: Path,
    file_ref: str,
) -> tuple[
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[str],
]:
    summaries: list[dict[str, Any]] = []
    columns: list[dict[str, Any]] = []
    warnings: list[str] = []
    suffix = path.suffix.lower()
    try:
        if suffix in {".xlsx", ".xls"}:
            engine = "openpyxl" if suffix == ".xlsx" else None
            excel = pd.ExcelFile(path, engine=engine)
            for sheet in excel.sheet_names:
                try:
                    frame = pd.read_excel(path, sheet_name=sheet, engine=engine)
                    summary, column_rows = summarise_frame(frame, file_ref, sheet)
                    summaries.append(summary)
                    columns.extend(column_rows)
                except Exception as exc:
                    warnings.append(f"Could not read sheet {sheet!r}: {exc}")
        elif suffix == ".csv":
            try:
                frame = pd.read_csv(path, low_memory=False)
            except UnicodeDecodeError:
                frame = pd.read_csv(path, low_memory=False, encoding="latin-1")
            summary, column_rows = summarise_frame(frame, file_ref)
            summaries.append(summary)
            columns.extend(column_rows)
        elif suffix == ".tsv":
            frame = pd.read_csv(path, sep="\t", low_memory=False)
            summary, column_rows = summarise_frame(frame, file_ref)
            summaries.append(summary)
            columns.extend(column_rows)
        elif suffix == ".dta":
            frame = pd.read_stata(path, convert_categoricals=False)
            summary, column_rows = summarise_frame(frame, file_ref)
            summaries.append(summary)
            columns.extend(column_rows)
    except Exception as exc:
        warnings.append(f"Could not read tabular file: {exc}")
    return summaries, columns, warnings


def inspect_workbook_structure(path: Path) -> dict[str, Any]:
    if load_workbook is None or path.suffix.lower() != ".xlsx":
        return {}
    try:
        workbook = load_workbook(path, read_only=True, data_only=False)
        return {
            "sheet_names": workbook.sheetnames,
            "sheet_dimensions": {
                sheet.title: {"max_row": sheet.max_row, "max_column": sheet.max_column}
                for sheet in workbook.worksheets
            },
        }
    except Exception as exc:
        return {"warning": f"Could not inspect workbook structure: {exc}"}


def inspect_zip(path: Path) -> dict[str, Any]:
    try:
        with zipfile.ZipFile(path) as archive:
            members = [m for m in archive.infolist() if not m.is_dir()]
            by_extension = Counter(Path(m.filename).suffix.lower() or "<none>" for m in members)
            return {
                "members": len(members),
                "uncompressed_bytes": int(sum(m.file_size for m in members)),
                "extensions": dict(sorted(by_extension.items())),
                "member_names": [m.filename for m in members],
            }
    except Exception as exc:
        return {"warning": f"Could not inspect ZIP: {exc}"}


def inspect_text(path: Path) -> dict[str, Any]:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
        return {"lines": text.count("\n") + 1, "characters": len(text)}
    except Exception as exc:
        return {"warning": f"Could not inspect text: {exc}"}


def infer_years_from_filename(path: Path) -> list[int]:
    return sorted({int(match) for match in YEAR_NAME_PATTERN.findall(path.name)})


def inspect_file(path: Path, root: Path, sources_root: Path, restricted_root: Path) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    relative = str(path.relative_to(root)) if path.is_relative_to(root) else str(path)
    suffix = path.suffix.lower()
    stat = path.stat()
    entry: dict[str, Any] = {
        "path": relative,
        "filename": path.name,
        "extension": suffix,
        "storage_class": path_class(path, sources_root, restricted_root),
        "size_bytes": int(stat.st_size),
        "modified_at": datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds"),
        "sha256": sha256(path),
        "years_in_filename": infer_years_from_filename(path),
        "warnings": [],
    }
    tabular_summaries: list[dict[str, Any]] = []
    column_rows: list[dict[str, Any]] = []

    if suffix in TABULAR_EXTENSIONS:
        summaries, columns, warnings = read_tabular(
            path,
            relative,
        )
        tabular_summaries.extend(summaries)
        column_rows.extend(columns)
        entry["tabular_objects"] = summaries
        entry["warnings"].extend(warnings)
        if suffix == ".xlsx":
            entry["workbook_structure"] = inspect_workbook_structure(path)
    elif suffix in ARCHIVE_EXTENSIONS:
        entry["archive"] = inspect_zip(path)
    elif suffix in {".txt", ".md", ".xml", ".xsd"}:
        entry["text_metadata"] = inspect_text(path)
    elif suffix in DOCUMENT_EXTENSIONS:
        entry["document_type"] = suffix.lstrip(".")
    else:
        entry["note"] = "Metadata only; no dedicated parser configured."

    return entry, tabular_summaries, column_rows


def discover_files(roots: Iterable[Path]) -> list[Path]:
    files: list[Path] = []
    for root in roots:
        if not root.exists():
            continue
        files.extend(
            path for path in root.rglob("*")
            if path.is_file() and path.name not in {".DS_Store"} and not path.name.startswith("~$")
        )
    return sorted(set(path.resolve() for path in files))


def make_markdown(entries: list[dict[str, Any]], tabular: list[dict[str, Any]], sources_root: Path, restricted_root: Path) -> str:
    tracked = sum(e["storage_class"] == "tracked_source" for e in entries)
    restricted = sum(e["storage_class"] == "restricted_raw" for e in entries)
    warning_count = sum(bool(e.get("warnings")) for e in entries)
    lines = [
        "# Formal-relations source inventory",
        "",
        f"Generated: {datetime.now().isoformat(timespec='seconds')}",
        "",
        "## Scope",
        "",
        "- Tracked source root: `data/sources/relations`",
        "- Restricted raw root: `data/raw/relations`",
        f"- Files inventoried: **{len(entries):,}**",
        f"- Tracked source files: **{tracked:,}**",
        f"- Restricted raw files: **{restricted:,}**",
        f"- Files with read warnings: **{warning_count:,}**",
        "",
        "## Files",
        "",
        "| Storage | File | Type | Size (bytes) | Tabular objects | Warnings |",
        "|---|---|---:|---:|---:|---:|",
    ]
    tabular_counts = Counter(item["file_ref"] for item in tabular)
    for entry in entries:
        lines.append(
            f"| {entry['storage_class']} | `{entry['path']}` | {entry['extension'] or 'none'} "
            f"| {entry['size_bytes']:,} | {tabular_counts.get(entry['path'], 0)} | {len(entry.get('warnings', []))} |"
        )
    lines.extend(["", "## Tabular objects", ""])
    for item in tabular:
        label = f"{item['file_ref']}"
        if item.get("sheet") is not None:
            label += f" :: {item['sheet']}"
        lines.extend([
            f"### `{label}`",
            "",
            f"- Rows: **{item['rows']:,}**",
            f"- Columns: **{item['columns']:,}**",
            f"- Duplicate rows: **{item['duplicate_rows']:,}**",
            f"- Candidate keys: {', '.join(item['candidate_keys']) if item['candidate_keys'] else 'None identified automatically'}",
            f"- Temporal fields: `{json.dumps(item['temporal_coverage'], ensure_ascii=False)}`",
            f"- Geographic fields: `{json.dumps(item['geographic_fields'], ensure_ascii=False)}`",
            "",
        ])
    lines.extend([
        "## Interpretation note",
        "",
        "Candidate keys and inferred temporal/geographic fields are diagnostics only. They must be reviewed against each dataset's codebook before production use.",
        "",
    ])
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sources", type=Path, default=Path("data/sources/relations"))
    parser.add_argument("--restricted", type=Path, default=Path("data/raw/relations"))
    parser.add_argument("--output", type=Path, default=Path("outputs/tables/relations_source_inventory"))
    args = parser.parse_args()

    repository_root = Path.cwd().resolve()
    sources_root = (repository_root / args.sources).resolve() if not args.sources.is_absolute() else args.sources.resolve()
    restricted_root = (repository_root / args.restricted).resolve() if not args.restricted.is_absolute() else args.restricted.resolve()
    output_base = (repository_root / args.output).resolve() if not args.output.is_absolute() else args.output.resolve()
    output_base.parent.mkdir(parents=True, exist_ok=True)

    files = discover_files([sources_root, restricted_root])
    if not files:
        raise FileNotFoundError("No files found under the requested source roots.")

    entries: list[dict[str, Any]] = []
    tabular: list[dict[str, Any]] = []
    columns: list[dict[str, Any]] = []

    print(f"Inventorying {len(files)} files...")
    for index, path in enumerate(files, start=1):
        print(f"[{index:>3}/{len(files)}] {path}")
        entry, tabular_items, column_items = inspect_file(
            path, repository_root, sources_root, restricted_root
        )
        entries.append(entry)
        tabular.extend(tabular_items)
        columns.extend(column_items)

    detailed = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "repository_root": ".",
        "sources_root": "data/sources/relations",
        "restricted_root": "data/raw/relations",
        "files": entries,
        "tabular_objects": tabular,
    }

    json_path = output_base.with_suffix(".json")
    csv_path = output_base.with_suffix(".csv")
    md_path = output_base.with_suffix(".md")
    columns_path = output_base.parent / f"{output_base.name}_columns.csv"

    json_path.write_text(json.dumps(detailed, indent=2, ensure_ascii=False, default=serialise), encoding="utf-8")

    file_rows = []
    for entry in entries:
        file_rows.append({
            "path": entry["path"],
            "filename": entry["filename"],
            "extension": entry["extension"],
            "storage_class": entry["storage_class"],
            "size_bytes": entry["size_bytes"],
            "modified_at": entry["modified_at"],
            "sha256": entry["sha256"],
            "tabular_objects": len(entry.get("tabular_objects", [])),
            "warning_count": len(entry.get("warnings", [])),
            "warnings": " | ".join(entry.get("warnings", [])),
        })
    pd.DataFrame(file_rows).to_csv(csv_path, index=False)
    pd.DataFrame(columns).to_csv(columns_path, index=False)
    md_path.write_text(make_markdown(entries, tabular, sources_root, restricted_root), encoding="utf-8")

    print("\nInventory complete.")
    print(f"Files inventoried: {len(entries):,}")
    print(f"Tabular objects: {len(tabular):,}")
    print(f"Columns inventoried: {len(columns):,}")
    print(f"Detailed JSON: {json_path.relative_to(repository_root)}")
    print(f"File summary CSV: {csv_path.relative_to(repository_root)}")
    print(f"Column summary CSV: {columns_path.relative_to(repository_root)}")
    print(f"Markdown report: {md_path.relative_to(repository_root)}")


if __name__ == "__main__":
    main()
