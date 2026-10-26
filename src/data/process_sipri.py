"""Processing pipeline for SIPRI Arms Transfers Database.

Reads raw US, China, and global TIV extractions, cleans recipient names,
removes non-state entities, maps to ISO3, aggregates duplicate mappings,
computes 5-year rolling sums, and outputs the bounded signed score panel.
"""

from pathlib import Path
import numpy as np
import pandas as pd

# File paths
US_FILE = Path("data/raw/sipri/us_transfers.csv")
CN_FILE = Path("data/raw/sipri/cn_transfers.csv")
GLOBAL_FILE = Path("data/raw/sipri/global_transfers.csv")
MAPPING_FILE = Path("data/sources/country_mapping.csv")
OUTPUT_FILE = Path("data/processed/sipri_arms_country_year.csv")
UNMAPPED_AUDIT_FILE = Path("data/processed/sipri_unmapped_names.csv")
REMOVED_AUDIT_FILE = Path("data/processed/sipri_removed_audit.csv")

VOLUME_THRESHOLD = 100


def find_header_row(filepath: Path) -> int:
    """Dynamically locates the row index starting with 'Recipient'."""
    with open(filepath, 'r', encoding='utf-8') as f:
        for i, line in enumerate(f):
            if line.startswith("Recipient"):
                return i
    return 0


def load_sipri(filepath: Path, value_name: str) -> pd.DataFrame:
    """Load, reshape, and parse a raw SIPRI CSV export."""
    header_idx = find_header_row(filepath)
    df = pd.read_csv(filepath, skiprows=header_idx)

    cols_to_drop = [
        "1996-2025",
        "Percentage",
        "Sum total years",
        "Percentage of total",
    ]
    df = df.drop(columns=[c for c in cols_to_drop if c in df.columns])

    df = df.melt(id_vars=["Recipient"], var_name="Year", value_name=value_name)

    df["Year"] = pd.to_numeric(df["Year"], errors="coerce")
    df = df.dropna(subset=["Year"])
    df["Year"] = df["Year"].astype(int)

    # '0' in SIPRI indicates <0.5 million TIV. Explicit blanks are 0.
    raw_vals = pd.to_numeric(df[value_name], errors="coerce")
    df[value_name] = np.where(raw_vals == 0, 0.25, raw_vals.fillna(0))

    return df


def remove_non_states(df: pd.DataFrame) -> pd.DataFrame:
    """
