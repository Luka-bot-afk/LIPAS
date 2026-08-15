"""LIPAS."""
import csv
import json
import os
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Tuple, Optional, Any

import numpy as np
import pandas as pd
import requests

from lunar_physics import physics_temperature, physics_micrometeorite_flux, physics_dust, physics_moonquake_rate

_LUNAR_PHASE_REFERENCE_NEW_MOON = datetime(2000, 1, 6).date()
_LUNAR_SYNODIC_MONTH_DAYS = 29.530588

INPUT_COLUMNS = [
    'solar_activity',
    'radiation_mSv',
    'temperature_C',
    'moonquakes_per_day',
    'meteor_flux_1e15',
    'dust_g_cm3'
]
TARGET_COLUMNS = [
    'target_solar_activity',
    'target_radiation_mSv',
    'target_temperature_C',
    'target_moonquakes_per_day',
    'target_meteor_flux_1e15',
    'target_dust_g_cm3'
]
TRAINING_COLUMNS = INPUT_COLUMNS + TARGET_COLUMNS

EXTENDED_INPUT_COLUMNS = INPUT_COLUMNS + [
    'lat', 'lon', 'local_solar_time',
    'hour_of_day', 'day_of_month', 'month_of_year',
    'solar_wind_speed', 'solar_wind_density', 'imf_bz', 'kp_index',
    'regolith_depth', 'thermal_inertia'
]
EXTENDED_TRAINING_COLUMNS = EXTENDED_INPUT_COLUMNS + TARGET_COLUMNS

SAMPLE_ROW = {
    'solar_activity': 5.0,
    'radiation_mSv': 0.057,
    'temperature_C': -160.0,
    'moonquakes_per_day': 14.0,
    'meteor_flux_1e15': 1.6,
    'dust_g_cm3': 1.5,
    'target_solar_activity': 5.0,
    'target_radiation_mSv': 0.057,
    'target_temperature_C': -160.0,
    'target_moonquakes_per_day': 14.0,
    'target_meteor_flux_1e15': 1.6,
    'target_dust_g_cm3': 1.5
}

SOURCE_DESCRIPTIONS = {
    'donki': 'NASA DONKI SEP/FLR/CME/GST event summaries',
    'noaa': 'NOAA SWPC GOES radiation and Kp/magnetometer products',
    'diviner': 'LRO DIVINER lunar surface temperature products',
    'crater': 'LRO CRaTER radiation baseline products',
    'ldex': 'LADEE/LDEX dust density summaries',
    'apollo': 'Apollo PSE moonquake catalogs',
    'mem3': 'MEM-3 micrometeoroid flux model outputs'
}

def get_training_columns() -> List[str]:
    return TRAINING_COLUMNS.copy()

def get_input_columns() -> List[str]:
    return INPUT_COLUMNS.copy()

def get_target_columns() -> List[str]:
    return TARGET_COLUMNS.copy()

def get_extended_input_columns() -> List[str]:
    return EXTENDED_INPUT_COLUMNS.copy()

def get_extended_training_columns() -> List[str]:
    return EXTENDED_TRAINING_COLUMNS.copy()

def get_schema_example() -> Dict[str, Any]:
    return SAMPLE_ROW.copy()

def write_schema_csv(path: str) -> None:
    path = Path(path)
    df = pd.DataFrame([SAMPLE_ROW], columns=TRAINING_COLUMNS)
    df.to_csv(path, index=False)

def load_training_csv(path: str, allow_inputs_as_targets: bool = False) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Load a training CSV and return valid feature and target dataframes."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Training CSV not found: {path}")

    df = pd.read_csv(path)
    missing = [c for c in INPUT_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"Missing required input columns: {missing}")

    if allow_inputs_as_targets and all(c in df.columns for c in TARGET_COLUMNS):
        pass
    elif allow_inputs_as_targets and not all(c in df.columns for c in TARGET_COLUMNS):
        for input_col, target_col in zip(INPUT_COLUMNS, TARGET_COLUMNS):
            if target_col not in df.columns:
                df[target_col] = df[input_col]
    else:
        missing_targets = [c for c in TARGET_COLUMNS if c not in df.columns]
        if missing_targets:
            raise ValueError(f"Missing required target columns: {missing_targets}")

    df = df[TRAINING_COLUMNS].copy()
    df = df.dropna(axis=0, how='any')
    for col in TRAINING_COLUMNS:
        df[col] = pd.to_numeric(df[col], errors='coerce')
    df = df.dropna(axis=0, how='any')

    if df.empty:
        raise ValueError('Training CSV contains no valid rows after cleaning.')

    X = df[INPUT_COLUMNS].astype(float)
    Y = df[TARGET_COLUMNS].astype(float)
    return X, Y

def load_json_or_csv(path: str) -> Any:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f'File not found: {path}')
    if path.suffix.lower().endswith('.json'):
        with path.open('r', encoding='utf-8') as fh:
            return json.load(fh)
    return pd.read_csv(path)

def is_url(value: Any) -> bool:
    return isinstance(value, str) and value.startswith(('http://', 'https://'))

def load_source_payload(raw: Any) -> Any:
    if isinstance(raw, str):
        if is_url(raw):
            data = fetch_api_json(raw)
            if data is not None:
                return data
        path = Path(raw)
        if path.exists():
            return load_json_or_csv(str(path))
        try:
            return json.loads(raw)
        except Exception:
            return raw
    return raw

def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default

NASA_DONKI_URLS = {
    'SEP': 'https://api.nasa.gov/DONKI/SEP',
    'FLR': 'https://api.nasa.gov/DONKI/FLR',
    'CME': 'https://api.nasa.gov/DONKI/CME',
    'GST': 'https://api.nasa.gov/DONKI/GST'
}

NOAA_SWPC_URLS = {
    'flux': 'https://services.swpc.noaa.gov/json/goes/primary/integral-protons-1-day.json',
    'xray_primary': 'https://services.swpc.noaa.gov/json/goes/primary/xrays-1-day.json',
    'xray_secondary': 'https://services.swpc.noaa.gov/json/goes/secondary/xrays-1-day.json',
    'kp': 'https://services.swpc.noaa.gov/products/noaa-planetary-k-index.json',
    'planetary_a': 'https://services.swpc.noaa.gov/products/noaa-planetary-a-index.json',
    'planetary_f': 'https://services.swpc.noaa.gov/products/noaa-planetary-f-index.json',
    'magnetometer': 'https://services.swpc.noaa.gov/json/goes/primary/magnetometers-1-day.json'
}

def fetch_api_json(url: str, params: dict = None, timeout: int = 15):
    try:
        r = requests.get(url, params=params, timeout=timeout)
        r.raise_for_status()
        return r.json()
    except Exception:
        return None

def fetch_nasa_donki(start_date: str, end_date: str, api_key: str = 'DEMO_KEY') -> dict:
    data = {}
    for key, url in NASA_DONKI_URLS.items():
        data[key.lower()] = fetch_api_json(url, params={'startDate': start_date, 'endDate': end_date, 'api_key': api_key}) or []
    return data

def fetch_noaa_swpc() -> dict:
    return {
        'flux': fetch_api_json(NOAA_SWPC_URLS['flux']) or [],
        'xray_primary': fetch_api_json(NOAA_SWPC_URLS['xray_primary']) or [],
        'xray_secondary': fetch_api_json(NOAA_SWPC_URLS['xray_secondary']) or [],
        'kp': fetch_api_json(NOAA_SWPC_URLS['kp']) or [],
        'planetary_a': fetch_api_json(NOAA_SWPC_URLS['planetary_a']) or [],
        'planetary_f': fetch_api_json(NOAA_SWPC_URLS['planetary_f']) or [],
        'magnetometer': fetch_api_json(NOAA_SWPC_URLS['magnetometer']) or []
    }

def _normalize_payload_to_dataframe(raw: Any) -> pd.DataFrame:
    if isinstance(raw, (str, Path)):
        raw = load_json_or_csv(str(raw))

    if isinstance(raw, pd.DataFrame):
        return raw.copy()

    if isinstance(raw, list):
        return pd.DataFrame(raw)

    if isinstance(raw, dict):
        if 'data' in raw and isinstance(raw['data'], (list, dict, pd.DataFrame)):
            return _normalize_payload_to_dataframe(raw['data'])
        frames = []
        for value in raw.values():
            if isinstance(value, (list, pd.DataFrame)):
                frames.append(pd.DataFrame(value))
        if frames:
            try:
                return pd.concat(frames, ignore_index=True, sort=False)
            except ValueError:
                return pd.DataFrame()
        return pd.DataFrame([raw])

    return pd.DataFrame()

def fetch_remote_json_or_text(url: str, timeout: int = 15):
    try:
        r = requests.get(url, timeout=timeout)
        r.raise_for_status()
        try:
            return r.json()
        except ValueError:
            return r.text
    except Exception:
        return None

def fetch_nasa_pds(source_url: str):
    return fetch_remote_json_or_text(source_url)

