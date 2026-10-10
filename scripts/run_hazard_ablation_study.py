#!/usr/bin/env python3


from __future__ import annotations

import argparse
import json
import os
import sys
from itertools import combinations
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

from space_weather_model import (  # noqa: E402
    CORE_FEATURE_NAMES,
    load_saved_model,
    load_blend_weights,
    refine_prediction,
)
from scripts.run_14day_flagship_study import (  # noqa: E402
    SITES,
    build_site_rows,
    row_to_inputs,
)

HAZARD_IDX = {name: i for i, name in enumerate(CORE_FEATURE_NAMES)}
# Short labels for tables
SHORT = {
    'solar_activity': 'solar',
    'radiation_mSv': 'radiation',
    'temperature_C': 'temperature',
    'moonquakes_per_day': 'moonquakes',
    'meteor_flux_1e15': 'micrometeorites',
    'dust_g_cm3': 'dust',
}


def _rmse(pred, truth):
    a = np.asarray(pred, float)
    b = np.asarray(truth, float)
    m = np.isfinite(a) & np.isfinite(b)
    if m.sum() == 0:
        return float('nan')
    return float(np.sqrt(np.mean((a[m] - b[m]) ** 2)))


def ablate_inputs(inputs, remove_names, fill_values):
    out = list(inputs)
    for name in remove_names:
        out[HAZARD_IDX[name]] = float(fill_values[name])
    return out


def predict_hybrid(row, inputs, day_of_year):
    extra = {
        'kp': float(row['kp_index']),
        'kp_index': float(row['kp_index']),
        'imf_bz': float(row['imf_bz']),
        'solar_wind_speed': float(row['solar_wind_speed']),
        'solar_wind_density': float(row['solar_wind_density']),
        'day_of_year': int(day_of_year),
        'date': str(pd.Timestamp(row['date']).date()),
    }
    out = refine_prediction(
        inputs,
        lat=float(row['lat']),
        lon=float(row['lon']),
        local_time=float(row['local_solar_time']),
        extra=extra,
        day_of_year=int(day_of_year),
    )
    hyb = out.get('hybrid') or {}
    return float(hyb['solar']), float(hyb['radiation'])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--csv', default='data/ingested_extended/extended_training_window_B_ready.csv')
    ap.add_argument('--model-dir', default='saved_model')
    ap.add_argument('--start', default='2026-07-05')
    ap.add_argument('--end', default='2026-07-18')
    ap.add_argument('--out-dir', default='logs/study_ablation_window_A')
    args = ap.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    print('Loading model...', flush=True)
    if load_saved_model(args.model_dir, set_global=True) is None:
        raise SystemExit(f'No model in {args.model_dir}')
    load_blend_weights(args.model_dir)

    df = pd.read_csv(args.csv, parse_dates=['date'])
    start, end = pd.Timestamp(args.start), pd.Timestamp(args.end)

    rows = []
    for site in SITES:
        sub = build_site_rows(df, site, start, end)
        for _, row in sub.iterrows():
            rows.append(row)
    if not rows:
        raise SystemExit('No study rows')

    # Fill values = mean of that hazard over the Window A rows (neutral climatology)
    fill_values = {}
    for name in CORE_FEATURE_NAMES:
        fill_values[name] = float(np.mean([float(r[name]) for r in rows]))

    truth_solar = [float(r['target_solar_activity']) for r in rows]
    truth_rad = [float(r['target_radiation_mSv']) for r in rows]

    # Configs: full, one-away, two-away
    others = list(CORE_FEATURE_NAMES)
    configs = [('full model (all hazards)', [])]
    for name in others:
        configs.append((f'remove {SHORT[name]}', [name]))

    # Two-away: all pairs (15) is fine; keep for analysis then pick top hurts for paper tables
    for a, b in combinations(others, 2):
        configs.append((f'remove {SHORT[a]} + {SHORT[b]}', [a, b]))

    results = []
    for label, remove in configs:
        pred_s, pred_r = [], []
        for r in rows:
            doy = int(pd.Timestamp(r['date']).dayofyear)
            base = row_to_inputs(r)
            inputs = ablate_inputs(base, remove, fill_values)
            s, rad = predict_hybrid(r, inputs, doy)
            pred_s.append(s)
            pred_r.append(rad)
        rs = _rmse(pred_s, truth_solar)
        rr = _rmse(pred_r, truth_rad)
        results.append({
            'config': label,
            'removed': ','.join(SHORT[x] for x in remove) if remove else '(none)',
            'n_removed': len(remove),
            'solar_rmse': rs,
            'radiation_rmse': rr,
        })
        print(f'OK {label}: solar={rs:.4f} rad={rr:.4f}', flush=True)

    res = pd.DataFrame(results)
    base_s = float(res.loc[res.n_removed == 0, 'solar_rmse'].iloc[0])
    base_r = float(res.loc[res.n_removed == 0, 'radiation_rmse'].iloc[0])
    res['solar_rmse_increase'] = res['solar_rmse'] - base_s
    res['radiation_rmse_increase'] = res['radiation_rmse'] - base_r
    res['solar_pct_worse'] = np.where(
        base_s > 0, 100.0 * res['solar_rmse_increase'] / base_s, np.nan)
    res['radiation_pct_worse'] = np.where(
        base_r > 0, 100.0 * res['radiation_rmse_increase'] / base_r, np.nan)

    res.to_csv(out_dir / 'ablation_full_results.csv', index=False)

    # Paper tables: focus one-away + top two-away for each target
    one = res[res.n_removed == 1].copy()
    two = res[res.n_removed == 2].copy()

    # Table radiation: full + one-away sorted by how much radiation got worse + top 3 two-away
    rad_one = one.sort_values('radiation_rmse_increase', ascending=False)
    rad_two = two.sort_values('radiation_rmse_increase', ascending=False).head(5)
    rad_table = pd.concat([
        res[res.n_removed == 0],
        rad_one,
        rad_two,
    ], ignore_index=True)
    rad_table.to_csv(out_dir / 'table_radiation_ablation.csv', index=False)

    sol_one = one.sort_values('solar_rmse_increase', ascending=False)
    sol_two = two.sort_values('solar_rmse_increase', ascending=False).head(5)
    sol_table = pd.concat([
        res[res.n_removed == 0],
        sol_one,
        sol_two,
    ], ignore_index=True)
    sol_table.to_csv(out_dir / 'table_solar_ablation.csv', index=False)

    summary = {
        'window': {'start': str(start.date()), 'end': str(end.date())},
        'sites': SITES,
        'n_site_days': len(rows),
        'fill': 'Window A mean of each hazard channel',
        'baseline_solar_rmse': base_s,
        'baseline_radiation_rmse': base_r,
        'worst_one_away_for_radiation': rad_one.iloc[0].to_dict() if len(rad_one) else None,
        'worst_one_away_for_solar': sol_one.iloc[0].to_dict() if len(sol_one) else None,
        'note': (
            'Ablation mean-fills removed hazard inputs before refine_prediction. '
            'Higher RMSE = worse. Cross-hazard value = how much target skill drops.'
        ),
    }
    (out_dir / 'summary.json').write_text(json.dumps(summary, indent=2), encoding='utf-8')
    print(json.dumps(summary, indent=2), flush=True)


if __name__ == '__main__':
    main()
