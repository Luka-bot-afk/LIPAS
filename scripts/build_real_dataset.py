
"""LIPAS."""
import glob
import json
import os
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from data_ingestion import (
    build_training_dataset,
    save_dataset,
    TRAINING_COLUMNS,
)
from ingest_swpc_data import load_all_swpc_jsons, merge_swpc_observations

ROOT = Path(__file__).parent.parent
DONKI_HISTORY_DIR = ROOT / 'data' / 'archives' / 'donki_history'
APOLLO_CATALOG_PATH = ROOT / 'data' / 'archives' / 'apollo_seismic' / 'levent.1008weber.csv'
CRATER_DOSE_PATH = ROOT / 'data' / 'archives' / 'crater_dose' / 'crater_l30_daily_dose_rate.html'
LDEX_DENSITY_PATH = ROOT / 'data' / 'archives' / 'ldex' / 'ldex_ltden_pds_derived.tab'
RAW_DIR = ROOT / 'data' / 'raw'
OUT_DIR = ROOT / 'data' / 'ingested_full'

CRATER_DOSE_QUALITY_FACTOR = 2.5

def load_donki_events() -> dict:
    """Load DONKI history from disk."""
    donki = {'flr': [], 'gst': [], 'sep': [], 'cme': []}
    for etype in donki:
        for path in sorted(DONKI_HISTORY_DIR.glob(f'{etype}_*.json')):
            with path.open() as f:
                donki[etype].extend(json.load(f))
    print("DONKI real events loaded (full 2010-2026 history archive): "
          + ", ".join(f"{k}={len(v)}" for k, v in donki.items()))
    return donki

def load_apollo_moonquakes() -> pd.DataFrame:
    """Parse Weber Apollo PSE catalog with amplitude-weighted daily intensity."""
    from data_ingestion import parse_apollo_seismic_catalog

    path = APOLLO_CATALOG_PATH
    if not path.exists():
        return pd.DataFrame(columns=['date', 'quake_count'])

    counts = parse_apollo_seismic_catalog(str(path))
    if counts.empty:
        return pd.DataFrame(columns=['date', 'quake_count'])
    print(
        f"Apollo PSE amplitude-weighted moonquake days: {len(counts)} "
        f"({counts['date'].min()} to {counts['date'].max()}), "
        f"mean intensity={float(counts['quake_count'].mean()):.2f}"
    )
    return counts[['date', 'quake_count']]

def load_ldex_local_time_profile() -> np.ndarray:
    """Normalize LDEX altitude×local-time density table to a 24h factor (~1 mean)."""
    path = LDEX_DENSITY_PATH
    if not path.exists():
        return np.ones(24, dtype=np.float64)
    rows = []
    with path.open() as f:
        for line in f:
            parts = line.split()
            if len(parts) < 3:
                continue
            nums = []
            for x in parts[1:]:
                try:
                    v = float(x)
                except Exception:
                    continue
                if v != -9.99e0 and np.isfinite(v) and v > 0:
                    nums.append(v)

            dens = nums[0::2] if len(nums) >= 2 else nums
            if dens:
                rows.append(dens)
    if not rows:
        return np.ones(24, dtype=np.float64)
    n_bins = max(len(r) for r in rows)
    col_means = []
    for i in range(n_bins):
        vals = [r[i] for r in rows if i < len(r)]
        col_means.append(float(np.mean(vals)) if vals else np.nan)
    col_means = np.asarray(col_means, dtype=np.float64)
    if not np.isfinite(col_means).any():
        return np.ones(24, dtype=np.float64)
    fill = float(np.nanmean(col_means))
    col_means = np.where(np.isfinite(col_means), col_means, fill)

    hour_centers = (np.arange(len(col_means), dtype=np.float64) + 0.5) * (24.0 / len(col_means))
    hour_grid = np.arange(24, dtype=np.float64)

    xc = np.concatenate([hour_centers - 24.0, hour_centers, hour_centers + 24.0])
    yc = np.concatenate([col_means, col_means, col_means])
    interp = np.interp(hour_grid, xc, yc)
    mean = float(np.mean(interp)) or 1.0
    profile = interp / mean
    print(f"LDEX local-time profile: {len(col_means)} bins → 24h factors "
          f"(min={profile.min():.3f}, max={profile.max():.3f})")
    return profile.astype(np.float64)