def fetch_real_source_data(start_date: Optional[str] = None, end_date: Optional[str] = None, nasa_key: str = 'DEMO_KEY', extra_urls: Optional[Dict[str, str]] = None) -> dict:
    if start_date is None or end_date is None:
        end_date = datetime.utcnow().strftime('%Y-%m-%d')
        start_date = (datetime.utcnow() - timedelta(days=30)).strftime('%Y-%m-%d')
    result = {
        'donki': fetch_nasa_donki(start_date, end_date, nasa_key),
        'noaa': fetch_noaa_swpc()
    }
    if extra_urls:
        for label, url in extra_urls.items():
            result[label] = load_source_payload(url)
            if result[label] is None and is_url(url):
                result[label] = fetch_nasa_pds(url)
    return result

def parse_donki_events(raw: Any) -> pd.DataFrame:
    """Parse NASA DONKI event lists into a normalized dataframe."""
    if isinstance(raw, (str, Path)):
        raw = load_json_or_csv(str(raw))

    if isinstance(raw, dict):
        frames = []
        for value in raw.values():
            if isinstance(value, (list, pd.DataFrame)):
                frames.append(_normalize_payload_to_dataframe(value))
        if frames:
            df = pd.concat(frames, ignore_index=True, sort=False)
        else:
            df = _normalize_payload_to_dataframe(raw)
    else:
        df = _normalize_payload_to_dataframe(raw)

    if df.empty:
        return pd.DataFrame()

    candidate_time_cols = ['eventTime', 'peakTime', 'startTime', 'beginTime', 'time']
    present_cols = [c for c in candidate_time_cols if c in df.columns]
    if present_cols:
        combined = pd.to_datetime(df[present_cols[0]], errors='coerce')
        for col in present_cols[1:]:
            combined = combined.combine_first(pd.to_datetime(df[col], errors='coerce'))
        df['eventTime'] = combined
        df['date'] = df['eventTime'].dt.date.astype(str)
        df.loc[df['eventTime'].isna(), 'date'] = ''
    else:
        df['eventTime'] = pd.NaT
        df['date'] = ''

    if 'classType' not in df.columns:
        df['classType'] = df.get('flrType', '') if hasattr(df, 'get') else ''

    return df[['date', 'eventTime', 'classType']].copy()

def parse_noaa_goes(raw: Any) -> pd.DataFrame:
    """Parse NOAA GOES or SWPC JSON/time series into a flat DataFrame."""
    if isinstance(raw, (str, Path)):
        raw = load_source_payload(raw)

    if isinstance(raw, dict):
        frames = []
        for value in raw.values():
            if isinstance(value, (list, pd.DataFrame, dict)):
                frames.append(_normalize_payload_to_dataframe(value))
        if frames:
            try:
                df = pd.concat(frames, ignore_index=True, sort=False)
            except ValueError:
                df = _normalize_payload_to_dataframe(raw)
        else:
            df = _normalize_payload_to_dataframe(raw)
    else:
        df = _normalize_payload_to_dataframe(raw)

    if df.empty:
        return pd.DataFrame()

    for alias in ['planetaryA', 'planetary_a', 'planetaryAIndex', 'planetaryKpIndex']:
        if alias in df.columns and 'planetary_a' not in df.columns:
            df['planetary_a'] = df[alias]
    for alias in ['planetaryF', 'planetary_f', 'planetaryFlux']:
        if alias in df.columns and 'planetary_f' not in df.columns:
            df['planetary_f'] = df[alias]
    for alias in ['electronFlux', 'electrons', 'electron_flux']:
        if alias in df.columns and 'electron_flux' not in df.columns:
            df['electron_flux'] = df[alias]
    for alias in ['Kp', 'kp_index', 'kIndex']:
        if alias in df.columns and 'kp' not in df.columns:
            df['kp'] = df[alias]

    for alias in ['total', 'Bt', 'totalField']:
        if alias in df.columns and 'mag' not in df.columns:
            df['mag'] = df[alias]

    for alias in ['Dst', 'DST']:
        if alias in df.columns and 'dst' not in df.columns:
            df['dst'] = df[alias]

    for tcol in ['time_tag', 'time', 'timestamp', 'date', 'eventTime']:
        if tcol in df.columns:
            df['time_tag'] = pd.to_datetime(df[tcol], errors='coerce', utc=True)
            break
    if 'time_tag' not in df.columns:
        df['time_tag'] = pd.NaT

    if 'time_tag' in df.columns:
        derived_date = df['time_tag'].dt.date.astype(str)
        if 'date' in df.columns:
            existing_date = df['date'].astype(str)
            df['date'] = derived_date.where(derived_date != 'NaT', existing_date)
        else:
            df['date'] = derived_date

    if 'flux' in df.columns:
        df['flux'] = pd.to_numeric(df['flux'], errors='coerce')
    if 'protonFlux' in df.columns and 'flux' not in df.columns:
        df['flux'] = pd.to_numeric(df['protonFlux'], errors='coerce')
    if 'proton_flux' in df.columns and 'flux' not in df.columns:
        df['flux'] = pd.to_numeric(df['proton_flux'], errors='coerce')
    if 'kp' in df.columns:
        df['kp'] = pd.to_numeric(df['kp'], errors='coerce')
    if 'planetary_kp' in df.columns and 'kp' not in df.columns:
        df['kp'] = pd.to_numeric(df['planetary_kp'], errors='coerce')
    if 'mag' in df.columns:
        df['mag'] = pd.to_numeric(df['mag'], errors='coerce')
    if 'planetary_a' in df.columns:
        df['planetary_a'] = pd.to_numeric(df['planetary_a'], errors='coerce')
    if 'planetary_f' in df.columns:
        df['planetary_f'] = pd.to_numeric(df['planetary_f'], errors='coerce')
    if 'electron_flux' in df.columns:
        df['electron_flux'] = pd.to_numeric(df['electron_flux'], errors='coerce')
    if 'dst' in df.columns:
        df['dst'] = pd.to_numeric(df['dst'], errors='coerce')
    if 'xray_flux' in df.columns:
        df['xray_flux'] = pd.to_numeric(df['xray_flux'], errors='coerce')

    return df

def parse_crater_summary(raw: Any) -> pd.DataFrame:
    if isinstance(raw, (str, Path)):
        raw = load_json_or_csv(str(raw))
    if isinstance(raw, pd.DataFrame):
        df = raw.copy()
    elif isinstance(raw, list):
        df = pd.DataFrame(raw)
    elif isinstance(raw, dict):
        df = _normalize_payload_to_dataframe(raw)
    else:
        return pd.DataFrame()

    if 'date' in df.columns:
        df['date'] = df['date'].astype(str)
    if 'radiation' in df.columns:
        df['radiation'] = pd.to_numeric(df['radiation'], errors='coerce')
    if 'doseRate' in df.columns:
        df['doseRate'] = pd.to_numeric(df['doseRate'], errors='coerce')
    if 'mSv' in df.columns:
        df['mSv'] = pd.to_numeric(df['mSv'], errors='coerce')
    if 'radiation_mSv' not in df.columns and 'mSv' in df.columns:
        df['radiation_mSv'] = df['mSv']
    if 'radiation_mSv' not in df.columns and 'doseRate' in df.columns:
        df['radiation_mSv'] = df['doseRate']

    return df

def parse_diviner_summary(raw: Any) -> pd.DataFrame:
    df = _normalize_payload_to_dataframe(raw)
    if df.empty:
        return df

    if 'date' in df.columns:
        df['date'] = df['date'].astype(str)
    if 'kelvin' in df.columns and 'temperature_C' not in df.columns:
        df['temperature_C'] = df['kelvin'] - 273.15
    if 'surface_temp' in df.columns and 'temperature_C' not in df.columns:
        df['temperature_C'] = df['surface_temp']
    if 'temperature' in df.columns and 'temperature_C' not in df.columns:
        df['temperature_C'] = df['temperature']

    return df

def parse_ldex_summary(raw: Any) -> pd.DataFrame:
    df = _normalize_payload_to_dataframe(raw)
    if df.empty:
        return df

    if 'date' in df.columns:
        df['date'] = df['date'].astype(str)
    if 'density' in df.columns:
        df['density'] = pd.to_numeric(df['density'], errors='coerce')
    if 'dust_g_cm3' in df.columns and 'density' not in df.columns:
        df['density'] = df['dust_g_cm3']
    return df

def parse_solar_cycle_indices(path: str) -> pd.DataFrame:
    """Parse NOAA SWPC's monthly `observed solar cycle indices.json` archive"""
    if isinstance(path, (str, Path)):
        p = Path(path)
        if not p.exists():
            return pd.DataFrame(columns=['date', 'ssn', 'planetary_f'])
        with p.open('r', encoding='utf-8') as fh:
            records = json.load(fh)
    else:
        records = path
    if not records:
        return pd.DataFrame(columns=['date', 'ssn', 'planetary_f'])

    rows = []
    for rec in records:
        tag = rec.get('time-tag')
        if not tag:
            continue
        ssn = rec.get('ssn')
        f107 = rec.get('f10.7')
        ssn = float(ssn) if ssn is not None and float(ssn) >= 0 else None
        f107 = float(f107) if f107 is not None and float(f107) > 0 else None
        if ssn is None and f107 is None:
            continue
        try:
            year, month = (int(x) for x in tag.split('-'))
            month_start = datetime(year, month, 1).date()
        except Exception:
            continue
        next_month = datetime(year + (1 if month == 12 else 0), 1 if month == 12 else month + 1, 1).date()
        days_in_month = (next_month - month_start).days
        for d in range(days_in_month):
            rows.append({
                'date': (month_start + timedelta(days=d)).isoformat(),
                'ssn': ssn,
                'planetary_f': f107,
            })

    return pd.DataFrame(rows, columns=['date', 'ssn', 'planetary_f'])

