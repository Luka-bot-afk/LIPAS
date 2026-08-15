
"""LIPAS."""
import argparse
import os
import time
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd
import requests

ROOT = Path(__file__).parent.parent
CACHE_DIR = ROOT / 'data' / 'archives' / 'omni2'
BASE_URL = 'https://spdf.gsfc.nasa.gov/pub/data/omni/low_res_omni/omni2_{year}.dat'

COL_NAMES = [
    'year', 'doy', 'hour', 'bartels', 'imf_id', 'plasma_id', 'n_imf_pts', 'n_plasma_pts',
    'field_mag_avg', 'field_vec_mag', 'lat_angle', 'long_angle',
    'bx_gse', 'by_gse', 'bz_gse', 'by_gsm', 'bz_gsm',
    'sigma_field', 'sigma_b', 'sigma_bx', 'sigma_by', 'sigma_bz',
    'proton_temp', 'proton_density', 'plasma_speed', 'flow_long', 'flow_lat',
    'na_np', 'flow_pressure', 'sigma_t', 'sigma_n', 'sigma_v', 'sigma_phi', 'sigma_theta', 'sigma_na_np',
    'efield', 'plasma_beta', 'alfven_mach',
    'kp_code', 'sunspot_r', 'dst', 'ae',
    'proton_flux_gt1', 'proton_flux_gt2', 'proton_flux_gt4', 'proton_flux_gt10', 'proton_flux_gt30', 'proton_flux_gt60',
    'flag', 'ap', 'f107', 'pc_index', 'al', 'au', 'magnetosonic_mach',
]
assert len(COL_NAMES) == 55

FILL_VALUES = {
    'bz_gsm': 999.9, 'plasma_speed': 9999.0, 'proton_density': 999.9,
    'kp_code': 99, 'dst': 99999, 'ap': 999, 'f107': 999.9,
}

_KP_CODES = [0, 3, 7, 10, 13, 17, 20, 23, 27, 30, 33, 37, 40, 43, 47,
             50, 53, 57, 60, 63, 67, 70, 73, 77, 80, 83, 87, 90]
_KP_CODE_TO_VALUE = {code: i / 3.0 for i, code in enumerate(_KP_CODES)}

def decode_kp(code) -> Optional[float]:
    try:
        code = int(round(float(code)))
    except Exception:
        return None
    return _KP_CODE_TO_VALUE.get(code)

def download_year(year: int, force: bool = False, timeout: int = 30) -> Optional[Path]:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    dest = CACHE_DIR / f'omni2_{year}.dat'
    if dest.exists() and not force and dest.stat().st_size > 0:
        return dest
    url = BASE_URL.format(year=year)
    try:
        r = requests.get(url, timeout=timeout)
        r.raise_for_status()
        if not r.text.strip():
            return None
        dest.write_text(r.text)
        return dest
    except Exception as e:
        print(f'  WARNING: failed to fetch OMNI2 {year}: {e}')
        return None

def parse_omni2_file(path: Path) -> pd.DataFrame:
    rows = []
    with path.open() as f:
        for line in f:
            parts = line.split()
            if len(parts) != 55:
                continue
            rows.append(parts)
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows, columns=COL_NAMES)
    for c in ['year', 'doy', 'hour', 'bz_gsm', 'plasma_speed', 'proton_density', 'kp_code', 'dst', 'ap', 'f107']:
        df[c] = pd.to_numeric(df[c], errors='coerce')

    for col, fill in FILL_VALUES.items():
        df.loc[np.isclose(df[col], fill, atol=0.05), col] = np.nan

    df['kp_index'] = df['kp_code'].apply(decode_kp)
    df['date'] = pd.to_datetime(df['year'].astype(int).astype(str), format='%Y') + \
        pd.to_timedelta(df['doy'].astype(int) - 1, unit='D')
    df['date'] = df['date'].dt.date.astype(str)
    return df[['date', 'hour', 'plasma_speed', 'proton_density', 'bz_gsm', 'kp_index', 'dst', 'ap', 'f107']].rename(
        columns={'plasma_speed': 'solar_wind_speed', 'proton_density': 'solar_wind_density', 'bz_gsm': 'imf_bz'}
    )

def build_daily_omni2(start_year: int = 1969, end_year: int = 2026, force: bool = False) -> pd.DataFrame:
    """Download (if needed) and parse every requested year, returning one"""
    frames = []
    for year in range(start_year, end_year + 1):
        path = download_year(year, force=force)
        if path is None:
            continue
        df = parse_omni2_file(path)
        if df.empty:
            continue
        frames.append(df)
        print(f'  OMNI2 {year}: {len(df)} real hourly rows parsed')
    if not frames:
        return pd.DataFrame(columns=['date', 'solar_wind_speed', 'solar_wind_density', 'imf_bz', 'kp_index', 'dst', 'ap', 'f107'])

    hourly = pd.concat(frames, ignore_index=True)
    daily = hourly.groupby('date', as_index=False).agg({
        'solar_wind_speed': 'mean',
        'solar_wind_density': 'mean',
        'imf_bz': 'mean',
        'kp_index': 'mean',
        'dst': 'mean',
        'ap': 'mean',
        'f107': 'mean',
    })
    return daily

def main():
    parser = argparse.ArgumentParser(description='Fetch & parse real NASA OMNI2 solar wind/IMF/Kp/Dst data.')
    parser.add_argument('--start-year', type=int, default=1969)
    parser.add_argument('--end-year', type=int, default=2026)
    parser.add_argument('--force', action='store_true', help='Re-download even if cached')
    parser.add_argument('--out', type=str, default=str(ROOT / 'data' / 'archives' / 'omni2_daily.csv'))
    args = parser.parse_args()

    print(f'Fetching real OMNI2 data for {args.start_year}-{args.end_year} from NASA SPDF...')
    daily = build_daily_omni2(args.start_year, args.end_year, force=args.force)
    print(f'\nParsed {len(daily)} real days of OMNI2 solar wind/IMF/Kp/Dst data '
          f'({daily["date"].min() if len(daily) else "n/a"} to {daily["date"].max() if len(daily) else "n/a"})')
    for col in ['solar_wind_speed', 'solar_wind_density', 'imf_bz', 'kp_index', 'dst', 'ap', 'f107']:
        n_real = daily[col].notna().sum()
        print(f'  {col:20s}: {n_real} real (non-missing) days, '
              f'mean={daily[col].mean():.3f}' if n_real else f'  {col:20s}: 0 real days')

    daily.to_csv(args.out, index=False)
    print(f'\nSaved daily-aggregated real OMNI2 data to {args.out}')

if __name__ == '__main__':
    main()
