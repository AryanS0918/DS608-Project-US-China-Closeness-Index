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


def main():
    print("Loading SIPRI raw data...")
    us_df = load_sipri(US_FILE, "US_TIV")
    cn_df = load_sipri(CN_FILE, "CN_TIV")
    global_df = load_sipri(GLOBAL_FILE, "Global_TIV")

    df = pd.merge(us_df, cn_df, on=["Recipient", "Year"], how="outer")
    df = pd.merge(df, global_df, on=["Recipient", "Year"], how="outer")
    df = df.fillna(0)

    # 1. Remove non-state recipients
    non_states = [
        "African Union**",
        "NATO**",
        "Syria rebels**",
        "United Nations**",
        "Unknown recipient(s)**",
    ]
    removed_df = df[df["Recipient"].isin(non_states)]
    if not removed_df.empty:
        REMOVED_AUDIT_FILE.parent.mkdir(parents=True, exist_ok=True)
        removed_df["Recipient"].drop_duplicates().to_csv(
            REMOVED_AUDIT_FILE, index=False
        )

    df = df[~df["Recipient"].isin(non_states)]

    # 2. Map recipient names to ISO3
    if MAPPING_FILE.exists():
        mapping = pd.read_csv(MAPPING_FILE)
        map_dict = dict(zip(mapping.iloc[:, 0], mapping.iloc[:, 1]))
        df["ISO3"] = df["Recipient"].map(map_dict)

        unmapped = df[df["ISO3"].isna()]["Recipient"].unique()
        if len(unmapped) > 0:
            pd.DataFrame({"Unmapped_Recipient": unmapped}).to_csv(
                UNMAPPED_AUDIT_FILE, index=False
            )
            raise ValueError(
                f"{len(unmapped)} names could not be mapped to ISO3. "
                f"Check {UNMAPPED_AUDIT_FILE}."
            )
    else:
        print(f"WARNING: {MAPPING_FILE} not found! Bypassing ISO3 mapping.")
        df["ISO3"] = df["Recipient"]

    # 3. Build full recipient x year grid
    all_recipients = df["ISO3"].unique()
    all_years = range(1996, 2026)
    idx = pd.MultiIndex.from_product(
        [all_recipients, all_years], names=["ISO3", "Year"]
    )
    grid = pd.DataFrame(index=idx).reset_index()

    df = pd.merge(grid, df, on=["ISO3", "Year"], how="left").fillna(
        {"US_TIV": 0, "CN_TIV": 0, "Global_TIV": 0}
    )

    # 4. Compute 5-year rolling sums (requiring all 5 years)
    df = df.sort_values(by=["ISO3", "Year"])
    df["US_5yr"] = df.groupby("ISO3")["US_TIV"].transform(
        lambda x: x.rolling(window=5, min_periods=5).sum()
    )
    df["CN_5yr"] = df.groupby("ISO3")["CN_TIV"].transform(
        lambda x: x.rolling(window=5, min_periods=5).sum()
    )
    df["Global_5yr"] = df.groupby("ISO3")["Global_TIV"].transform(
        lambda x: x.rolling(window=5, min_periods=5).sum()
    )

    df = df.dropna(subset=["US_5yr", "CN_5yr", "Global_5yr"]).copy()

    # 5. Compute outputs & formating
    df["Volume"] = df["US_5yr"] + df["CN_5yr"]
    df["Signed_Score"] = np.where(
        df["Volume"] == 0,
        np.nan,
        (df["US_5yr"] - df["CN_5yr"]) / df["Volume"],
    )
    df["Exposure"] = np.where(
        df["Global_5yr"] == 0, np.nan, df["Volume"] / df["Global_5yr"]
    )
    df["Low_Volume_Flag"] = df["Volume"] < VOLUME_THRESHOLD

    df["Status"] = "available"
    df.loc[df["Global_5yr"] == 0, "Status"] = "no_observed_relationship"

    final_cols = [
        "ISO3",
        "Year",
        "Signed_Score",
        "Volume",
        "Exposure",
        "Low_Volume_Flag",
        "Status",
    ]
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    df[final_cols].to_csv(OUTPUT_FILE, index=False)

    print(f"Success! Processed SIPRI panel saved to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
