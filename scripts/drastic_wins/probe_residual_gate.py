#!/usr/bin/env python3
"""R6 last-shot: residual ridge/GBM gate on y−physics for solar/rad/temp.

Abort Metal/LSTM residual retrain if held-out skill is weak (solar already failed
cheap_checks; T4b RMSE 44 killed). Emit residual_correct bias tables only when
skill clears the gate — Mac wave applies them hybrid-only and aborts on window regress.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.linear_model import Ridge
from sklearn.model_selection import train_test_split

ROOT = Path(__file__).resolve().parents[2]
FEATURE_COLS = [
    'solar_activity', 'radiation_mSv', 'temperature_C', 'moonquakes_per_day',
    'meteor_flux_1e15', 'dust_g_cm3', 'lat', 'lon', 'local_solar_time',
    'hour_of_day', 'day_of_month', 'month_of_year', 'solar_wind_speed',
    'solar_wind_density', 'imf_bz', 'kp_index', 'regolith_depth', 'thermal_inertia',
]
TARGET_COLS = [
    'target_solar_activity', 'target_radiation_mSv', 'target_temperature_C',
]
PHYS_COLS = ['solar_activity', 'radiation_mSv', 'temperature_C']
SKILL_GATE = 0.02
CORR_CIRCULAR = 0.98


def _skill(y_true, y_pred, y_zero_rmse):
    rmse = float(np.sqrt(np.mean((y_pred - y_true) ** 2)))
    skill = 1.0 - (rmse / y_zero_rmse) if y_zero_rmse > 1e-9 else 0.0
    return rmse, skill


def main():
    csv_path = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / (
        'data/ingested_extended/train7_training_locked_y_ext_drivers.csv'
    )
    out_dir = Path(sys.argv[2]) if len(sys.argv) > 2 else ROOT / (
        'studies/drastic_wins/r6_residual_gate'
    )
    out_dir.mkdir(parents=True, exist_ok=True)
    df = pd.read_csv(csv_path)
    missing = [c for c in FEATURE_COLS + TARGET_COLS if c not in df.columns]
    if missing:
        raise SystemExit(f'missing cols: {missing}')

    n = min(len(df), 100_000)
    sub = df.sample(n=n, random_state=42) if len(df) > n else df
    X = sub[FEATURE_COLS].to_numpy(dtype=np.float64)
    report = {
        'n_rows_used': int(n),
        'channels': {},
        'abort_metal_retrain': True,  # T4b already failed; default abort
        'allow_residual_correct': {},
        'residual_correct_prior': {'enabled': False},
    }
    prior = {'enabled': False}

    for i, name in enumerate(TARGET_COLS):
        y = sub[name].to_numpy(dtype=np.float64)
        phys = sub[PHYS_COLS[i]].to_numpy(dtype=np.float64)
        resid = y - phys
        corr = float(np.corrcoef(y, phys)[0, 1]) if np.std(y) > 0 and np.std(phys) > 0 else 0.0
        Xtr, Xte, rtr, rte, lst_tr, lst_te = train_test_split(
            X, resid, sub['local_solar_time'].to_numpy(dtype=np.float64),
            test_size=0.2, random_state=42,
        )
        zero = float(np.sqrt(np.mean(rte ** 2)))
        ridge = Ridge(alpha=1.0)
        ridge.fit(Xtr, rtr)
        r_pred = ridge.predict(Xte)
        r_rmse, r_skill = _skill(rte, r_pred, zero)
        gbm = HistGradientBoostingRegressor(
            max_depth=3, learning_rate=0.08, max_iter=80, random_state=42,
        )
        gbm.fit(Xtr, rtr)
        g_pred = gbm.predict(Xte)
        g_rmse, g_skill = _skill(rte, g_pred, zero)
        best_skill = max(r_skill, g_skill)
        has_skill = bool(best_skill > SKILL_GATE and corr < CORR_CIRCULAR)
        # Bias table: mean residual by LST bin on train (serve-safe)
        bins = [(0, 6), (6, 12), (12, 18), (18, 24)]
        lst_bins = []
        for lo, hi in bins:
            m = (lst_tr >= lo) & (lst_tr < hi)
            add = float(np.mean(rtr[m])) if m.any() else 0.0
            # shrink toward 0 — only keep mild bias
            add = float(np.clip(add * 0.35, -3.0 if i == 2 else -0.02, 3.0 if i == 2 else 0.02))
            lst_bins.append({'start': lo, 'end': hi, 'add': add})
        global_add = float(np.clip(np.mean(rtr) * 0.25, -2.0 if i == 2 else -0.015, 2.0 if i == 2 else 0.015))
        ch = {
            'corr_label_vs_physics_x': corr,
            'ridge_skill': r_skill,
            'ridge_rmse': r_rmse,
            'gbm_skill': g_skill,
            'gbm_rmse': g_rmse,
            'physics_residual_rmse': zero,
            'circular_risk': bool(corr > CORR_CIRCULAR),
            'residual_has_skill': has_skill,
            'proposed_global_add': global_add,
            'proposed_lst_bins': lst_bins,
        }
        report['channels'][name] = ch
        key = ['solar', 'radiation', 'temperature'][i]
        # Solar failed cheap gate historically — only allow if skill clears AND not circular
        allow = has_skill and (key != 'solar' or r_skill > 0.03)
        report['allow_residual_correct'][key] = allow
        print(
            f'gate {name}: ridge={r_skill:.3f} gbm={g_skill:.3f} '
            f'corr={corr:.3f} allow={allow}'
        )
        if allow:
            prior.setdefault(key, {})
            prior[key] = {'add': global_add, 'lst_bins': lst_bins}
            prior['enabled'] = True

    # Metal retrain still aborted: T4b held-out collapse; residual_correct is serve-only.
    report['abort_metal_retrain'] = True
    report['abort_reason'] = (
        'T4b residual LSTM held-out RMSE 44.0 vs train2 4.97; do not retrain. '
        'Serve residual_correct only if allow_* and window does not regress.'
    )
    report['residual_correct_prior'] = prior
    (out_dir / 'residual_gate.json').write_text(json.dumps(report, indent=2))
    (out_dir / 'residual_correct_prior.json').write_text(json.dumps(prior, indent=2))
    print('Wrote', out_dir / 'residual_gate.json')
    print('abort_metal_retrain', report['abort_metal_retrain'], 'prior_enabled', prior.get('enabled'))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