def parse_apollo_seismic_catalog(path: str) -> pd.DataFrame:
    """Parse the real Apollo Passive Seismic Experiment long period event"""
    p = Path(path)
    if not p.exists():
        return pd.DataFrame(columns=['date', 'quake_count'])

    df = pd.read_csv(p)
    if df.empty or 'Y' not in df.columns or 'JD' not in df.columns:
        return pd.DataFrame(columns=['date', 'quake_count'])

    df = df.dropna(subset=['Y', 'JD']).copy()
    df['Y'] = pd.to_numeric(df['Y'], errors='coerce')
    df['JD'] = pd.to_numeric(df['JD'], errors='coerce')
    df = df.dropna(subset=['Y', 'JD'])

    def year_jd_to_date(row) -> Any:
        try:
            year = 1900 + int(row['Y'])
            jd = int(row['JD'])
            return (datetime(year, 1, 1) + timedelta(days=jd - 1)).date()
        except Exception:
            return None

    df['date'] = df.apply(year_jd_to_date, axis=1)
    df = df.dropna(subset=['date'])
    df['date'] = df['date'].astype(str)

    amp_cols = [c for c in ('A1', 'A2', 'A3', 'A4') if c in df.columns]
    if amp_cols:
        df['magnitude'] = pd.to_numeric(df[amp_cols].bfill(axis=1).iloc[:, 0], errors='coerce')

    grade_mult = np.ones(len(df), dtype=np.float64)
    if 'Grade' in df.columns:
        g = df['Grade'].astype(str).str.upper().str.strip()

        grade_map = {'A': 1.25, 'B': 1.1, 'C': 1.0, 'D': 0.85, 'M': 1.15, 'S': 1.05}
        grade_mult = g.map(grade_map).fillna(1.0).to_numpy(dtype=np.float64)
    if 'Traces' in df.columns:
        tr = pd.to_numeric(df['Traces'], errors='coerce').fillna(0.0).clip(0.0, 20.0)
        grade_mult = grade_mult * (1.0 + 0.03 * tr.to_numpy(dtype=np.float64))

    if amp_cols and 'magnitude' in df.columns:
        mag = pd.to_numeric(df['magnitude'], errors='coerce').fillna(0.0).clip(lower=0.0)
        df['event_weight'] = (1.0 + np.log1p(mag)) * grade_mult
        intensity = df.groupby('date')['event_weight'].sum().rename('quake_count').reset_index()
        mags = df.groupby('date')['magnitude'].mean().reset_index()
        counts = intensity.merge(mags, on='date', how='left')
    else:
        df['event_weight'] = grade_mult
        counts = df.groupby('date')['event_weight'].sum().rename('quake_count').reset_index()

    return counts

def parse_apollo_pse(raw: Any) -> pd.DataFrame:
    df = _normalize_payload_to_dataframe(raw)
    if df.empty:
        return df

    if 'date' in df.columns:
        df['date'] = df['date'].astype(str)
    if 'magnitude' in df.columns:
        df['magnitude'] = pd.to_numeric(df['magnitude'], errors='coerce')
    if 'quake_count' not in df.columns:

        df['quake_count'] = 1
    return df

def parse_mem3(raw: Any) -> pd.DataFrame:
    df = _normalize_payload_to_dataframe(raw)
    if df.empty:
        return df

    if 'date' in df.columns:
        df['date'] = df['date'].astype(str)
    if 'flux' in df.columns:
        df['flux'] = pd.to_numeric(df['flux'], errors='coerce')
    if 'meteor_flux_1e15' in df.columns and 'flux' not in df.columns:
        df['flux'] = df['meteor_flux_1e15']
    return df

def save_dataset(path: str, df: pd.DataFrame) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(p, index=False)

def merge_noaa_sources(primary: Any, extras: Optional[List[Any]] = None) -> pd.DataFrame:
    """Merge primary NOAA payloads with additional archive-like sources."""
    frames = []
    if primary is not None:
        try:
            frames.append(parse_noaa_goes(primary))
        except Exception:
            pass
    if extras:
        for extra in extras:
            try:
                frames.append(parse_noaa_goes(extra))
            except Exception:
                pass
    if not frames:
        return pd.DataFrame()
    merged = pd.concat([f for f in frames if not f.empty], ignore_index=True, sort=False)
    if merged.empty:
        return merged
    if 'date' in merged.columns:
        merged['date'] = pd.to_datetime(merged['date'], errors='coerce').dt.date.astype(str)
    return merged

def save_parquet(path: str, df: pd.DataFrame) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    try:

        df.to_parquet(p, index=False)
    except Exception:

        df.to_csv(p.with_suffix('.csv'), index=False)

def append_parquet(path: str, df: pd.DataFrame) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    if not p.exists():
        save_parquet(path, df)
        return

    old = pd.read_parquet(p)
    combined = pd.concat([old, df], ignore_index=True)
    save_parquet(path, combined)

def batch_ingest_from_sources(sources: dict, out_dir: str = 'data/ingested', parquet: bool = True, chunk_size: int = 100000):
    donki = sources.get('donki')
    noaa = sources.get('noaa')
    diviner = sources.get('diviner')
    apollo = sources.get('apollo')
    mem3 = sources.get('mem3')
    ldex = sources.get('ldex')
    crater = sources.get('crater')

    extra_sources = [value for key, value in sources.items() if key not in {'donki', 'noaa', 'diviner', 'apollo', 'mem3', 'ldex', 'crater'}]
    if extra_sources:
        noaa = merge_noaa_sources(noaa, extra_sources)

    df = build_training_dataset(donki=donki, noaa=noaa, diviner=diviner, crater=crater, ldex=ldex, apollo=apollo, mem3=mem3)
    out_paths = []
    os.makedirs(out_dir, exist_ok=True)
    if df.empty:
        return out_paths

    n = len(df)
    if parquet:
        for i in range(0, n, chunk_size):
            chunk = df.iloc[i:i+chunk_size]
            path = os.path.join(out_dir, f'training_chunk_{int(time.time())}_{i//chunk_size}.parquet')
            save_parquet(path, chunk)
            out_paths.append(path)
    else:
        path = os.path.join(out_dir, f'training_{int(time.time())}.csv')
        save_dataset(path, df)
        out_paths.append(path)

    return out_paths

def fetch_api_json(url: str, params: dict = None, timeout: int = 15):
    try:
        r = requests.get(url, params=params, timeout=timeout)
        r.raise_for_status()
        return r.json()
    except Exception:
        return None

