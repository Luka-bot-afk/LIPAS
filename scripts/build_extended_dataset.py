
"""LIPAS."""
import json
import sys
import time
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))

from data_ingestion import (
    build_extended_training_dataset,
    save_dataset,
    load_omni2_daily,
    EXTENDED_TRAINING_COLUMNS,
)
from ingest_swpc_data import load_all_swpc_jsons, merge_swpc_observations
from build_real_dataset import (
    load_donki_events,
    load_apollo_moonquakes,
    load_crater_dose_rates,
    load_ldex_local_time_profile,
    EARLIEST_USEFUL_DATE,
)

ROOT = Path(__file__).parent.parent
RAW_DIR = ROOT / 'data' / 'raw'
OUT_DIR = ROOT / 'data' / 'ingested_extended'
OMNI_PATH = ROOT / 'data' / 'archives' / 'omni2_daily.csv'

def main():
    print("Loading real NOAA SWPC data from data/raw/...")
    swpc_data = load_all_swpc_jsons(str(RAW_DIR))
    noaa_df = merge_swpc_observations(swpc_data)
    if 'date' in noaa_df.columns:
        before = len(noaa_df)
        noaa_df = noaa_df[noaa_df['date'].astype(str) >= EARLIEST_USEFUL_DATE]
        print(f"  NOAA merged real observations: {len(noaa_df)} rows (>= {EARLIEST_USEFUL_DATE}, dropped {before - len(noaa_df)})")

    print("\nLoading real NASA DONKI events...")
    donki = load_donki_events()

    print("\nLoading real Apollo PSE moonquake catalog...")
    apollo_df = load_apollo_moonquakes()

    print("\nLoading real CRaTER dose-rate table...")
    crater_df = load_crater_dose_rates()

    print("\nLoading real LADEE/LDEX local-time dust climatology...")
    ldex_profile = load_ldex_local_time_profile()

    print("\nLoading real NASA OMNI2 solar wind / IMF / Kp / F10.7 data...")
    omni_df = load_omni2_daily(str(OMNI_PATH))
    if omni_df.empty:
        print(f"  WARNING: {OMNI_PATH} not found or empty -- run scripts/fetch_omni2.py first. "
              f"Continuing with median/zero fallback for solar_wind_speed/density/imf_bz/kp_index.")
    else:
        print(f"  Loaded {len(omni_df)} real OMNI2 days ({omni_df['date'].min()} to {omni_df['date'].max()})")

    print("\nBuilding extended (18-input) canonical training dataset across all real lunar sites...")
    t0 = time.time()
    df = build_extended_training_dataset(
        donki=donki,
        noaa=noaa_df,
        apollo=apollo_df,
        crater=crater_df,
        omni=omni_df,
        ldex=ldex_profile,
    )
    print(f"Generated {len(df)} extended rows ({df['site'].nunique()} sites x "
          f"{df['date'].nunique()} distinct dates) in {time.time() - t0:.1f}s")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUT_DIR / f'extended_training_{int(time.time())}.csv'
    save_dataset(str(out_path), df)
    print(f"\nSaved extended real dataset to {out_path}")

    print("\n--- Column variability report (real vs constant) ---")
    for col in EXTENDED_TRAINING_COLUMNS:
        print(f"  {col:24s} nunique={df[col].nunique():6d}  min={df[col].min():.4g}  max={df[col].max():.4g}")

    return str(out_path)

if __name__ == '__main__':
    main()
