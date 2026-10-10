"""LIPAS."""
from __future__ import annotations

import numpy as np
import pandas as pd

from lunar_physics import clamp

def kp_from_ap(ap: float) -> float:
    """Bartels-style Ap→Kp proxy (piecewise, deterministic)."""
    a = float(max(0.0, ap))
    table = [
        (0, 0.0), (2, 0.33), (3, 0.67), (4, 1.0), (5, 1.33), (6, 1.67),
        (7, 2.0), (9, 2.33), (12, 2.67), (15, 3.0), (18, 3.33), (22, 3.67),
        (27, 4.0), (32, 4.33), (39, 4.67), (48, 5.0), (56, 5.33), (67, 5.67),
        (80, 6.0), (94, 6.33), (111, 6.67), (132, 7.0), (154, 7.33),
        (179, 7.67), (207, 8.0), (236, 8.33), (300, 8.67), (400, 9.0),
    ]
    if a <= 0:
        return 0.0
    for i in range(1, len(table)):
        a0, k0 = table[i - 1]
        a1, k1 = table[i]
        if a <= a1:
            t = (a - a0) / max(a1 - a0, 1e-6)
            return float(k0 + t * (k1 - k0))
    return 9.0

def ap_from_kp(kp: float) -> float:
    """Kp→Ap proxy (midpoint of NOAA bins)."""
    k = float(clamp(kp, 0.0, 9.0, 3.0))
    bins = [0, 2, 3, 4, 5, 6, 7, 9, 12, 15, 18, 22, 27, 32, 39, 48, 56, 67, 80, 94, 111, 132, 154, 179, 207, 236, 300, 400]
    idx = int(round(k * 3.0))
    idx = max(0, min(len(bins) - 1, idx))
    return float(bins[idx])

def f107_from_ssn(ssn: float) -> float:
    """Empirical F10.7 from sunspot number (quiet≈70)."""
    s = float(max(0.0, ssn))
    return float(clamp(67.0 + 0.55 * s + 0.0012 * s * s, 60.0, 400.0, 70.0))

def ssn_from_f107(f107: float) -> float:
    """Rough inverse of f107_from_ssn for blending."""
    f = float(max(60.0, f107))
    return float(clamp((f - 67.0) / 0.55, 0.0, 400.0, 0.0))

def interpolate_numeric_columns(df: pd.DataFrame, cols: list[str], limit: int = 5) -> pd.DataFrame:
    """Time-ordered linear interpolation with short forward/back fill (drivers only)."""
    out = df.copy()
    if 'date' in out.columns:
        out = out.sort_values('date')
    for col in cols:
        if col not in out.columns:
            continue
        s = pd.to_numeric(out[col], errors='coerce')
        s = s.interpolate(method='linear', limit=limit, limit_direction='both')
        s = s.ffill(limit=limit).bfill(limit=limit)
        out[col] = s
    return out

def cross_fill_omni_drivers(df: pd.DataFrame) -> pd.DataFrame:
\
\
\

    out = df.copy()
    if 'kp_index' in out.columns and 'ap' in out.columns:
        miss_kp = out['kp_index'].isna()
        if miss_kp.any():
            out.loc[miss_kp, 'kp_index'] = out.loc[miss_kp, 'ap'].apply(
                lambda x: kp_from_ap(x) if pd.notna(x) else np.nan
            )
        miss_ap = out['ap'].isna()
        if miss_ap.any():
            out.loc[miss_ap, 'ap'] = out.loc[miss_ap, 'kp_index'].apply(
                lambda x: ap_from_kp(x) if pd.notna(x) else np.nan
            )
    if 'f107' in out.columns and 'ssn' in out.columns:
        miss_f = out['f107'].isna()
        if miss_f.any():
            out.loc[miss_f, 'f107'] = out.loc[miss_f, 'ssn'].apply(
                lambda x: f107_from_ssn(x) if pd.notna(x) else np.nan
            )
        miss_s = out['ssn'].isna()
        if miss_s.any():
            out.loc[miss_s, 'ssn'] = out.loc[miss_s, 'f107'].apply(
                lambda x: ssn_from_f107(x) if pd.notna(x) else np.nan
            )
    defaults = {
        'solar_wind_speed': 400.0,
        'solar_wind_density': 5.0,
        'imf_bz': -2.0,
        'kp_index': 2.0,
        'f107': 70.0,
        'dst': -10.0,
        'ap': 6.0,
    }
    for col, val in defaults.items():
        if col in out.columns:
            out[col] = pd.to_numeric(out[col], errors='coerce').fillna(val)
    return out

def expand_base_to_omni_spine(base: pd.DataFrame, omni: pd.DataFrame, max_gap_days: int = 3) -> pd.DataFrame:
\
\
\
\

    _ = (omni, max_gap_days)
    return base

_DRIVER_INPUT_COLS = (
    'solar_wind_speed', 'solar_wind_density', 'imf_bz', 'kp_index',
)

_SITE_CONST_COLS = (
    'regolith_depth', 'thermal_inertia', 'lat', 'lon',
)

_REQUIRED_TRAINING_COLS = [
    'solar_activity', 'radiation_mSv', 'temperature_C', 'moonquakes_per_day',
    'meteor_flux_1e15', 'dust_g_cm3',
    'lat', 'lon', 'local_solar_time', 'hour_of_day', 'day_of_month', 'month_of_year',
    'solar_wind_speed', 'solar_wind_density', 'imf_bz', 'kp_index',
    'regolith_depth', 'thermal_inertia',
    'target_solar_activity', 'target_radiation_mSv', 'target_temperature_C',
    'target_moonquakes_per_day', 'target_meteor_flux_1e15', 'target_dust_g_cm3',
]

def gap_fill_extended_training(df: pd.DataFrame) -> pd.DataFrame:

    out = df.copy()
    out = out.sort_values(['site', 'date']).reset_index(drop=True)

    chunks = []
    for _site, g in out.groupby('site', sort=False):
        g2 = interpolate_numeric_columns(
            g, [c for c in _DRIVER_INPUT_COLS if c in g.columns], limit=5,
        )
        chunks.append(g2)
    out = pd.concat(chunks, ignore_index=True)

    for col in _SITE_CONST_COLS:
        if col in out.columns:
            out[col] = out.groupby('site')[col].transform(lambda s: s.ffill().bfill())

    if 'date' in out.columns:
        dts = pd.to_datetime(out['date'], errors='coerce')
        if 'day_of_month' in out.columns:
            out['day_of_month'] = out['day_of_month'].fillna(dts.dt.day.astype(float))
        if 'month_of_year' in out.columns:
            out['month_of_year'] = out['month_of_year'].fillna(dts.dt.month.astype(float))

    before = len(out)
    need = [c for c in _REQUIRED_TRAINING_COLS if c in out.columns]
    out = out.dropna(subset=need, axis=0, how='any')
    dropped = before - len(out)
    if dropped:
        print(f'  gap_fill: dropped {dropped} incomplete rows (no fake target synthesis)')
    return out.sort_values(['site', 'date']).reset_index(drop=True)