def feature_from_sources(
    donki: Optional[pd.DataFrame] = None,
    noaa: Optional[pd.DataFrame] = None,
    diviner: Optional[pd.DataFrame] = None,
    crater: Optional[pd.DataFrame] = None,
    ldex: Optional[pd.DataFrame] = None,
    apollo: Optional[pd.DataFrame] = None,
    mem3: Optional[pd.DataFrame] = None
) -> pd.DataFrame:
    records: List[Dict[str, Any]] = []
    donor_dates = set()

    def ensure_date_column(frame: pd.DataFrame) -> pd.DataFrame:
        if frame is None or frame.empty:
            return frame
        if 'date' not in frame.columns:
            if 'time_tag' in frame.columns:
                frame['date'] = pd.to_datetime(frame['time_tag'], errors='coerce').dt.date.astype(str)
            elif 'eventTime' in frame.columns:
                frame['date'] = pd.to_datetime(frame['eventTime'], errors='coerce').dt.date.astype(str)
            elif 'timestamp' in frame.columns:
                frame['date'] = pd.to_datetime(frame['timestamp'], errors='coerce').dt.date.astype(str)
        else:
            frame['date'] = pd.to_datetime(frame['date'], errors='coerce').dt.date.astype(str)
        return frame

    donki = ensure_date_column(donki) if donki is not None else donki
    noaa = ensure_date_column(noaa) if noaa is not None else noaa
    diviner = ensure_date_column(diviner) if diviner is not None else diviner
    crater = ensure_date_column(crater) if crater is not None else crater
    ldex = ensure_date_column(ldex) if ldex is not None else ldex
    apollo = ensure_date_column(apollo) if apollo is not None else apollo
    mem3 = ensure_date_column(mem3) if mem3 is not None else mem3

    all_frames = [donki, noaa, diviner, crater, ldex, apollo, mem3]

    def _col_agg_dict(frame: Optional[pd.DataFrame], column: str, agg: str) -> Dict[str, float]:
        if frame is None or frame.empty or column not in frame.columns or 'date' not in frame.columns:
            return {}
        sub = frame[['date', column]].dropna(subset=[column])
        if sub.empty:
            return {}
        return sub.groupby('date')[column].agg(agg).to_dict()

    def _count_prefix_dict(frame: Optional[pd.DataFrame], column: str, prefix: str) -> Dict[str, int]:
        """date -> count of rows where `column` (as str) startswith `prefix`."""
        if frame is None or frame.empty or column not in frame.columns or 'date' not in frame.columns:
            return {}
        mask = frame[column].astype(str).str.startswith(prefix)
        if not mask.any():
            return {}
        return frame.loc[mask].groupby('date').size().to_dict()

    donki_x_count = _count_prefix_dict(donki, 'classType', 'X')
    donki_m_count = _count_prefix_dict(donki, 'classType', 'M')

    noaa_flux = _col_agg_dict(noaa, 'flux', 'mean')
    noaa_kp = _col_agg_dict(noaa, 'kp', 'mean')
    noaa_planetary_a = _col_agg_dict(noaa, 'planetary_a', 'mean')
    noaa_planetary_f = _col_agg_dict(noaa, 'planetary_f', 'mean')
    noaa_ssn = _col_agg_dict(noaa, 'ssn', 'mean')
    noaa_mag = _col_agg_dict(noaa, 'mag', 'mean')
    noaa_dst = _col_agg_dict(noaa, 'dst', 'mean')
    noaa_xray_flux = _col_agg_dict(noaa, 'xray_flux', 'mean')

    diviner_temperature_C = _col_agg_dict(diviner, 'temperature_C', 'mean')
    diviner_surface_temp = _col_agg_dict(diviner, 'surface_temp', 'mean')

    apollo_quake_count = _col_agg_dict(apollo, 'quake_count', 'sum')
    apollo_magnitude_count = _col_agg_dict(apollo, 'magnitude', 'count')

    crater_radiation_mSv = _col_agg_dict(crater, 'radiation_mSv', 'mean')
    crater_radiation = _col_agg_dict(crater, 'radiation', 'mean')
    crater_doseRate = _col_agg_dict(crater, 'doseRate', 'mean')

    crater_has_radiation_mSv_col = bool(crater is not None and not crater.empty and 'radiation_mSv' in crater.columns)
    crater_dates_with_any_row = set(crater['date'].dropna().astype(str)) if (crater is not None and not crater.empty and 'date' in crater.columns) else set()

    mem3_flux = _col_agg_dict(mem3, 'flux', 'mean')

    ldex_density = _col_agg_dict(ldex, 'density', 'mean')
    ldex_dust_g_cm3 = _col_agg_dict(ldex, 'dust_g_cm3', 'mean')

    available_dates = set()
    for frame in all_frames:
        if frame is None or frame.empty or 'date' not in frame.columns:
            continue
        available_dates.update(frame['date'].dropna().astype(str).tolist())
    donor_dates.update(available_dates)

    if not donor_dates:
        return pd.DataFrame(columns=TRAINING_COLUMNS)

    parsed_series = pd.to_datetime(pd.Series(list(donor_dates)), errors='coerce')
    parsed_dates = [d for d in parsed_series.dropna().dt.date.tolist()]

    if not parsed_dates:
        return pd.DataFrame(columns=TRAINING_COLUMNS)

    start_date = min(parsed_dates)
    end_date = max(parsed_dates)
    all_date_objs = [start_date + timedelta(days=i) for i in range((end_date - start_date).days + 1)]
    all_dates = [d.strftime('%Y-%m-%d') for d in all_date_objs]

    def build_day_features(date_str: str, day) -> Dict[str, float]:
        if day is not None:
            day_of_year = day.timetuple().tm_yday
            phys_flux_default = physics_micrometeorite_flux(day_of_year=day_of_year)
            phys_dust_default = physics_dust(phys_flux_default)
            days_since_ref = (day - _LUNAR_PHASE_REFERENCE_NEW_MOON).days
            synthetic_local_time = ((days_since_ref % _LUNAR_SYNODIC_MONTH_DAYS) / _LUNAR_SYNODIC_MONTH_DAYS) * 24.0
            phys_temp_default = physics_temperature(0.0, 0.0, synthetic_local_time)
        else:
            phys_flux_default = 1.6
            phys_dust_default = 1.5
            phys_temp_default = -160.0

        out = {
            'solar_activity': 0.0,
            'radiation_mSv': 0.057,
            'temperature_C': phys_temp_default,

            'moonquakes_per_day': physics_moonquake_rate(),
            'meteor_flux_1e15': phys_flux_default,
            'dust_g_cm3': phys_dust_default
        }

        if donki is not None and not donki.empty and day is not None:
            try:
                x_count = donki_x_count.get(date_str, 0)
                m_count = donki_m_count.get(date_str, 0)
                out['solar_activity'] = max(1.0, 5.0 + x_count * 12.0 + m_count * 6.0)
                crater_day_present = date_str in crater_dates_with_any_row
                skip_bump = crater_day_present and crater_has_radiation_mSv_col
                if x_count > 0 and not skip_bump:
                    out['radiation_mSv'] = max(out['radiation_mSv'], 0.08 + x_count * 0.005)
                if m_count > 0 and not skip_bump:
                    out['radiation_mSv'] = max(out['radiation_mSv'], 0.06 + m_count * 0.003)
            except Exception:
                pass

        if noaa is not None and not noaa.empty:
            try:
                if date_str in noaa_flux:
                    flux = noaa_flux[date_str]
                    out['radiation_mSv'] = max(out['radiation_mSv'], 0.05 + flux * 0.00125)
                if date_str in noaa_kp:
                    kp = noaa_kp[date_str]
                    out['solar_activity'] = max(out['solar_activity'], 5.0 + kp * 1.8)
                    out['radiation_mSv'] = max(out['radiation_mSv'], 0.053 + kp * 0.003)
                if date_str in noaa_planetary_a:
                    a_index = noaa_planetary_a[date_str]
                    out['radiation_mSv'] = max(out['radiation_mSv'], 0.052 + a_index * 0.002)
                    out['solar_activity'] = max(out['solar_activity'], 5.0 + a_index * 0.35)
                if date_str in noaa_ssn:
                    ssn = noaa_ssn[date_str]
                    out['solar_activity'] = max(out['solar_activity'], 5.0 + ssn * 0.12)
                if date_str in noaa_planetary_f:
                    f_index = noaa_planetary_f[date_str]
                    out['radiation_mSv'] = max(out['radiation_mSv'], 0.052 + f_index * 0.001)
                    out['solar_activity'] = max(out['solar_activity'], 5.0 + max(0.0, f_index - 70.0) * 0.15)
                if date_str in noaa_mag:
                    mag = noaa_mag[date_str]
                    out['radiation_mSv'] = max(out['radiation_mSv'], 0.052 + abs(mag) * 0.0004)
                if date_str in noaa_dst:

                    dst = noaa_dst[date_str]
                    out['radiation_mSv'] = max(out['radiation_mSv'], 0.052 + abs(dst) * 0.0003)
                    out['solar_activity'] = max(out['solar_activity'], 5.0 + abs(dst) * 0.04)
                if date_str in noaa_xray_flux:

                    import math as _math
                    xray = noaa_xray_flux[date_str]
                    if xray > 0:
                        out['solar_activity'] = max(out['solar_activity'], 5.0 + max(0.0, _math.log10(xray) + 9.0) * 3.0)
            except Exception:
                pass

        if diviner is not None and not diviner.empty:
            try:
                if 'temperature_C' in diviner.columns:
                    out['temperature_C'] = safe_float(diviner_temperature_C.get(date_str), out['temperature_C'])
                elif 'surface_temp' in diviner.columns:
                    out['temperature_C'] = safe_float(diviner_surface_temp.get(date_str), out['temperature_C'])
            except Exception:
                pass

        if apollo is not None and not apollo.empty:
            try:
                if 'quake_count' in apollo.columns:
                    out['moonquakes_per_day'] = safe_float(apollo_quake_count.get(date_str), out['moonquakes_per_day'])
                elif 'magnitude' in apollo.columns:
                    out['moonquakes_per_day'] = safe_float(apollo_magnitude_count.get(date_str), out['moonquakes_per_day'])
            except Exception:
                pass

        if crater is not None and not crater.empty:
            try:
                if 'radiation_mSv' in crater.columns:
                    out['radiation_mSv'] = max(out['radiation_mSv'], safe_float(crater_radiation_mSv.get(date_str), out['radiation_mSv']))
                elif 'radiation' in crater.columns:
                    out['radiation_mSv'] = max(out['radiation_mSv'], safe_float(crater_radiation.get(date_str), out['radiation_mSv']))
                elif 'doseRate' in crater.columns:
                    out['radiation_mSv'] = max(out['radiation_mSv'], safe_float(crater_doseRate.get(date_str), out['radiation_mSv']))
            except Exception:
                pass

        if mem3 is not None and not mem3.empty:
            try:
                if 'flux' in mem3.columns:
                    out['meteor_flux_1e15'] = safe_float(mem3_flux.get(date_str), out['meteor_flux_1e15'])
            except Exception:
                pass

        if ldex is not None and not ldex.empty:
            try:
                if 'density' in ldex.columns:
                    out['dust_g_cm3'] = safe_float(ldex_density.get(date_str), out['dust_g_cm3'])
                if 'dust_g_cm3' in ldex.columns:
                    out['dust_g_cm3'] = safe_float(ldex_dust_g_cm3.get(date_str), out['dust_g_cm3'])
            except Exception:
                pass

        if out['dust_g_cm3'] < 0.01:
            out['dust_g_cm3'] = 1.5

        return out

    def has_data_on(date_str: str) -> bool:
        return date_str in available_dates

    total_dates = len(all_dates)
    show_progress = total_dates > 5000
    for i, day_obj in enumerate(all_date_objs):
        if show_progress and i % 10000 == 0:
            print(f"  feature_from_sources: {i}/{total_dates} dates scanned...", flush=True)
        date_str = all_dates[i]
        target_day_obj = day_obj + timedelta(days=1)
        target_date = target_day_obj.strftime('%Y-%m-%d')
        if not has_data_on(date_str) and not has_data_on(target_date):
            continue
        input_values = build_day_features(date_str, day_obj)
        target_values = build_day_features(target_date, target_day_obj)

        row = {
            'date': date_str,
            'solar_activity': input_values['solar_activity'],
            'radiation_mSv': input_values['radiation_mSv'],
            'temperature_C': input_values['temperature_C'],
            'moonquakes_per_day': input_values['moonquakes_per_day'],
            'meteor_flux_1e15': input_values['meteor_flux_1e15'],
            'dust_g_cm3': input_values['dust_g_cm3'],
            'target_solar_activity': target_values['solar_activity'],
            'target_radiation_mSv': target_values['radiation_mSv'],
            'target_temperature_C': target_values['temperature_C'],
            'target_moonquakes_per_day': target_values['moonquakes_per_day'],
            'target_meteor_flux_1e15': target_values['meteor_flux_1e15'],
            'target_dust_g_cm3': target_values['dust_g_cm3']
        }

        records.append(row)

    return pd.DataFrame(records, columns=['date'] + TRAINING_COLUMNS)

