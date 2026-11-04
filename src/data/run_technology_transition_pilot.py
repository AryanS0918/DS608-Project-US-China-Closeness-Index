"""Run the four-case HS1992-to-HS1996 technology-trade transition pilot."""
from __future__ import annotations

import shutil
from pathlib import Path

import pandas as pd

from src.data import collect_technology_trade as collector

SELECTIONS = (
    ("LSO", 2004),
    ("LSO", 2005),
    ("SUR", 2008),
    ("SUR", 2009),
)


def repository_root() -> Path:
    for path in (Path.cwd(), *Path.cwd().parents):
        if (path / "requirements.txt").exists() and (path / "src").exists():
            return path
    raise FileNotFoundError("Run from inside the repository")


def backup(path: Path) -> Path | None:
    if not path.exists():
        return None
    target = path.with_suffix(path.suffix + ".transition_pilot_backup")
    shutil.copy2(path, target)
    return target


def restore(path: Path, saved: Path | None) -> None:
    if saved is None:
        path.unlink(missing_ok=True)
    else:
        shutil.move(saved, path)


def main() -> None:
    root = repository_root()
    output_dir = root / "outputs" / "tables" / "technology"
    output_dir.mkdir(parents=True, exist_ok=True)
    canonical_manifest = output_dir / "technology_collection_manifest.csv"
    canonical_coverage = output_dir / "technology_reporter_year_coverage.csv"
    manifest_backup = backup(canonical_manifest)
    coverage_backup = backup(canonical_coverage)
    manifests: list[pd.DataFrame] = []
    coverages: list[pd.DataFrame] = []

    try:
        for reporter_iso, year in SELECTIONS:
            collector.PILOT = (reporter_iso,)
            print(f"\nRunning transition pilot: {reporter_iso} {year}")
            result = collector.collect(
                root=root,
                start_year=year,
                end_year=year,
                pilot=True,
                basket="include_broad_ict",
                refresh=False,
                delay=1.1,
                batch_size=100,
                max_retries=3,
            )
            result.insert(0, "pilot_case", f"{reporter_iso}_{year}")
            manifests.append(result)
            if canonical_coverage.exists():
                coverage = pd.read_csv(canonical_coverage)
                coverage.insert(0, "pilot_case", f"{reporter_iso}_{year}")
                coverages.append(coverage)
    finally:
        restore(canonical_manifest, manifest_backup)
        restore(canonical_coverage, coverage_backup)

    manifest = pd.concat(manifests, ignore_index=True)
    coverage = pd.concat(coverages, ignore_index=True)
    manifest_path = output_dir / "technology_transition_pilot_manifest.csv"
    coverage_path = output_dir / "technology_transition_pilot_coverage.csv"
    manifest.to_csv(manifest_path, index=False)
    coverage.to_csv(coverage_path, index=False)

    print("\nPilot manifest status counts")
    print(manifest["status"].value_counts(dropna=False).to_string())
    print(f"\nWrote {manifest_path.relative_to(root)}")
    print(f"Wrote {coverage_path.relative_to(root)}")


if __name__ == "__main__":
    main()
