
"""LIPAS."""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np

from space_weather_model import load_saved_model, make_sliding_windows_grouped, SEQUENCE_LENGTH
import pandas as pd

from data_ingestion import split_extended_dataset, EXTENDED_TRAINING_COLUMNS, get_target_columns

KNOWN_STORMS = [
    {'date': '2024-05-11', 'name': 'Gannon Storm (May 2024, G5 extreme)', 'dst': -286.5},
    {'date': '1989-03-14', 'name': 'March 1989 storm (Quebec blackout)', 'dst': -224.7},
    {'date': '1991-11-09', 'name': 'November 1991 storm', 'dst': -222.5},
    {'date': '2003-10-30', 'name': 'Halloween storm (Oct 2003)', 'dst': -221.0},
    {'date': '2001-03-31', 'name': 'March 2001 storm', 'dst': -210.9},
    {'date': '2004-11-08', 'name': 'November 2004 storm', 'dst': -209.9},
    {'date': '2024-10-11', 'name': 'October 2024 storm', 'dst': -197.3},
    {'date': '1989-10-21', 'name': 'October 1989 storm', 'dst': -191.3},
    {'date': '1991-03-25', 'name': 'March 1991 Great storm', 'dst': -193.9},
    {'date': '1986-02-09', 'name': 'February 1986 storm', 'dst': -164.1},
]

def load_model_and_scaler(model_dir):
    model = load_saved_model(model_dir)
    if model is None:
        raise RuntimeError(f'No saved model found in {model_dir}')
    scaler_path = Path(model_dir) / 'scaler.npz'
    scaler = np.load(scaler_path)
    return model, scaler['mean'], scaler['std']

def formal_test_metrics(csv_path, model_dir, sequence_length=SEQUENCE_LENGTH, window_stride=7,
                         validation_split=0.15, test_split=0.15):
    model, mean, std = load_model_and_scaler(model_dir)
    df = pd.read_csv(csv_path)
    split = split_extended_dataset(df, val_frac=validation_split, test_frac=test_split, chronological=True)
    X_test, Y_test, g_test = split['X_test'].astype(np.float32), split['Y_test'].astype(np.float32), split['groups_test']
    if len(X_test) == 0:
        return {'error': 'empty test split'}
    Xs_test = (X_test - mean) / std

    is_temporal = len(model.input_shape) == 3
    if is_temporal:
        Xw_test, Yw_test = make_sliding_windows_grouped(Xs_test, Y_test, g_test, sequence_length=sequence_length, stride=window_stride)
        if len(Xw_test) == 0:
            return {'error': 'not enough per-site test rows to form a temporal window'}
        preds = model.predict(Xw_test, verbose=0)
        y_true = Yw_test
        persistence = Xw_test[:, -1, :6] * std[:6] + mean[:6]
    else:
        preds = model.predict(Xs_test, verbose=0)
        y_true = Y_test
        persistence = Xs_test[:, :6] * std[:6] + mean[:6]

    mse = float(np.mean((preds - y_true) ** 2))
    mae = float(np.mean(np.abs(preds - y_true)))
    pers_mse = float(np.mean((persistence - y_true) ** 2))
    pers_mae = float(np.mean(np.abs(persistence - y_true)))
    return {
        'n_test_samples': int(len(y_true)),
        'model_rmse': float(np.sqrt(mse)), 'model_mae': mae,
        'persistence_rmse': float(np.sqrt(pers_mse)), 'persistence_mae': pers_mae,
        'model_beats_persistence_rmse': float(np.sqrt(mse)) < float(np.sqrt(pers_mse)),
        'model_beats_persistence_mae': mae < pers_mae,
        'rmse_improvement_pct': 100.0 * (1 - float(np.sqrt(mse)) / float(np.sqrt(pers_mse))) if pers_mse > 0 else None,
    }

def storm_event_backtest(csv_path, model_dir, sequence_length=SEQUENCE_LENGTH):
    model, mean, std = load_model_and_scaler(model_dir)
    is_temporal = len(model.input_shape) == 3

    df = pd.read_csv(csv_path)
    df['date'] = pd.to_datetime(df['date'])
    sites = sorted(df['site'].unique())
    target_cols = get_target_columns()

    results = []
    for storm in KNOWN_STORMS:
        storm_date = pd.Timestamp(storm['date'])
        for site in sites:
            site_df = df[df['site'] == site].sort_values('date').reset_index(drop=True)
            if storm_date not in set(site_df['date']):
                continue
            idx = site_df.index[site_df['date'] == storm_date][0]

            def build_input(end_idx):
                if is_temporal:
                    start_idx = end_idx - sequence_length + 1
                    if start_idx < 0:
                        return None
                    window = site_df.iloc[start_idx:end_idx + 1][EXTENDED_TRAINING_COLUMNS[:len(mean)]].values.astype(np.float32)
                    return ((window - mean) / std)[None, :, :]
                else:
                    row = site_df.iloc[end_idx][EXTENDED_TRAINING_COLUMNS[:len(mean)]].values.astype(np.float32)
                    return ((row - mean) / std)[None, :]

            storm_input = build_input(idx)
            if storm_input is None:
                continue
            storm_pred = model.predict(storm_input, verbose=0)[0]

            quiet_idx = idx - 45
            quiet_input = build_input(quiet_idx) if quiet_idx >= sequence_length else None
            quiet_pred = model.predict(quiet_input, verbose=0)[0] if quiet_input is not None else None

            results.append({
                'storm': storm['name'], 'date': storm['date'], 'real_dst': storm['dst'],
                'site': site,
                'real_kp_on_date': float(site_df.iloc[idx]['kp_index']),
                'real_solar_activity_on_date': float(site_df.iloc[idx]['solar_activity']),
                'predicted_hazard': {c: float(v) for c, v in zip(target_cols, storm_pred)},
                'quiet_control_predicted_hazard': ({c: float(v) for c, v in zip(target_cols, quiet_pred)}
                                                    if quiet_pred is not None else None),
            })
    return results

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--csv', type=str, required=True)
    parser.add_argument('--model-dir', type=str, default='saved_model_extended')
    parser.add_argument('--sequence-length', type=int, default=SEQUENCE_LENGTH)
    parser.add_argument('--window-stride', type=int, default=7)
    parser.add_argument('--output', type=str, default='data/backtest_results.json')
    args = parser.parse_args()

    print(                                                                  , flush=True)
    formal = formal_test_metrics(args.csv, args.model_dir, args.sequence_length, args.window_stride)
    print(json.dumps(formal, indent=2), flush=True)

    print('\n=== 2. Real known-storm event backtest ===', flush=True)
    storms = storm_event_backtest(args.csv, args.model_dir, args.sequence_length)
    for r in storms:
        pred = r['predicted_hazard']
        ctrl = r['quiet_control_predicted_hazard']
        print(f"{r['date']} {r['storm']} @ {r['site']} (real Dst={r['real_dst']}, "
              f"real Kp on date={r['real_kp_on_date']:.2f}, real solar_activity={r['real_solar_activity_on_date']:.1f})", flush=True)
        print(f"  predicted: {pred}", flush=True)
        if ctrl is not None:
            print(f"  quiet-day control: {ctrl}", flush=True)
        print(flush=True)

    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, 'w') as f:
        json.dump({'formal_test_metrics': formal, 'storm_backtest': storms}, f, indent=2, default=str)
    print(f'Wrote full results to {args.output}', flush=True)

if __name__ == '__main__':
    main()