def build_training_dataset(
    donki: Optional[Any] = None,
    noaa: Optional[Any] = None,
    diviner: Optional[Any] = None,
    crater: Optional[Any] = None,
    ldex: Optional[Any] = None,
    apollo: Optional[Any] = None,
    mem3: Optional[Any] = None
) -> pd.DataFrame:
    return feature_from_sources(
        parse_donki_events(donki),
        parse_noaa_goes(noaa),
        parse_diviner_summary(diviner),
        parse_crater_summary(crater),
        parse_ldex_summary(ldex),
        parse_apollo_pse(apollo),
        parse_mem3(mem3)
    )

def load_omni2_daily(path: str = 'data/archives/omni2_daily.csv') -> pd.DataFrame:
    """Load the real, per day aggregated NASA OMNI2 solar wind/IMF/Kp/Dst"""
    p = Path(path)
    if not p.exists():
        return pd.DataFrame(columns=['date', 'solar_wind_speed', 'solar_wind_density', 'imf_bz', 'kp_index', 'dst', 'ap', 'f107'])
    df = pd.read_csv(p)
    df['date'] = df['date'].astype(str)
    return df

def load_diviner_site_climatology(
    path: str = 'data/archives/diviner/site_climatology.json',
) -> Dict[str, Any]:
    """Load per-site Diviner GCP bolometric T vs local-time (hourly °C)."""
    p = Path(path)
    if not p.exists():
        return {}
    try:
        payload = json.loads(p.read_text(encoding='utf-8'))
    except Exception:
        return {}
    sites = payload.get('sites') if isinstance(payload, dict) else None
    return sites if isinstance(sites, dict) else {}

def diviner_temp_C(climatology: Dict[str, Any], site_name: str, local_time: float) -> Optional[float]:
    """Lookup Diviner climatology temperature (°C) at local solar time."""
    rec = climatology.get(site_name) if climatology else None
    if not rec:
        return None
    hourly = rec.get('temp_C_hourly')
    if not hourly or len(hourly) < 24:
        return None
    h = float(local_time) % 24.0
    i0 = int(h) % 24
    i1 = (i0 + 1) % 24
    frac = h - int(h)
    return float(hourly[i0] * (1.0 - frac) + hourly[i1] * frac)

def load_diviner_prp_polar_temps(
    path: str = 'data/archives/diviner/prp_polar_site_temps.json',
) -> Dict[str, Any]:
    """Load nearest-triangle Diviner PRP averages for polar LIPAS sites."""
    p = Path(path)
    if not p.exists():
        return {}
    try:
        payload = json.loads(p.read_text(encoding='utf-8'))
    except Exception:
        return {}
    sites = payload.get('sites') if isinstance(payload, dict) else None
    return sites if isinstance(sites, dict) else {}

def diviner_prp_polar_temp_C(prp_sites: Dict[str, Any], site_name: str) -> Optional[float]:
    """Return PRP polar average temperature (°C) when available."""
    rec = prp_sites.get(site_name) if prp_sites else None
    if not rec:
        return None
    t = rec.get('temp_avg_C')
    if t is None:
        return None
    try:
        return float(t)
    except Exception:
        return None

def load_silso_daily_ssn(path: str = 'data/archives/silso_daily_sunspot.csv') -> pd.DataFrame:
    """Load SILSO daily total sunspot number (semicolon CSV)."""
    p = Path(path)
    if not p.exists():
        return pd.DataFrame(columns=['date', 'ssn'])
    rows = []
    with p.open('r', encoding='utf-8', errors='replace') as fh:
        for line in fh:
            parts = [x.strip() for x in line.strip().split(';')]
            if len(parts) < 5:
                continue
            try:
                y, m, d = int(parts[0]), int(parts[1]), int(parts[2])
                ssn = float(parts[4])
            except Exception:
                continue
            if ssn < 0:
                continue
            rows.append({'date': f'{y:04d}-{m:02d}-{d:02d}', 'ssn': ssn})
    if not rows:
        return pd.DataFrame(columns=['date', 'ssn'])
    return pd.DataFrame(rows)

def load_ldex_local_time_profile(
    path: str = 'data/archives/ldex/ldex_ltden_pds_derived.tab',
) -> np.ndarray:
    """Normalize LDEX altitude×local-time density table to a 24h factor (~1 mean)."""
    p = Path(path)
    if not p.exists():
        return np.ones(24, dtype=np.float64)
    rows = []
    with p.open(encoding='utf-8', errors='replace') as fh:
        for line in fh:
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
    return (interp / mean).astype(np.float64)

_SERVE_DRIVERS_CACHE: Optional[Dict[str, Any]] = None
_SERVE_DRIVERS_CACHE_TS: float = 0.0

def _json_latest_flux(path: Path, flux_key: str = 'flux') -> Optional[float]:
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        return None
    if isinstance(payload, list) and payload:

        try:
            ordered = sorted(
                (r for r in payload if isinstance(r, dict) and r.get(flux_key) is not None),
                key=lambda r: str(r.get('time_tag') or ''),
            )
            if ordered:
                return float(ordered[-1][flux_key])
        except Exception:
            pass
        for rec in reversed(payload):
            if isinstance(rec, dict) and rec.get(flux_key) is not None:
                try:
                    return float(rec[flux_key])
                except Exception:
                    continue
    return None

