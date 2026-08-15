
"""LIPAS."""
import argparse
import json
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))

from data_ingestion import (
    split_extended_dataset,
    load_training_csv,
)
from space_weather_model import (
    load_saved_model,
    make_sliding_windows_grouped,
    SEQUENCE_LENGTH,
    CORE_FEATURE_NAMES,
    physics_estimate,
    adaptive_channel_blend_weights,
    get_channel_blend_weights,
    load_blend_weights,
)

def _rmse(a, b):
    return float(np.sqrt(np.mean((a - b) ** 2)))

def _mae(a, b):
    return float(np.mean(np.abs(a - b)))

def evaluate_extended(csv_path, model_dir, sequence_length=SEQUENCE_LENGTH, window_stride=7):
    model = load_saved_model(model_dir, set_global=False)
    if model is None:
        raise RuntimeError(f'No model in {model_dir}')
    scaler = np.load(os.path.join(model_dir, 'scaler.npz'))
    mean, std = scaler['mean'], scaler['std']
    load_blend_weights(model_dir)

    df = pd.read_csv(csv_path)
    split = split_extended_dataset(df, val_frac=0.15, test_frac=0.15, chronological=True)
    X_test = split['X_test'].astype(np.float32)
    Y_test = split['Y_test'].astype(np.float32)
    g_test = split['groups_test']
    if len(X_test) == 0:
        raise RuntimeError('empty test split')
    Xs = (X_test - mean) / std

    is_temporal = isinstance(model.input_shape, tuple) and len(model.input_shape) == 3
    if is_temporal:
        Xw, Yw = make_sliding_windows_grouped(
            Xs, Y_test, g_test, sequence_length=sequence_length, stride=window_stride,
        )
        raw = Xw[:, -1, :] * std + mean
    else:
        Xw, Yw = Xs, Y_test
        raw = X_test

    preds = model.predict(Xw, verbose=0)

    phys = np.zeros_like(Yw)
    regimes = []
    for i in range(len(raw)):
        p = physics_estimate(raw[i, :6], lat=float(raw[i, 6]), lon=float(raw[i, 7]),
                             local_time=float(raw[i, 8]))
        phys[i] = [p['solar'], p['radiation'], p['temperature'],
                   p['moonquakes'], p['micrometeorites'], p['dust']]
        regimes.append(p.get('regime') or {})

    base_w = np.asarray(get_channel_blend_weights(), dtype=np.float64)
    hybrid = np.zeros_like(preds)
    for i in range(len(preds)):
        w = adaptive_channel_blend_weights(
            base_w, {'regime': regimes[i]}, ml_std=None, inputs=raw[i, :6],
        )
        w = np.asarray(w, dtype=np.float64)
        hybrid[i] = w * preds[i] + (1.0 - w) * phys[i]

    persistence = raw[:, :6]

    out = {
        'n_test': int(len(Yw)),
        'temporal': bool(is_temporal),
        'ml_rmse': _rmse(preds, Yw),
        'ml_mae': _mae(preds, Yw),
        'physics_rmse': _rmse(phys, Yw),
        'physics_mae': _mae(phys, Yw),
        'hybrid_rmse': _rmse(hybrid, Yw),
        'hybrid_mae': _mae(hybrid, Yw),
        'persistence_rmse': _rmse(persistence, Yw),
        'persistence_mae': _mae(persistence, Yw),
        'per_channel_ml_rmse': {CORE_FEATURE_NAMES[i]: _rmse(preds[:, i], Yw[:, i])
                                for i in range(min(6, preds.shape[1]))},
        'per_channel_hybrid_rmse': {CORE_FEATURE_NAMES[i]: _rmse(hybrid[:, i], Yw[:, i])
                                    for i in range(min(6, hybrid.shape[1]))},
        'blend_weights': base_w.tolist(),
    }
    return out

def evaluate_legacy_dense(csv_path, model_dir):
    from tensorflow import keras
    X_df, Y_df = load_training_csv(csv_path, allow_inputs_as_targets=False)
    X = X_df.values.astype(np.float32)
    Y = Y_df.values.astype(np.float32)
    sc = np.load(os.path.join(model_dir, 'scaler.npz'))
    Xs = (X - sc['mean']) / sc['std']
    model = keras.models.load_model(os.path.join(model_dir, 'model.keras'), compile=False)
    preds = model.predict(Xs, verbose=0)
    n = min(len(preds), len(Y))
    return {
        'rmse': _rmse(preds[:n], Y[:n]),
        'mae': _mae(preds[:n], Y[:n]),
        'n': n,
        'legacy_dense': True,
    }

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--csv', required=True)
    parser.add_argument('--model-dir', default='saved_model')
    parser.add_argument('--sequence-length', type=int, default=SEQUENCE_LENGTH)
    parser.add_argument('--window-stride', type=int, default=7)
    parser.add_argument('--out', type=str, default=None, help='Optional JSON report path')
    args = parser.parse_args()

    df_head = pd.read_csv(args.csv, nrows=2)
    if 'site' in df_head.columns and 'lat' in df_head.columns:
        out = evaluate_extended(args.csv, args.model_dir, args.sequence_length, args.window_stride)
    else:
        out = evaluate_legacy_dense(args.csv, args.model_dir)
    print('Evaluation results:', json.dumps(out, indent=2))
    if args.out:
        Path(args.out).write_text(json.dumps(out, indent=2))
        print('Wrote', args.out)

if __name__ == '__main__':
    main()
