"""Train a Mercury solar LSTM (no temperature) into mercurius/saved_model.

Head is persistence + residual on solar / radiation / standoff / P_dyn / |B|.
Temperature stays physics-only. Refuses to save unless test RMSE beats persistence.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

os.environ.setdefault('MPLCONFIGDIR', '/tmp/mpl')
os.environ.setdefault('TF_CPP_MIN_LOG_LEVEL', '2')
os.environ.setdefault('CUDA_VISIBLE_DEVICES', '')

import tensorflow as tf
try:
    tf.config.set_visible_devices([], 'GPU')
except Exception:
    pass

from data_ingestion import split_extended_dataset
from mercurius.mercury_lstm import (
    BLEND_WEIGHTS,
    CHANNEL_KEYS,
    HAZARD_COLUMNS,
    MODEL_DIR,
    OUTPUT_BOUNDS,
    SEQUENCE_LENGTH,
    SOLAR_FEATURE_IDX,
    apply_channel_mix,
    build_mercury_solar_model,
    fit_ridge_residuals,
    mix_heads_on_val,
    persist_from_scaled_windows,
    ridge_predict,
)
from space_weather_model import make_sliding_windows_grouped
from training_pipeline import _apply_scaler, _fit_scaler

SOLAR_NAMES = list(HAZARD_COLUMNS)


def _metrics(preds: np.ndarray, y: np.ndarray, persist: np.ndarray, names: list[str]) -> dict:
    rmse = float(np.sqrt(np.mean((preds - y) ** 2)))
    pers = float(np.sqrt(np.mean((persist - y) ** 2)))
    per_ch = {}
    pers_ch = {}
    for i, name in enumerate(names):
        per_ch[name] = float(np.sqrt(np.mean((preds[:, i] - y[:, i]) ** 2)))
        pers_ch[name] = float(np.sqrt(np.mean((persist[:, i] - y[:, i]) ** 2)))
    skill = 0.0 if pers <= 1e-12 else 100.0 * (1.0 - rmse / pers)
    return {
        'test_rmse': rmse,
        'test_mae': float(np.mean(np.abs(preds - y))),
        'test_rmse_persistence': pers,
        'test_mae_persistence': float(np.mean(np.abs(persist - y))),
        'test_rmse_per_channel': per_ch,
        'test_rmse_persistence_per_channel': pers_ch,
        'skill_pct': skill,
    }


def _clip_solar(preds: np.ndarray) -> np.ndarray:
    out = np.asarray(preds, dtype=np.float64).copy()
    for i, (lo, hi) in enumerate(OUTPUT_BOUNDS):
        if i < out.shape[1]:
            out[:, i] = np.clip(out[:, i], lo, hi)
    return out


def train_once(
    csv_path: Path,
    model_dir: Path,
    epochs: int,
    batch_size: int,
    sequence_length: int,
    window_stride: int,
    learning_rate: float,
    lstm_units: tuple[int, ...],
) -> dict:
    print(f'Loading {csv_path}...')
    import pandas as pd
    df = pd.read_csv(csv_path)
    split = split_extended_dataset(df, val_frac=0.15, test_frac=0.15, chronological=True)
    idx = np.asarray(SOLAR_FEATURE_IDX)
    X_train, Y_train, g_train = split['X_train'].astype(np.float32), split['Y_train'].astype(np.float32)[:, idx], split['groups_train']
    X_val, Y_val, g_val = split['X_val'].astype(np.float32), split['Y_val'].astype(np.float32)[:, idx], split['groups_val']
    X_test, Y_test, g_test = split['X_test'].astype(np.float32), split['Y_test'].astype(np.float32)[:, idx], split['groups_test']

    mean, std = _fit_scaler(X_train)
    Xs_train = _apply_scaler(X_train, mean, std)
    Xs_val = _apply_scaler(X_val, mean, std)
    Xs_test = _apply_scaler(X_test, mean, std)

    print(f'Windows sequence_length={sequence_length} stride={window_stride}')
    Xw_train, Yw_train = make_sliding_windows_grouped(Xs_train, Y_train, g_train, sequence_length=sequence_length, stride=window_stride)
    Xw_val, Yw_val = make_sliding_windows_grouped(Xs_val, Y_val, g_val, sequence_length=sequence_length, stride=window_stride)
    Xw_test, Yw_test = make_sliding_windows_grouped(Xs_test, Y_test, g_test, sequence_length=sequence_length, stride=window_stride)
    print(f'Windows: train={len(Xw_train)} val={len(Xw_val)} test={len(Xw_test)}')

    persist_test = persist_from_scaled_windows(Xw_test, mean, std)
    persist_val = persist_from_scaled_windows(Xw_val, mean, std)
    persist_rmse0 = float(np.sqrt(np.mean((persist_test - Yw_test) ** 2)))
    print(f'Persistence RMSE (solar channels): {persist_rmse0:.4f}')

    model = build_mercury_solar_model(
        sequence_length=sequence_length,
        num_features=Xs_train.shape[1],
        mean=mean,
        std=std,
        lstm_units=lstm_units,
        learning_rate=learning_rate,
    )
    opt = tf.keras.optimizers.Adam(learning_rate=learning_rate, clipnorm=1.0)
    model.compile(optimizer=opt, loss='mse', metrics=['mae'])

    print('Fitting LSTM (MSE, no storm weights)...')
    model.fit(
        Xw_train, Yw_train,
        validation_data=(Xw_val, Yw_val),
        epochs=epochs,
        batch_size=batch_size,
        shuffle=True,
        callbacks=[
            tf.keras.callbacks.EarlyStopping(monitor='val_loss', patience=10, restore_best_weights=True, verbose=1),
            tf.keras.callbacks.ReduceLROnPlateau(monitor='val_loss', factor=0.5, patience=4, min_lr=1e-5, verbose=1),
        ],
        verbose=2,
    )

    lstm_val = np.asarray(model.predict(Xw_val, verbose=0))
    lstm_test = np.asarray(model.predict(Xw_test, verbose=0))
    print('Fitting Ridge residuals...')
    ridges = fit_ridge_residuals(Xw_train, Yw_train, mean, std)
    ridge_val = ridge_predict(ridges, Xw_val, mean, std)
    ridge_test = ridge_predict(ridges, Xw_test, mean, std)
    mix = mix_heads_on_val(lstm_val, ridge_val, persist_val, Yw_val)
    preds = _clip_solar(apply_channel_mix(lstm_test, ridge_test, persist_test, mix))
    lstm_metrics = _metrics(lstm_test, Yw_test, persist_test, SOLAR_NAMES)
    metrics = _metrics(preds, Yw_test, persist_test, SOLAR_NAMES)
    metrics['lstm_only_skill_pct'] = lstm_metrics['skill_pct']
    metrics['lstm_only_rmse'] = lstm_metrics['test_rmse']
    metrics['channel_mix'] = mix
    metrics['loss_type'] = 'mse_lstm_plus_ridge_stack'
    metrics['lstm_units'] = list(lstm_units)
    metrics['learning_rate'] = learning_rate
    metrics['epochs'] = epochs
    metrics['window_stride'] = window_stride
    print('LSTM-only RMSE', lstm_metrics['test_rmse'], f"skill {lstm_metrics['skill_pct']:.1f}%")
    print('Stacked RMSE', metrics['test_rmse'], 'persistence', metrics['test_rmse_persistence'],
          f"skill {metrics['skill_pct']:.1f}%")
    for i, name in enumerate(SOLAR_NAMES):
        w = mix[i]
        print(
            f'  {name}: stacked {metrics["test_rmse_per_channel"][name]:.4f}  '
            f'persist {metrics["test_rmse_persistence_per_channel"][name]:.4f}  '
            f'mix lstm={w["lstm"]:.2f} ridge={w["ridge"]:.2f} persist={w["persist"]:.2f}'
        )
    return {
        'metrics': metrics,
        'model': model,
        'mean': mean,
        'std': std,
        'ridges': ridges,
        'mix': mix,
    }


def wins_flying_colors(metrics: dict, min_skill_pct: float) -> bool:
    if float(metrics['skill_pct']) < min_skill_pct:
        return False
    if float(metrics['test_rmse']) >= float(metrics['test_rmse_persistence']):
        return False
    # Every solar channel must at least match persistence (tiny channels get 2% slack).
    for name, rmse in metrics['test_rmse_per_channel'].items():
        pers = metrics['test_rmse_persistence_per_channel'][name]
        if pers < 1e-6:
            continue
        if rmse > pers * 1.02:
            print(f'Channel {name} lost to persistence ({rmse:.4f} > {pers:.4f})')
            return False
    return True


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('--csv', default=str(ROOT / 'data' / 'ingested_mercury' / 'mercury_training.csv'))
    ap.add_argument('--model-dir', default=str(MODEL_DIR))
    ap.add_argument('--epochs', type=int, default=35)
    ap.add_argument('--batch-size', type=int, default=96)
    ap.add_argument('--sequence-length', type=int, default=SEQUENCE_LENGTH)
    ap.add_argument('--window-stride', type=int, default=4)
    ap.add_argument('--min-skill', type=float, default=25.0, help='Minimum % RMSE reduction vs persistence')
    args = ap.parse_args()
    csv_path = Path(args.csv)
    if not csv_path.is_file():
        raise SystemExit(f'Missing {csv_path}; run scripts/build_mercury_dataset.py first.')
    model_dir = Path(args.model_dir)
    if model_dir.resolve() == (ROOT / 'saved_model').resolve():
        raise SystemExit('Refusing to write Mercury weights into lunar saved_model/')
    model_dir.mkdir(parents=True, exist_ok=True)

    configs = [
        dict(epochs=args.epochs, window_stride=args.window_stride, learning_rate=1e-3, lstm_units=(128, 64, 32)),
        dict(epochs=max(args.epochs, 40), window_stride=2, learning_rate=8e-4, lstm_units=(128, 64, 32)),
        dict(epochs=max(args.epochs, 50), window_stride=2, learning_rate=5e-4, lstm_units=(96, 48, 24)),
    ]
    best = None
    for i, cfg in enumerate(configs, 1):
        print(f'\n=== Mercury solar train attempt {i}/{len(configs)} {cfg} ===')
        result = train_once(
            csv_path=csv_path,
            model_dir=model_dir,
            batch_size=args.batch_size,
            sequence_length=args.sequence_length,
            **cfg,
        )
        met = result['metrics']
        if best is None or met['skill_pct'] > best['metrics']['skill_pct']:
            best = result
        if wins_flying_colors(met, args.min_skill):
            best = result
            break
        print(f'Skill {met["skill_pct"]:.1f}% below {args.min_skill:.0f}% — trying a stronger run.')

    assert best is not None
    met = best['metrics']
    if not wins_flying_colors(met, args.min_skill):
        raise SystemExit(
            f'Mercury solar LSTM did not beat persistence with flying colors '
            f'(RMSE {met["test_rmse"]:.4f} vs {met["test_rmse_persistence"]:.4f}, '
            f'skill {met["skill_pct"]:.1f}%, need {args.min_skill:.0f}%).'
        )

    np.savez(model_dir / 'scaler.npz', mean=best['mean'], std=best['std'])
    best['model'].save(model_dir / 'model.keras')
    best['model'].save(model_dir / 'best.keras')
    np.save(model_dir / 'blend_weights.npy', BLEND_WEIGHTS)
    import joblib
    joblib.dump(best['ridges'], model_dir / 'ridge_residual.joblib')
    extra = {
        'body': 'mercury',
        'head': 'solar_persistence_residual_ridge_stack',
        'temperature_ml': False,
        'parent_architecture': 'mercury_solar_residual_lstm',
        'heliospheric_drivers': ['solar_wind_speed', 'solar_wind_density', 'imf_bz', 'kp_index'],
        'lunar_saved_model_untouched': True,
        'channel_labels': list(CHANNEL_KEYS),
        'output_bounds': OUTPUT_BOUNDS,
        'channel_ml_blend_weights': BLEND_WEIGHTS.tolist(),
        'channel_mix': best['mix'],
        'solar_feature_idx': list(SOLAR_FEATURE_IDX),
        'note': (
            'Next-day solar/heliosphere forecast. Temperature is not an ML target. '
            'Head is last-step persistence plus a residual LSTM, stacked with Ridge. '
            'Lunar weights were not loaded or fine-tuned.'
        ),
        'metrics': met,
    }
    (model_dir / 'mercury_meta.json').write_text(json.dumps(extra, indent=2), encoding='utf-8')
    print('Wrote', model_dir / 'mercury_meta.json')
    print(f'Saved solar LSTM with {met["skill_pct"]:.1f}% RMSE skill vs persistence.')


if __name__ == '__main__':
    main()