def load_serve_space_drivers(force_reload: bool = False) -> Dict[str, Any]:
\
\
\
\
\

    global _SERVE_DRIVERS_CACHE, _SERVE_DRIVERS_CACHE_TS
    now = time.time()
    if (
        not force_reload
        and _SERVE_DRIVERS_CACHE is not None
        and (now - _SERVE_DRIVERS_CACHE_TS) < 300.0
    ):
        return dict(_SERVE_DRIVERS_CACHE)

    root = Path(__file__).resolve().parent
    arch = root / 'data' / 'archives'
    out: Dict[str, Any] = {
        'sources': [],
        'omni_date': None,
        'solar_wind_speed': None,
        'solar_wind_density': None,
        'imf_bz': None,
        'kp_index': None,
        'dst': None,
        'ap': None,
        'f107': None,
        'proton_flux': None,
        'ssn': None,
        'ldex_profile': None,
    }

    omni = load_omni2_daily(str(arch / 'omni2_daily.csv'))
    if not omni.empty:

        ranked = omni.dropna(subset=['kp_index'], how='all')
        if ranked.empty:
            ranked = omni.dropna(
                subset=['solar_wind_speed', 'f107', 'dst', 'ap'], how='all'
            )
        if not ranked.empty:
            row = ranked.iloc[-1]
            out['omni_date'] = str(row.get('date'))
            for k in (
                'solar_wind_speed', 'solar_wind_density', 'imf_bz',
                'kp_index', 'dst', 'ap', 'f107',
            ):
                v = row.get(k)
                try:
                    fv = float(v)
                    if np.isfinite(fv):
                        out[k] = fv
                except Exception:
                    pass
            out['sources'].append('omni2_daily')

    kp_live = _json_latest_flux(arch / 'noaa_planetary_k_index.json', 'Kp')
    if kp_live is None:

        p = arch / 'noaa_planetary_k_index.json'
        if p.exists():
            try:
                raw = json.loads(p.read_text(encoding='utf-8'))
                if isinstance(raw, list) and len(raw) > 1 and isinstance(raw[-1], list):

                    kp_live = float(raw[-1][1])
            except Exception:
                pass
    if kp_live is not None and np.isfinite(kp_live):
        out['kp_index'] = float(kp_live)
        out['sources'].append('swpc_kp')

    f107_live = _json_latest_flux(arch / 'f107_cm_flux.json', 'flux')
    if f107_live is not None and np.isfinite(f107_live) and f107_live > 0:
        out['f107'] = float(f107_live)
        out['sources'].append('swpc_f107')

    proton_path = arch / 'goes_integral_protons_1day.json'
    if proton_path.exists():
        try:
            protons = json.loads(proton_path.read_text(encoding='utf-8'))
            if isinstance(protons, list) and protons:
                prefer = [
                    r for r in protons
                    if isinstance(r, dict) and '10' in str(r.get('energy') or '')
                ]
                pool = prefer or [r for r in protons if isinstance(r, dict)]
                pool = sorted(pool, key=lambda r: str(r.get('time_tag') or ''))
                if pool and pool[-1].get('flux') is not None:
                    out['proton_flux'] = max(0.05, float(pool[-1]['flux']))
                    out['sources'].append('goes_protons')
        except Exception:
            pass

    silso = load_silso_daily_ssn(str(arch / 'silso_daily_sunspot.csv'))
    if not silso.empty:
        try:
            out['ssn'] = float(silso.iloc[-1]['ssn'])
            out['sources'].append('silso')
            if out.get('f107') is None and out['ssn'] is not None:
                from gap_fill import f107_from_ssn
                out['f107'] = float(f107_from_ssn(out['ssn']))
                out['sources'].append('silso_f107_proxy')
        except Exception:
            pass

    try:
        out['ldex_profile'] = load_ldex_local_time_profile(
            str(arch / 'ldex' / 'ldex_ltden_pds_derived.tab')
        )
        if out['ldex_profile'] is not None:
            out['sources'].append('ldex_climatology')
    except Exception:
        out['ldex_profile'] = None

    try:
        from gap_fill import cross_fill_omni_drivers
        frame = pd.DataFrame([{
            'solar_wind_speed': out.get('solar_wind_speed'),
            'solar_wind_density': out.get('solar_wind_density'),
            'imf_bz': out.get('imf_bz'),
            'kp_index': out.get('kp_index'),
            'f107': out.get('f107'),
            'dst': out.get('dst'),
            'ap': out.get('ap'),
            'ssn': out.get('ssn'),
        }])
        filled = cross_fill_omni_drivers(frame)
        for k in (
            'solar_wind_speed', 'solar_wind_density', 'imf_bz',
            'kp_index', 'f107', 'dst', 'ap',
        ):
            if k in filled.columns:
                v = filled.iloc[0][k]
                try:
                    fv = float(v)
                    if np.isfinite(fv):
                        out[k] = fv
                except Exception:
                    pass
    except Exception:
        pass

    _SERVE_DRIVERS_CACHE = dict(out)
    _SERVE_DRIVERS_CACHE_TS = now
    return dict(out)

def serve_extra_for_local_time(local_time: Optional[float] = None) -> Dict[str, Any]:
    """Build refine_prediction/physics_estimate `extra` from cached archives."""
    drv = load_serve_space_drivers()
    extra: Dict[str, Any] = {}
    for k in (
        'solar_wind_speed', 'solar_wind_density', 'imf_bz',
        'kp_index', 'f107', 'dst', 'ap', 'proton_flux',
    ):
        if drv.get(k) is not None:
            extra[k] = drv[k]
    profile = drv.get('ldex_profile')
    if profile is not None and local_time is not None:
        try:
            extra['ldex_factor'] = float(profile[int(float(local_time)) % 24])
        except Exception:
            pass
    extra['driver_sources'] = list(drv.get('sources') or [])
    extra['omni_date'] = drv.get('omni_date')
    return extra

