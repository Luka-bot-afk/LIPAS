
"""LIPAS."""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np
import pandas as pd
from space_weather_model import (
    load_saved_model, make_sliding_windows_grouped, SEQUENCE_LENGTH,
    fit_calibration, save_calibration, apply_calibration,
    CORE_FEATURE_NAMES, NUM_CORE_FEATURES, physics_estimate,
)
from data_ingestion import split_extended_dataset, get_target_columns, EXTENDED_INPUT_COLUMNS

def _physics_anchor_matrix(X_raw: np.ndarray, dates: np.ndarray | None = None) -> np.ndarray:
    """Build Nx6 physics anchors from unscaled extended feature rows."""

    try:
        lat_i = EXTENDED_INPUT_COLUMNS.index('lat')
        lon_i = EXTENDED_INPUT_COLUMNS.index('lon')
        lst_i = EXTENDED_INPUT_COLUMNS.index('local_solar_time')
        month_i = EXTENDED_INPUT_COLUMNS.index('month_of_year')
        day_i = EXTENDED_INPUT_COLUMNS.index('day_of_month')
    except ValueError:
        lat_i, lon_i, lst_i, month_i, day_i = 6, 7, 8, 11, 10

    out = np.zeros((len(X_raw), NUM_CORE_FEATURES), dtype=np.float64)
    n = len(X_raw)
    for i in range(n):
        if i and i % 500 == 0:
            print(f'  physics anchors {i}/{n}', flush=True)
        row = X_raw[i]
        core = row[:6]
        lat = float(row[lat_i]) if X_raw.shape[1] > lat_i else 0.0
        lon = float(row[lon_i]) if X_raw.shape[1] > lon_i else 0.0
        lst = float(row[lst_i]) if X_raw.shape[1] > lst_i else 12.0
        doy = None
        if dates is not None and i < len(dates) and dates[i] is not None and str(dates[i]) not in ('', 'nan'):
            try:
                ts = pd.Timestamp(dates[i])
                doy = int(ts.dayofyear)
            except Exception:
                doy = None
        if doy is None and X_raw.shape[1] > month_i:

            m = max(1, min(12, int(round(float(row[month_i])))))
            d = max(1, min(28, int(round(float(row[day_i])))))
            doy = int(pd.Timestamp(year=2001, month=m, day=d).dayofyear)
        phys = physics_estimate(core, lat=lat, lon=lon, local_time=lst, day_of_year=doy)
        out[i] = [
            phys['solar'], phys['radiation'], phys['temperature'],
            phys['moonquakes'], phys['micrometeorites'], phys['dust'],
        ]
    return out

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--csv', type=str, required=True)
    ap.add_argument('--model-dir', type=str, default='saved_model')
    ap.add_argument('--sequence-length', type=int, default=SEQUENCE_LENGTH)
    ap.add_argument('--window-stride', type=int, default=7)
    ap.add_argument('--calibration-method', type=str, default='platt', choices=['platt', 'isotonic'])
    ap.add_argument('--max-windows', type=int, default=2000,
                    help='Subsample validation windows for blend/calibration (speeds CPU; 0 = all)')
    ap.add_argument('--dry-run', action='store_true')
    args = ap.parse_args()

    model_dir = Path(args.model_dir)
    model = load_saved_model(str(model_dir))
    if model is None:
        raise RuntimeError(f'No saved model in {args.model_dir}')
    scaler = np.load(model_dir / 'scaler.npz')
    mean, std = scaler['mean'], scaler['std']

    df = pd.read_csv(args.csv)
    split = split_extended_dataset(df, val_frac=0.15, test_frac=0.15, chronological=True)
    X_val = split['X_val'].astype(np.float32)
    Y_val = split['Y_val'].astype(np.float32)
    g_val = split['groups_val']
    if len(X_val) == 0:
        raise RuntimeError('empty validation split')
    Xs_val = (X_val - mean) / std

    is_temporal = len(model.input_shape) == 3
    if is_temporal:
        Xw_val, Yw_val = make_sliding_windows_grouped(
            Xs_val, Y_val, g_val,
            sequence_length=args.sequence_length, stride=args.window_stride,
        )

        physics_input_raw = Xw_val[:, -1, :] * std + mean

        dates = None
    else:
        Xw_val, Yw_val = Xs_val, Y_val
        physics_input_raw = X_val
        dates = None

    print(f'Validation windows: {len(Xw_val)}')
    if args.max_windows and len(Xw_val) > args.max_windows:
        rng = np.random.default_rng(42)
        idx = np.sort(rng.choice(len(Xw_val), size=args.max_windows, replace=False))
        Xw_val = Xw_val[idx]
        Yw_val = Yw_val[idx]
        physics_input_raw = physics_input_raw[idx]
        if dates is not None:
            dates = np.asarray(dates)[idx]
        print(f'Subsampled to {len(Xw_val)} windows for blend/calibration (--max-windows={args.max_windows})')
    print('Building true physics_estimate anchors (not persistence)...', flush=True)
    physics_anchors = _physics_anchor_matrix(physics_input_raw, dates=dates)
    print('Running model.predict on validation windows...', flush=True)
    raw_preds = model.predict(Xw_val, verbose=0)

    print('\n=== Scalar ML blend weight sweep vs physics_estimate (val) ===')
    weights = np.round(np.arange(0.0, 1.01, 0.05), 2)
    best_w, best_rmse = None, np.inf
    scalar_results = []
    for w in weights:
        hybrid = w * raw_preds + (1.0 - w) * physics_anchors
        rmse = float(np.sqrt(np.mean((hybrid - Yw_val) ** 2)))
        scalar_results.append({'ml_blend_weight': float(w), 'val_rmse': rmse})
        if rmse < best_rmse:
            best_rmse, best_w = rmse, float(w)
        marker = '  <-- best' if w == best_w else ''
        print(f'  w={w:.2f}  val_rmse={rmse:.4f}{marker}')
    print(f'\nBest scalar ML blend weight: {best_w} (val_rmse={best_rmse:.4f})')

    print('\n=== Per-channel ML blend weight sweep vs physics_estimate (val) ===')
    channel_weights = []
    channel_report = []
    cols = get_target_columns()
    for i in range(NUM_CORE_FEATURES):
        best_ci, best_c_rmse = best_w, np.inf
        for w in weights:
            hybrid_i = w * raw_preds[:, i] + (1.0 - w) * physics_anchors[:, i]
            rmse_i = float(np.sqrt(np.mean((hybrid_i - Yw_val[:, i]) ** 2)))
            if rmse_i < best_c_rmse:
                best_c_rmse, best_ci = rmse_i, float(w)
        channel_weights.append(best_ci)
        name = CORE_FEATURE_NAMES[i] if i < len(CORE_FEATURE_NAMES) else cols[i]
        channel_report.append({'channel': name, 'ml_blend_weight': best_ci, 'val_rmse': best_c_rmse})
        print(f'  {name}: w={best_ci:.2f}  val_rmse={best_c_rmse:.4f}')

    channel_weights = np.asarray(channel_weights, dtype=np.float64)
    hybrid_ch = channel_weights * raw_preds + (1.0 - channel_weights) * physics_anchors
    rmse_ch = float(np.sqrt(np.mean((hybrid_ch - Yw_val) ** 2)))
    print(f'\nPer-channel hybrid val_rmse={rmse_ch:.4f} (scalar best was {best_rmse:.4f})')

    print(f'\n=== Fitting {args.calibration_method} calibration on REAL validation predictions ===')
    calib = fit_calibration(raw_preds, Yw_val, method=args.calibration_method)
    calibrated = apply_calibration(raw_preds, calib)
    rmse_before = float(np.sqrt(np.mean((raw_preds - Yw_val) ** 2)))
    rmse_after = float(np.sqrt(np.mean((np.asarray(calibrated) - Yw_val) ** 2)))
    print(f'Raw model RMSE (val):        {rmse_before:.4f}')
    print(f'Calibrated model RMSE (val): {rmse_after:.4f}  ({"improved" if rmse_after < rmse_before else "no improvement"})')
    if calib.get('method') == 'platt':
        for i, c in enumerate(cols):
            print(f'  {c}: y_cal = {calib["A"][i]:.4f} * y_raw + {calib["B"][i]:.4f}')

    cal_arr = np.asarray(calibrated, dtype=np.float64)
    hybrid_cal = channel_weights * cal_arr + (1.0 - channel_weights) * physics_anchors
    rmse_cal_blend = float(np.sqrt(np.mean((hybrid_cal - Yw_val) ** 2)))
    print(f'Calibrated + per-channel blend val_rmse={rmse_cal_blend:.4f}')

    pers = physics_input_raw[:, :6] if physics_input_raw.ndim == 2 else physics_input_raw
    rmse_pers = float(np.sqrt(np.mean((pers[:, :6] - Yw_val) ** 2)))
    print(f'Persistence (last features) val_rmse={rmse_pers:.4f}')
    rmse_phys_only = float(np.sqrt(np.mean((physics_anchors - Yw_val) ** 2)))
    print(f'Physics-only val_rmse={rmse_phys_only:.4f}')

    out = {
        'model_dir': args.model_dir,
        'csv': args.csv,
        'anchor': 'physics_estimate',
        'blend_weight_sweep': scalar_results,
        'best_physics_weight': best_w,
        'best_ml_blend_weight': best_w,
        'best_val_rmse': best_rmse,
        'channel_blend_weights': channel_report,
        'blend_weights': channel_weights.tolist(),
        'per_channel_val_rmse': rmse_ch,
        'calibrated_per_channel_val_rmse': rmse_cal_blend,
        'physics_only_val_rmse': rmse_phys_only,
        'persistence_val_rmse': rmse_pers,
        'calibration_method': calib.get('method'),
        'val_rmse_raw': rmse_before,
        'val_rmse_calibrated': rmse_after,
    }

    if not args.dry_run:
        save_calibration(calib, str(model_dir))
        np.save(model_dir / 'blend_weights.npy', channel_weights)
        meta_path = model_dir / 'meta.json'
        meta = {}
        if meta_path.exists():
            with open(meta_path) as f:
                meta = json.load(f)
        meta['best_physics_weight'] = best_w
        meta['best_ml_blend_weight'] = best_w
        meta['blend_anchor'] = 'physics_estimate'
        meta['blend_weights'] = {
            CORE_FEATURE_NAMES[i]: float(channel_weights[i]) for i in range(NUM_CORE_FEATURES)
        }
        meta['channel_ml_blend_weights'] = channel_weights.tolist()
        meta['calibration'] = {
            'method': calib.get('method'),
            'val_rmse_raw': rmse_before,
            'val_rmse_calibrated': rmse_after,
            'calibrated_per_channel_val_rmse': rmse_cal_blend,
            'physics_only_val_rmse': rmse_phys_only,
        }
        with open(meta_path, 'w') as f:
            json.dump(meta, f, indent=2, default=str)
        print(f'\nSaved calibration + blend_weights.npy + updated {meta_path}')

    out_path = model_dir / 'blend_and_calibration_report.json'
    with open(out_path, 'w') as f:
        json.dump(out, f, indent=2, default=str)
    print(f'Wrote report to {out_path}')

if __name__ == '__main__':
    main()