def load_crater_dose_rates() -> pd.DataFrame:
    """Parse the real CRaTER Legacy Data Products daily dose rate table"""
    path = CRATER_DOSE_PATH
    if not path.exists():
        return pd.DataFrame(columns=['date', 'radiation_mSv'])

    tables = pd.read_html(path)
    t = tables[0].dropna(subset=['Date']).copy()
    t = t[t['Date'].astype(str).str.match(r'^\d{4}-\d{2}-\d{2}$')]

    dose_cols = [c for c in t.columns if 'Corrected Dose Rate' in str(c)]
    for c in dose_cols:
        t[c] = pd.to_numeric(t[c], errors='coerce')

    t['mean_dose_mGy'] = t[dose_cols].mean(axis=1, skipna=True)
    t = t.dropna(subset=['mean_dose_mGy'])
    t['radiation_mSv'] = t['mean_dose_mGy'] * CRATER_DOSE_QUALITY_FACTOR
    t = t.rename(columns={'Date': 'date'})
    print(f"CRaTER real daily dose-rate rows: {len(t)} days "
          f"({t['date'].min()} to {t['date'].max()}), "
          f"mean radiation_mSv={t['radiation_mSv'].mean():.4f}")
    return t[['date', 'radiation_mSv']]

def report_ldex_real_density() -> float:
    """Compute the real mission mean LDEX dust density from the derived"""
    path = LDEX_DENSITY_PATH
    if not path.exists():
        return None
    vals = []
    with path.open() as f:
        for line in f:
            parts = line.split()
            nums = [float(x) for x in parts[1:] if x != '-9.99E+00']
            vals.extend(nums)
    if not vals:
        return None
    mean_density_m3 = float(np.mean(vals))
    print(f"LDEX real derived mean dust density: {mean_density_m3:.4e} m^-3 "
          f"(from {len(vals)} real measured local-time/altitude bins)")
    return mean_density_m3

EARLIEST_USEFUL_DATE = '1969-01-01'

def main():
    print("Loading real NOAA SWPC data from data/raw/...")
    swpc_data = load_all_swpc_jsons(str(RAW_DIR))
    noaa_df = merge_swpc_observations(swpc_data)
    if 'date' in noaa_df.columns:
        before = len(noaa_df)
        noaa_df = noaa_df[noaa_df['date'].astype(str) >= EARLIEST_USEFUL_DATE]
        print(f"  NOAA merged real observations: {len(noaa_df)} rows "
              f"(dropped {before - len(noaa_df)} pre-{EARLIEST_USEFUL_DATE} solar-cycle-only rows "
              f"that carried no other real source -- see EARLIEST_USEFUL_DATE comment)")
    else:
        print(f"  NOAA merged real observations: {len(noaa_df)} rows")

    print("\nLoading real NASA DONKI events...")
    donki = load_donki_events()

    print("\nLoading real Apollo PSE moonquake catalog...")
    apollo_df = load_apollo_moonquakes()

    print("\nLoading real CRaTER dose-rate table...")
    crater_df = load_crater_dose_rates()

    print("\nComputing real LDEX dust density (climatology, reported separately)...")
    ldex_mean = report_ldex_real_density()
    _ = load_ldex_local_time_profile()

    print("\nBuilding canonical training dataset from all real sources...")
    df = build_training_dataset(
        donki=donki,
        noaa=noaa_df,
        apollo=apollo_df,
        crater=crater_df,
    )
    print(f"Generated {len(df)} canonical rows from real sources "
          f"(date range {df.shape[0] and 'n/a'})")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUT_DIR / f'real_combined_training_{int(time.time())}.csv'
    save_dataset(str(out_path), df)
    print(f"\nSaved combined real dataset to {out_path}")

    print("\n--- Column variability report (real vs constant) ---")
    for col in TRAINING_COLUMNS:
        print(f"  {col:28s} nunique={df[col].nunique():4d}  min={df[col].min():.4g}  max={df[col].max():.4g}")

    if ldex_mean is not None:
        print(f"\nLDEX real mean density for physics-fallback update: {ldex_mean:.4e} m^-3")

    return str(out_path)

if __name__ == '__main__':
    main()