def build_extended_training_dataset(
    donki: Optional[Any] = None,
    noaa: Optional[Any] = None,
    diviner: Optional[Any] = None,
    crater: Optional[Any] = None,
    ldex: Optional[Any] = None,
    apollo: Optional[Any] = None,
    mem3: Optional[Any] = None,
    omni: Optional[pd.DataFrame] = None,
    sites: Optional[list] = None,
) -> pd.DataFrame:
    """Build the real 18 input feature training dataset consumed by the"""
    from lunar_physics import (
        physics_temperature,
        physics_micrometeorite_flux,
        physics_dust,
        physics_moonquake_rate,
        physics_radiation,
    )
    from lunar_sites import LUNAR_SITES as _DEFAULT_SITES

    sites = sites if sites is not None else _DEFAULT_SITES
    base = feature_from_sources(
        parse_donki_events(donki),
        parse_noaa_goes(noaa),
        parse_diviner_summary(diviner),
        parse_crater_summary(crater),
        parse_ldex_summary(ldex),
        parse_apollo_pse(apollo),
        parse_mem3(mem3),
    )
    if base.empty:
        return pd.DataFrame(columns=['date', 'site'] + EXTENDED_TRAINING_COLUMNS)

    from gap_fill import (
        expand_base_to_omni_spine,
        cross_fill_omni_drivers,
        interpolate_numeric_columns,
        gap_fill_extended_training,
    )

    omni = omni if omni is not None else pd.DataFrame(columns=['date', 'solar_wind_speed', 'solar_wind_density', 'imf_bz', 'kp_index'])
    omni = omni.copy()
    omni['date'] = omni['date'].astype(str)
    if not omni.empty:

        silso_early = load_silso_daily_ssn()
        if not silso_early.empty:
            omni = omni.merge(silso_early, on='date', how='left')
        cycle_path = Path('data/archives/observed_solar_cycle_indices.json')
        if cycle_path.exists():
            cycle = parse_solar_cycle_indices(str(cycle_path))
            if not cycle.empty and 'planetary_f' in cycle.columns:
                c2 = cycle[['date', 'planetary_f']].rename(columns={'planetary_f': 'cycle_f107'})
                omni = omni.merge(c2, on='date', how='left')
                if 'f107' in omni.columns:
                    miss = omni['f107'].isna() | (pd.to_numeric(omni['f107'], errors='coerce') <= 0)
                    omni.loc[miss, 'f107'] = pd.to_numeric(omni.loc[miss, 'cycle_f107'], errors='coerce')
                else:
                    omni['f107'] = pd.to_numeric(omni.get('cycle_f107'), errors='coerce')
        omni = interpolate_numeric_columns(
            omni,
            [c for c in ('solar_wind_speed', 'solar_wind_density', 'imf_bz', 'kp_index', 'f107', 'dst', 'ap', 'ssn') if c in omni.columns],
            limit=5,
        )
        omni = cross_fill_omni_drivers(omni)

    base = base.copy()
    base['date'] = base['date'].astype(str)

    if not omni.empty:
        base = expand_base_to_omni_spine(base, omni, max_gap_days=3)
    base['_date_obj'] = pd.to_datetime(base['date'], errors='coerce')
    base['_next_date'] = (base['_date_obj'] + timedelta(days=1)).dt.date.astype(str)

    omni_cols = ['date', 'solar_wind_speed', 'solar_wind_density', 'imf_bz', 'kp_index']
    for opt in ('f107', 'dst', 'ap'):
        if opt in omni.columns:
            omni_cols.append(opt)
    omni_input = omni.copy()
    base = base.merge(omni_input[omni_cols], on='date', how='left')
    rename_tg = {
        'date': '_next_date',
        'solar_wind_speed': 'target_solar_wind_speed',
        'solar_wind_density': 'target_solar_wind_density',
        'imf_bz': 'target_imf_bz',
        'kp_index': 'target_kp_index',
    }
    if 'f107' in omni_input.columns:
        rename_tg['f107'] = 'target_f107'
    if 'dst' in omni_input.columns:
        rename_tg['dst'] = 'target_dst'
    if 'ap' in omni_input.columns:
        rename_tg['ap'] = 'target_ap'
    omni_target = omni_input[omni_cols].rename(columns=rename_tg)
    base = base.merge(omni_target, on='_next_date', how='left')

    for col in ['solar_wind_speed', 'solar_wind_density', 'imf_bz', 'kp_index', 'f107', 'dst', 'ap']:
        if col not in base.columns:
            continue
        if base[col].notna().any():
            base[col] = base[col].fillna(base[col].median())
        else:
            base[col] = base[col].fillna(0.0)
        tcol = f'target_{col}'
        if tcol in base.columns:
            if base[tcol].notna().any():
                base[tcol] = base[tcol].fillna(base[tcol].median())
            else:
                base[tcol] = base[tcol].fillna(0.0)

    if 'f107' in base.columns and base['f107'].notna().any():
        f107_sa = ((base['f107'].astype(float) - 70.0) / 18.0).clip(lower=0.0, upper=40.0)
        base['solar_activity'] = (
            0.55 * base['solar_activity'].astype(float) + 0.45 * f107_sa
        ).clip(lower=0.0, upper=80.0)
        if 'target_f107' in base.columns:
            f107_sa_tg = ((base['target_f107'].astype(float) - 70.0) / 18.0).clip(lower=0.0, upper=40.0)
            base['target_solar_activity'] = (
                0.55 * base['target_solar_activity'].astype(float) + 0.45 * f107_sa_tg
            ).clip(lower=0.0, upper=80.0)

    silso = load_silso_daily_ssn()
    if not silso.empty:
        base = base.merge(silso, on='date', how='left')
        if base['ssn'].notna().any():
            ssn_sa = (base['ssn'].astype(float) / 12.0).clip(lower=0.0, upper=40.0)

            base['solar_activity'] = (
                0.85 * base['solar_activity'].astype(float) + 0.15 * ssn_sa.fillna(base['solar_activity'])
            ).clip(lower=0.0, upper=80.0)
            silso_tg = silso.rename(columns={'date': '_next_date', 'ssn': 'target_ssn'})
            base = base.merge(silso_tg, on='_next_date', how='left')
            if 'target_ssn' in base.columns:
                ssn_sa_tg = (base['target_ssn'].astype(float) / 12.0).clip(lower=0.0, upper=40.0)
                base['target_solar_activity'] = (
                    0.85 * base['target_solar_activity'].astype(float)
                    + 0.15 * ssn_sa_tg.fillna(base['target_solar_activity'])
                ).clip(lower=0.0, upper=80.0)

    ldex_profile = None
    if isinstance(ldex, np.ndarray) and len(ldex) >= 24:
        ldex_profile = np.asarray(ldex, dtype=np.float64)

    diviner_clim = load_diviner_site_climatology()

    rows = []
    for site in sites:
        site_df = base.copy()
        site_df['site'] = site.name
        site_df['lat'] = site.lat
        site_df['lon'] = site.lon
        site_df['regolith_depth'] = site.regolith_depth
        site_df['thermal_inertia'] = site.thermal_inertia
        site_albedo = float(getattr(site, 'albedo', 0.07))
        site_emiss = float(getattr(site, 'emissivity', 0.95))
        site_terrain = str(getattr(site, 'terrain', 'mare'))

        day_objs = site_df['_date_obj']
        next_day_objs = day_objs + timedelta(days=1)
        days_since_ref = (day_objs - pd.Timestamp(_LUNAR_PHASE_REFERENCE_NEW_MOON)).dt.days
        local_time = ((days_since_ref % _LUNAR_SYNODIC_MONTH_DAYS) / _LUNAR_SYNODIC_MONTH_DAYS) * 24.0
        next_days_since_ref = (next_day_objs - pd.Timestamp(_LUNAR_PHASE_REFERENCE_NEW_MOON)).dt.days
        next_local_time = ((next_days_since_ref % _LUNAR_SYNODIC_MONTH_DAYS) / _LUNAR_SYNODIC_MONTH_DAYS) * 24.0

        site_df['local_solar_time'] = local_time
        site_df['hour_of_day'] = local_time % 24.0
        site_df['day_of_month'] = day_objs.dt.day.astype(float)
        site_df['month_of_year'] = day_objs.dt.month.astype(float)

        doys = day_objs.dt.dayofyear.astype(int).tolist()
        next_doys = next_day_objs.dt.dayofyear.astype(int).tolist()
        lt_list = local_time.tolist() if hasattr(local_time, 'tolist') else list(local_time)
        nlt_list = next_local_time.tolist() if hasattr(next_local_time, 'tolist') else list(next_local_time)
        def _temp_blend(lt, doy):
            phys = physics_temperature(
                site.lat, site.lon, lt, albedo=site_albedo, emissivity=site_emiss,
                day_of_year=doy, terrain=site_terrain, thermal_inertia=site.thermal_inertia,
            )
            div = diviner_temp_C(diviner_clim, site.name, lt)
            if div is None:
                return float(phys)

            return float(0.75 * float(div) + 0.25 * float(phys))

        site_df['temperature_C'] = [_temp_blend(lt, doy) for lt, doy in zip(lt_list, doys)]
        site_df['target_temperature_C'] = [
            _temp_blend(lt, doy) for lt, doy in zip(nlt_list, next_doys)
        ]
        flux_in = [physics_micrometeorite_flux(day_of_year=d, lat=site.lat) for d in doys]
        flux_tg = [physics_micrometeorite_flux(day_of_year=d, lat=site.lat) for d in next_doys]
        site_df['meteor_flux_1e15'] = flux_in
        site_df['target_meteor_flux_1e15'] = flux_tg

        def _ldex_fac(hour_v):
            if ldex_profile is None:
                return 1.0
            return float(ldex_profile[int(float(hour_v)) % 24])

        site_df['dust_g_cm3'] = [
            physics_dust(
                f, lat=site.lat, local_time=lt, ldex_factor=_ldex_fac(lt),
                regolith_depth=site.regolith_depth,
            )
            for f, lt in zip(flux_in, lt_list)
        ]
        site_df['target_dust_g_cm3'] = [
            physics_dust(
                f, lat=site.lat, local_time=lt, ldex_factor=_ldex_fac(lt),
                regolith_depth=site.regolith_depth,
            )
            for f, lt in zip(flux_tg, nlt_list)
        ]

        mq = site_df['moonquakes_per_day'].astype(float)
        mq_phys = [
            physics_moonquake_rate(
                lat=site.lat, local_time=lt, regolith_depth=site.regolith_depth,
            )
            for lt in lt_list
        ]
        mq_phys_tg = [
            physics_moonquake_rate(
                lat=site.lat, local_time=lt, regolith_depth=site.regolith_depth,
            )
            for lt in nlt_list
        ]

        if float(mq.std()) <= 5.0:
            site_df['moonquakes_per_day'] = mq_phys
            site_df['target_moonquakes_per_day'] = mq_phys_tg
        else:
            med = float(mq.median())
            site_df['moonquakes_per_day'] = [
                phys if abs(float(obs) - med) < 1.0 else float(obs)
                for obs, phys in zip(mq.tolist(), mq_phys)
            ]
            mq_tg = site_df['target_moonquakes_per_day'].astype(float)
            med_tg = float(mq_tg.median()) if len(mq_tg) else 46.0
            site_df['target_moonquakes_per_day'] = [
                phys if abs(float(obs) - med_tg) < 1.0 else float(obs)
                for obs, phys in zip(mq_tg.tolist(), mq_phys_tg)
            ]

        if 'kp_index' in site_df.columns:
            kp_vals = site_df['kp_index'].astype(float).tolist()
            sa_vals = site_df['solar_activity'].astype(float).tolist()
            bz_vals = site_df['imf_bz'].astype(float).tolist() if 'imf_bz' in site_df.columns else [None] * len(kp_vals)
            vsw_vals = site_df['solar_wind_speed'].astype(float).tolist() if 'solar_wind_speed' in site_df.columns else [None] * len(kp_vals)
            rad_phys = [
                physics_radiation(
                    solar_activity=sa, kp=kp, proton_flux=max(1.0, sa),
                    lat=site.lat, imf_bz=bz, solar_wind_speed=vsw,
                )
                for sa, kp, bz, vsw in zip(sa_vals, kp_vals, bz_vals, vsw_vals)
            ]

            if 'dst' in site_df.columns:
                dst_boost = (site_df['dst'].astype(float).clip(upper=0.0).abs() / 180.0).clip(0.0, 1.5)
                rad_phys = [float(p) * (1.0 + 0.22 * float(b)) for p, b in zip(rad_phys, dst_boost.tolist())]
            site_df['radiation_mSv'] = [
                max(float(obs), 0.65 * float(phys) + 0.35 * float(obs))
                for obs, phys in zip(site_df['radiation_mSv'].tolist(), rad_phys)
            ]

            kp_next = site_df['kp_index'].astype(float).shift(-1).fillna(site_df['kp_index']).tolist()
            sa_next = site_df['target_solar_activity'].astype(float).tolist()
            bz_next = site_df['imf_bz'].astype(float).shift(-1).fillna(site_df['imf_bz']).tolist() if 'imf_bz' in site_df.columns else [None] * len(kp_next)
            vsw_next = site_df['solar_wind_speed'].astype(float).shift(-1).fillna(site_df['solar_wind_speed']).tolist() if 'solar_wind_speed' in site_df.columns else [None] * len(kp_next)
            rad_phys_tg = [
                physics_radiation(
                    solar_activity=sa, kp=kp, proton_flux=max(1.0, sa),
                    lat=site.lat, imf_bz=bz, solar_wind_speed=vsw,
                )
                for sa, kp, bz, vsw in zip(sa_next, kp_next, bz_next, vsw_next)
            ]
            if 'target_dst' in site_df.columns:
                dst_boost_tg = (site_df['target_dst'].astype(float).clip(upper=0.0).abs() / 180.0).clip(0.0, 1.5)
                rad_phys_tg = [float(p) * (1.0 + 0.22 * float(b)) for p, b in zip(rad_phys_tg, dst_boost_tg.tolist())]
            site_df['target_radiation_mSv'] = [
                max(float(obs), 0.65 * float(phys) + 0.35 * float(obs))
                for obs, phys in zip(site_df['target_radiation_mSv'].tolist(), rad_phys_tg)
            ]

        rows.append(site_df)

    out = pd.concat(rows, ignore_index=True)
    out = out.rename(columns={
        'solar_wind_speed': 'solar_wind_speed', 'solar_wind_density': 'solar_wind_density',
        'imf_bz': 'imf_bz', 'kp_index': 'kp_index',
    })
    keep_cols = ['date', 'site'] + EXTENDED_TRAINING_COLUMNS
    out = out[keep_cols].copy()
    for col in EXTENDED_TRAINING_COLUMNS:
        out[col] = pd.to_numeric(out[col], errors='coerce')

    out = gap_fill_extended_training(out)
    return out

