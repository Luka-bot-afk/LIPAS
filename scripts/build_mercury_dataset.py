"""Build a Mercury LSTM training CSV from the train2 OMNI spine + Mercury labels.

X is day t (1 AU OMNI + same-day Mercury physics). Y is day t+1, matching lunar
train2 (next-day forecast). Same-day Y would make persistence RMSE ~0.

Does not copy lunar temperature / radiation / quake / dust / meteor labels.
"""
from __future__ import annotations

import argparse
import sys
from datetime import timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from mercurius.mercury_lstm import attach_next_day_targets, persistence_rmse
from mercurius.mercury_physics import physics_estimate_mercury, local_solar_time_mercury
from mercurius.mercury_sites import PHYSICS_SITES, require_site

OUT_DIR = ROOT / 'data' / 'ingested_mercury'
DEFAULT_SRC = ROOT / 'data' / 'ingested_extended' / 'extended_training_window_B_ready.csv'

def _load_heliosphere(src: Path, date_stride: int) -> pd.DataFrame:
    cols = [
        'date', 'solar_activity', 'solar_wind_speed', 'solar_wind_density',
        'imf_bz', 'kp_index', 'hour_of_day',
    ]
    df = pd.read_csv(src, usecols=lambda c: c in cols)
    df = df.dropna(subset=['date', 'solar_wind_speed', 'kp_index', 'imf_bz'])
    df['date'] = pd.to_datetime(df['date'], errors='coerce')
    df = df.dropna(subset=['date'])
    df['day'] = df['date'].dt.strftime('%Y-%m-%d')
    spine = df.sort_values('date').drop_duplicates('day', keep='last').copy()
    return spine.iloc[::max(1, int(date_stride))].reset_index(drop=True)

def build_frame(src: Path, site_ids: list[str], date_stride: int, horizon: int = 1) -> pd.DataFrame:
    spine = _load_heliosphere(src, date_stride)
    rows = []
    n = len(spine) * len(site_ids)
    done = 0
    for site_id in site_ids:
        site = require_site(site_id)
        for rec in spine.itertuples(index=False):
            when = rec.date.to_pydatetime()
            if when.tzinfo is None:
                when = when.replace(tzinfo=timezone.utc)
            extra = {
                'kp_index': float(rec.kp_index),
                'imf_bz': float(rec.imf_bz),
                'solar_wind_speed': float(rec.solar_wind_speed),
                'solar_wind_density': float(rec.solar_wind_density),
                'terrain': site.terrain,
                'albedo': site.albedo,
                'day_of_year': int(when.strftime('%j')),
            }
            lst = local_solar_time_mercury(site.lon, when)
            phys = physics_estimate_mercury(
                [float(rec.solar_activity), 0.06],
                lat=site.lat, lon=site.lon, local_time=lst,
                extra=extra, when=when,
            )
            sw = phys['wind_mercury']
            rows.append({
                'date': when.strftime('%Y-%m-%d'),
                'site': site.id,
                'solar_activity': phys['solar'],
                'radiation_mSv': phys['radiation'],
                'temperature_C': phys['temperature'],
                'moonquakes_per_day': phys['magnetopause_rm'],
                'meteor_flux_1e15': phys['p_dyn_npa'],
                'dust_g_cm3': sw['imf_b_mag'],
                'lat': site.lat,
                'lon': site.lon,
                'local_solar_time': lst,
                'hour_of_day': float(getattr(rec, 'hour_of_day', lst) or lst),
                'day_of_month': float(when.day),
                'month_of_year': float(when.month),
                'solar_wind_speed': float(rec.solar_wind_speed),
                'solar_wind_density': float(rec.solar_wind_density),
                'imf_bz': float(rec.imf_bz),
                'kp_index': float(rec.kp_index),
                'regolith_depth': phys['r_au'],
                'thermal_inertia': site.albedo * 100.0,
                'target_solar_activity': phys['solar'],
                'target_radiation_mSv': phys['radiation'],
                'target_temperature_C': phys['temperature'],
                'target_moonquakes_per_day': phys['magnetopause_rm'],
                'target_meteor_flux_1e15': phys['p_dyn_npa'],
                'target_dust_g_cm3': sw['imf_b_mag'],
            })
            done += 1
            if done % 20000 == 0:
                print(f'  labeled {done}/{n}', flush=True)
    df = attach_next_day_targets(pd.DataFrame(rows), horizon=horizon)
    return df

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('--src', default=str(DEFAULT_SRC))
    ap.add_argument('--sites', default=','.join(s.id for s in PHYSICS_SITES))
    ap.add_argument('--date-stride', type=int, default=1)
    ap.add_argument('--horizon', type=int, default=1, help='Target shift in days (train2 uses 1)')
    ap.add_argument('--out', default=str(OUT_DIR / 'mercury_training.csv'))
    args = ap.parse_args()
    if args.horizon < 1:
        raise SystemExit('horizon must be >= 1; same-day targets make the LSTM an identity copy of physics')
    site_ids = [s.strip() for s in args.sites.split(',') if s.strip()]
    for sid in site_ids:
        require_site(sid)
    print(
        f'Building Mercury LSTM CSV from {args.src} sites={site_ids} '
        f'stride={args.date_stride} horizon={args.horizon}d'
    )
    df = build_frame(Path(args.src), site_ids, args.date_stride, horizon=args.horizon)
    pers = persistence_rmse(df)
    if pers < 1e-3:
        raise SystemExit(f'Persistence RMSE {pers:.3e} is ~0 — targets still leak same-day X.')
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out, index=False)
    print(f'Wrote {len(df)} rows -> {out}')
    print(f'Next-day persistence RMSE (X_t vs Y_t+{args.horizon}): {pers:.4f}')
    print(df[['solar_activity', 'radiation_mSv', 'temperature_C', 'moonquakes_per_day']].describe().to_string())

if __name__ == '__main__':
    main()
