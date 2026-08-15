
"""LIPAS."""
import json
import time
import os
from pathlib import Path
from collections import defaultdict

import pandas as pd

from data_ingestion import (
    parse_noaa_goes,
    parse_apollo_seismic_catalog,
    parse_solar_cycle_indices,
    build_training_dataset,
    dataset_completeness_report,
    augment_training_df,
    TRAINING_COLUMNS,
    save_dataset,
)

DEFAULT_APOLLO_CATALOG_PATH = 'data/archives/apollo_seismic/levent.1008weber.csv'

MIN_ROWS_FOR_SPLIT = 40

CATEGORY_PATTERNS = [
    ('solar-cycle', 'solar_cycle'),
    ('solar_cycle', 'solar_cycle'),
    ('xray', 'xray'),
    ('proton', 'radiation'),
    ('electron', 'radiation'),
    ('magnetometer', 'magnetometer'),
    ('k_index', 'kp_dst'),
    ('kp', 'kp_dst'),
    ('dst', 'kp_dst'),
    ('f107', 'f107'),
]

def categorize_filename(fname: str) -> "str | None":
    lower = fname.lower()
    for substring, category in CATEGORY_PATTERNS:
        if substring in lower:
            return category
    return None

def load_all_swpc_jsons(source_dir: str = 'data/raw') -> dict:
    """Load all SWPC JSON files and organize by data category."""
    source_dir = Path(source_dir)
    swpc_data = defaultdict(list)

    for json_file in sorted(source_dir.glob('*.json')):
        category = categorize_filename(json_file.stem)
        if category is None:
            continue
        try:
            with open(json_file) as f:
                data = json.load(f)
            swpc_data[category].append(data)
        except Exception as e:
            print(f"Warning: Failed to load {json_file.name}: {e}")

    return dict(swpc_data)

def _disambiguate_columns(df: pd.DataFrame, category: str) -> pd.DataFrame:
    """Rename category specific fields so unrelated quantities never share a"""
    if df.empty:
        return df
    df = df.copy()
    if category == 'xray' and 'flux' in df.columns:
        df = df.rename(columns={'flux': 'xray_flux'})
    elif category == 'f107' and 'flux' in df.columns:

        df = df.rename(columns={'flux': 'planetary_f'})

    return df

def merge_swpc_observations(swpc_data: dict) -> pd.DataFrame:
    """Parse and merge all SWPC categories into a single time indexed"""
    frames = []

    for category, data_list in swpc_data.items():
        for data in data_list:
            try:
                if category == 'solar_cycle':
                    df = parse_solar_cycle_indices(data)
                    if df.empty or 'date' not in df.columns:
                        continue
                    df['category'] = category
                    frames.append(df)
                    continue

                df = parse_noaa_goes(data)
                if df.empty or 'time_tag' not in df.columns:
                    continue
                df = _disambiguate_columns(df, category)
                df['category'] = category
                frames.append(df)
            except Exception as e:
                print(f"Warning: Failed to parse {category} data: {e}")

    if not frames:
        return pd.DataFrame()

    merged = pd.concat(frames, ignore_index=True, sort=False)
    merged = merged.drop_duplicates()
    return merged

def load_apollo_catalog_if_present(path: str = DEFAULT_APOLLO_CATALOG_PATH):
    p = Path(path)
    if not p.exists():
        return None
    try:
        catalog = parse_apollo_seismic_catalog(str(p))
        return catalog if not catalog.empty else None
    except Exception as e:
        print(f"Warning: failed to parse Apollo seismic catalog at {path}: {e}")
        return None

def ingest_all_swpc(
    source_dir: str = 'data/raw',
    out_dir: str = 'data/ingested_full',
    augment_if_sparse: bool = False,
    min_rows: int = MIN_ROWS_FOR_SPLIT,
    apollo_catalog_path: str = DEFAULT_APOLLO_CATALOG_PATH,
):
    print(f"Loading SWPC JSON files from {source_dir}...")
    swpc_data = load_all_swpc_jsons(source_dir)

    for category, data_list in swpc_data.items():
        print(f"  {category}: {len(data_list)} files")

    if not swpc_data:
        print("No categorized SWPC files found -- nothing to ingest.")
        return {'csv_path': None, 'report': {}, 'real_rows': 0, 'augmented': False}

    print("Merging observations across categories...")
    merged_obs = merge_swpc_observations(swpc_data)
    print(f"  Merged {len(merged_obs)} raw observation rows")

    apollo_catalog = load_apollo_catalog_if_present(apollo_catalog_path)
    if apollo_catalog is not None:
        print(f"  Loaded real Apollo PSE catalog: {len(apollo_catalog)} distinct event-dates from {apollo_catalog_path}")
    else:
        print(f"  No real Apollo PSE catalog found at {apollo_catalog_path} -- moonquakes_per_day will default to 0.0 for all rows")

    print("Building canonical per-date training rows via data_ingestion.build_training_dataset...")
    df = build_training_dataset(noaa=merged_obs, apollo=apollo_catalog)
    real_rows = len(df)
    print(f"  Generated {real_rows} real (non-augmented) training rows")

    augmented = False
    if real_rows == 0:
        print("No training rows generated! Check that data/raw contains recognized SWPC JSON files.")
        return {'csv_path': None, 'report': {}, 'real_rows': 0, 'augmented': False}

    if augment_if_sparse and real_rows < min_rows:
        print(
            f"Only {real_rows} real rows (< {min_rows}); applying physics-informed "
            f"augmentation to reach a workable sample size for train/val/test splitting. "
            f"This is clearly logged and should not be mistaken for additional real observations."
        )
        df = augment_training_df(df, target_rows=min_rows)
        augmented = True

    df = df[TRAINING_COLUMNS].copy()
    for col in TRAINING_COLUMNS:
        df[col] = pd.to_numeric(df[col], errors='coerce')
    before = len(df)
    df = df.dropna(axis=0, how='any')
    if len(df) < before:
        print(f"  Dropped {before - len(df)} rows containing non-numeric/NaN values")

    print(f"Final training set: {df.shape}")

    os.makedirs(out_dir, exist_ok=True)
    csv_path = os.path.join(out_dir, f'swpc_training_{int(time.time())}.csv')
    save_dataset(csv_path, df)
    print(f"Saved training data to {csv_path}")

    report = dataset_completeness_report(csv_path)
    print(f"Completeness report: rows={report.get('rows')}")

    return {'csv_path': csv_path, 'report': report, 'real_rows': real_rows, 'augmented': augmented}

if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Ingest raw SWPC JSON files into a canonical training CSV.')
    parser.add_argument('--source-dir', type=str, default='data/raw', help='Directory of raw SWPC JSON files')
    parser.add_argument('--out-dir', type=str, default='data/ingested_full', help='Directory to write the canonical CSV')
    parser.add_argument('--augment-if-sparse', action='store_true', help='Apply physics-informed augmentation if too few real rows were found')
    parser.add_argument('--min-rows', type=int, default=MIN_ROWS_FOR_SPLIT, help='Row-count threshold that triggers augmentation')
    args = parser.parse_args()

    ingest_all_swpc(
        source_dir=args.source_dir,
        out_dir=args.out_dir,
        augment_if_sparse=args.augment_if_sparse,
        min_rows=args.min_rows,
    )