def load_extended_training_csv(path: str) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Load an extended (18 input) training CSV produced by"""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Extended training CSV not found: {path}")
    df = pd.read_csv(path)
    missing = [c for c in EXTENDED_TRAINING_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"Missing required extended columns: {missing}")
    df = df.dropna(subset=EXTENDED_TRAINING_COLUMNS, axis=0, how='any')
    X = df[EXTENDED_INPUT_COLUMNS].astype(float)
    Y = df[TARGET_COLUMNS].astype(float)
    return X, Y

def parse_json_or_dataframe(raw: Any) -> pd.DataFrame:
    return _normalize_payload_to_dataframe(raw)

def dataset_completeness_report(csv_path: str) -> dict:
    """Return a simple completeness report for a canonical training CSV."""
    p = Path(csv_path)
    if not p.exists():
        raise FileNotFoundError(csv_path)
    df = pd.read_csv(p)
    report = {}
    report['rows'] = len(df)
    for col in TRAINING_COLUMNS:
        report[f'present_{col}'] = int(df[col].notna().sum())
        report[f'percent_{col}'] = float(df[col].notna().mean() * 100.0)
    return report

def augment_training_df(df: pd.DataFrame, target_rows: int = 128, seed: int = 42) -> pd.DataFrame:
    """Light noise augmentation."""
    import numpy as _np
    _np.random.seed(seed)
    if df.empty:
        return df

    base = df.copy()
    rows = [base]
    n_existing = len(base)
    if n_existing == 0:
        return df

    while sum(len(r) for r in rows) < target_rows:
        samp = base.sample(min(len(base), max(1, n_existing // 2))).copy()

        noise = _np.random.normal(scale=0.05, size=(len(samp),))
        samp['solar_activity'] = (samp['solar_activity'] * (1.0 + noise)).clip(lower=0.0)
        samp['radiation_mSv'] = (samp['radiation_mSv'] * (1.0 + noise * 0.5) + (samp['solar_activity'] - samp['target_solar_activity']) * 0.001).clip(lower=0.0)
        samp['temperature_C'] = samp['temperature_C'] + _np.random.normal(scale=1.0, size=(len(samp),))
        samp['moonquakes_per_day'] = (samp['moonquakes_per_day'] + _np.random.poisson(lam=0.5, size=(len(samp),))).clip(lower=0.0)
        samp['meteor_flux_1e15'] = (samp['meteor_flux_1e15'] * (1.0 + _np.random.normal(scale=0.02, size=(len(samp),)))).clip(lower=0.0)
        samp['dust_g_cm3'] = (samp['dust_g_cm3'] * (1.0 + _np.random.normal(scale=0.02, size=(len(samp),)))).clip(lower=0.001)

        samp['target_solar_activity'] = (samp['target_solar_activity'] * (1.0 + _np.random.normal(scale=0.05, size=(len(samp),)))).clip(lower=0.0)
        samp['target_radiation_mSv'] = (samp['target_radiation_mSv'] * (1.0 + _np.random.normal(scale=0.05, size=(len(samp),)))).clip(lower=0.0)
        samp['target_temperature_C'] = samp['target_temperature_C'] + _np.random.normal(scale=1.5, size=(len(samp),))
        samp['target_moonquakes_per_day'] = (samp['target_moonquakes_per_day'] + _np.random.poisson(lam=0.3, size=(len(samp),))).clip(lower=0.0)
        samp['target_meteor_flux_1e15'] = (samp['target_meteor_flux_1e15'] * (1.0 + _np.random.normal(scale=0.03, size=(len(samp),)))).clip(lower=0.0)
        samp['target_dust_g_cm3'] = (samp['target_dust_g_cm3'] * (1.0 + _np.random.normal(scale=0.03, size=(len(samp),)))).clip(lower=0.001)

        rows.append(samp)

    combined = pd.concat(rows, ignore_index=True, sort=False)

    combined = combined.iloc[:target_rows].reset_index(drop=True)

    for col in TRAINING_COLUMNS:
        if col not in combined.columns:
            combined[col] = SAMPLE_ROW[col]
    combined = combined[TRAINING_COLUMNS]
    return combined

def split_dataset(
    X: "pd.DataFrame | Any",
    Y: "pd.DataFrame | Any",
    val_frac: float = 0.15,
    test_frac: float = 0.15,
    chronological: bool = True,
    seed: int = 42
) -> Dict[str, Any]:
    """Split feature/target arrays into train/val/test partitions."""
    import numpy as _np

    if val_frac < 0 or test_frac < 0 or (val_frac + test_frac) >= 1.0:
        raise ValueError('val_frac and test_frac must be >= 0 and sum to < 1.0')

    X_arr = X.values if hasattr(X, 'values') else _np.asarray(X)
    Y_arr = Y.values if hasattr(Y, 'values') else _np.asarray(Y)
    n = len(X_arr)
    if n == 0:
        raise ValueError('Cannot split an empty dataset.')

    n_test = int(round(n * test_frac))
    n_val = int(round(n * val_frac))
    n_train = n - n_val - n_test
    if n_train < 1:
        raise ValueError(
            f'val_frac/test_frac leave no rows for training (n={n}, '
            f'n_train={n_train}, n_val={n_val}, n_test={n_test}).'
        )

    if chronological:
        idx = _np.arange(n)
    else:
        rng = _np.random.RandomState(seed)
        idx = rng.permutation(n)

    train_idx = idx[:n_train]
    val_idx = idx[n_train:n_train + n_val]
    test_idx = idx[n_train + n_val:]

    return {
        'X_train': X_arr[train_idx], 'Y_train': Y_arr[train_idx], 'train_idx': train_idx,
        'X_val': X_arr[val_idx], 'Y_val': Y_arr[val_idx], 'val_idx': val_idx,
        'X_test': X_arr[test_idx], 'Y_test': Y_arr[test_idx], 'test_idx': test_idx,
    }

def split_extended_dataset(
    df: pd.DataFrame,
    val_frac: float = 0.15,
    test_frac: float = 0.15,
    chronological: bool = True,
    seed: int = 42,
) -> Dict[str, Any]:
    """Split an extended schema dataframe (with `date` and `site` columns,"""
    import numpy as np

    if val_frac < 0 or test_frac < 0 or (val_frac + test_frac) >= 1.0:
        raise ValueError('val_frac and test_frac must be >= 0 and sum to < 1.0')
    if 'site' not in df.columns or 'date' not in df.columns:
        raise ValueError('split_extended_dataset requires `site` and `date` columns')

    df = df.sort_values(['site', 'date']).reset_index(drop=True)
    train_parts, val_parts, test_parts = [], [], []
    rng = np.random.RandomState(seed)

    for site, group in df.groupby('site', sort=False):
        n = len(group)
        n_test = int(round(n * test_frac))
        n_val = int(round(n * val_frac))
        n_train = n - n_val - n_test
        if n_train < 1:
            continue
        if chronological:
            idx = np.arange(n)
        else:
            idx = rng.permutation(n)
        g = group.reset_index(drop=True)
        train_parts.append(g.iloc[idx[:n_train]])
        val_parts.append(g.iloc[idx[n_train:n_train + n_val]])
        test_parts.append(g.iloc[idx[n_train + n_val:]])

    train_df = pd.concat(train_parts, ignore_index=True) if train_parts else df.iloc[0:0]
    val_df = pd.concat(val_parts, ignore_index=True) if val_parts else df.iloc[0:0]
    test_df = pd.concat(test_parts, ignore_index=True) if test_parts else df.iloc[0:0]

    def _xy(d):
        return d[EXTENDED_INPUT_COLUMNS].astype(float).values, d[TARGET_COLUMNS].astype(float).values

    X_train, Y_train = _xy(train_df)
    X_val, Y_val = _xy(val_df)
    X_test, Y_test = _xy(test_df)

    return {
        'X_train': X_train, 'Y_train': Y_train, 'groups_train': train_df['site'].values, 'dates_train': train_df['date'].values,
        'X_val': X_val, 'Y_val': Y_val, 'groups_val': val_df['site'].values, 'dates_val': val_df['date'].values,
        'X_test': X_test, 'Y_test': Y_test, 'groups_test': test_df['site'].values, 'dates_test': test_df['date'].values,
    }

if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='L.I.P.A.S. training data ingestion helper')
    parser.add_argument('--write-schema', type=str, help='Write a sample training CSV schema to this path')
    parser.add_argument('--show-schema', action='store_true', help='Print the training CSV schema columns')
    args = parser.parse_args()

    if args.show_schema:
        print(json.dumps({'columns': TRAINING_COLUMNS, 'sample': SAMPLE_ROW}, indent=2))
    if args.write_schema:
        write_schema_csv(args.write_schema)
        print(f'Wrote schema CSV to {args.write_schema}')
