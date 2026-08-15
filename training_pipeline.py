
"""LIPAS."""
import argparse
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import tensorflow as tf
import pandas as pd

from data_ingestion import (
    fetch_real_source_data,
    batch_ingest_from_sources,
    load_training_csv,
    split_dataset,
    get_input_columns,
    get_target_columns,
    split_extended_dataset,
    get_extended_input_columns,
    EXTENDED_TRAINING_COLUMNS,
)
from models import train_ensemble
from space_weather_model import (
    build_model,
    build_temporal_model,
    make_sliding_windows_grouped,
    make_channel_normalized_huber,
    make_weighted_huber,
    SEQUENCE_LENGTH,
    CORE_FEATURE_NAMES,
    DEFAULT_TEMPORAL_HYPERPARAMS,
)

DEFAULT_VAL_SPLIT = 0.15
DEFAULT_TEST_SPLIT = 0.15
MIN_ROWS_TO_TRAIN = 6
MIN_ROWS_FOR_HOLDOUT_SPLIT = 20
DEFAULT_WINDOW_STRIDE = 7

DEFAULT_CHANNEL_PRIORITY = np.asarray([2.0, 2.5, 1.0, 1.35, 1.5, 1.5], dtype=np.float64)

def _storm_sample_weights(Y: np.ndarray) -> np.ndarray:
    """Upweight storm / SEP-like target rows so rare events are not washed out."""
    Y = np.asarray(Y, dtype=np.float64)
    w = np.ones(len(Y), dtype=np.float32)
    if Y.ndim != 2 or Y.shape[1] < 2:
        return w
    solar = Y[:, 0]
    rad = Y[:, 1]
    w += 0.75 * (solar > 12.0).astype(np.float32)
    w += 1.25 * (solar > 20.0).astype(np.float32)
    w += 1.0 * (rad > 0.12).astype(np.float32)
    w += 1.5 * (rad > 0.25).astype(np.float32)

    if Y.shape[1] > 3:
        mq = Y[:, 3]
        w += 0.5 * (mq > 50.0).astype(np.float32)

    if Y.shape[1] > 4:
        mf = Y[:, 4]
        w += 0.35 * (mf > 2.0).astype(np.float32)
    if Y.shape[1] > 5:
        dust = Y[:, 5]
        w += 0.35 * (dust > 2.2).astype(np.float32)
    return np.clip(w, 1.0, 5.0)

def _recency_sample_weights(groups_or_dates, n: int, half_life_frac: float = 0.35) -> np.ndarray:
    """Upweight later chronology so live ops favor recent solar-cycle regimes."""
    w = np.linspace(0.55, 1.0, num=max(1, int(n)), dtype=np.float32)

    t = np.linspace(0.0, 1.0, num=max(1, int(n)), dtype=np.float32)
    decay = np.exp(np.log(0.5) * (1.0 - t) / max(half_life_frac, 1e-3))
    out = (0.65 * w + 0.35 * decay).astype(np.float32)
    return np.clip(out, 0.5, 1.35)

def _merge_temporal_kwargs(model_kwargs: dict | None) -> dict:
    """Start from production defaults; let CLI/Optuna overrides win."""
    merged = dict(DEFAULT_TEMPORAL_HYPERPARAMS)
    if model_kwargs:
        merged.update(model_kwargs)

    for key in ('lstm_units', 'dense_units', 'dropout'):
        if key in merged and not isinstance(merged[key], tuple):
            merged[key] = tuple(merged[key])
    return merged

def fetch_and_ingest(start_date: str, end_date: str, nasa_key: str, extra_urls: dict, out_dir: str, local_sources: dict | None = None, parquet: bool = False):
    print(f'Fetching remote source data for {start_date} to {end_date}...')
    sources = fetch_real_source_data(start_date=start_date, end_date=end_date, nasa_key=nasa_key, extra_urls=extra_urls)
    if local_sources:
        sources.update(local_sources)
    if not sources:
        raise RuntimeError('No source payloads available for ingestion.')
    print('Fetched source payloads. Ingesting into canonical dataset...')
    paths = batch_ingest_from_sources(sources, out_dir=out_dir, parquet=parquet, chunk_size=100000)
    if not paths:
        raise RuntimeError('No training files were written from ingestion.')
    print('Wrote ingested datasets:')
    for p in paths:
        print('-', p)
    return paths

def ingest_raw_swpc_dir(source_dir: str, out_dir: str, augment_if_sparse: bool = False) -> str:
    """Ingest local SWPC dumps."""
    from ingest_swpc_data import ingest_all_swpc
    result = ingest_all_swpc(source_dir=source_dir, out_dir=out_dir, augment_if_sparse=augment_if_sparse)
    if not result.get('csv_path'):
        raise RuntimeError(f'No training rows could be ingested from {source_dir}.')
    print(f"Ingested {result['real_rows']} real rows from {source_dir} (augmented={result['augmented']}) -> {result['csv_path']}")
    return result['csv_path']

def _fit_scaler(X_train: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Fit scaler on train only."""
    mean = X_train.mean(axis=0)
    std = X_train.std(axis=0)
    std[std == 0] = 1.0
    return mean, std

def _apply_scaler(X: np.ndarray, mean: np.ndarray, std: np.ndarray) -> np.ndarray:
    return (X - mean) / std

def verify_model_scaler_sync(model_dir: str) -> dict:
    """Load the saved scaler and model from `model_dir` and assert their"""
    scaler_path = os.path.join(model_dir, 'scaler.npz')
    if not os.path.exists(scaler_path):
        raise RuntimeError(f'verify_model_scaler_sync: scaler not found at {scaler_path}')
    scaler = np.load(scaler_path)
    scaler_dim = int(scaler['mean'].shape[0])

    model_path = None
    for candidate in ('model.keras', 'best.keras', 'best.h5', 'model.h5'):
        p = os.path.join(model_dir, candidate)
        if os.path.exists(p):
            model_path = p
            break
    if model_path is None:
        raise RuntimeError(f'verify_model_scaler_sync: no model file found in {model_dir}')

    model = tf.keras.models.load_model(model_path, compile=False)
    model_input_shape = model.input_shape

    if isinstance(model_input_shape, list):
        model_input_shape = model_input_shape[0]
    model_dim = model_input_shape[-1]

    if model_dim != scaler_dim:
        raise RuntimeError(
            f'scaler/model dimension mismatch in {model_dir}: '
            f'scaler.npz has {scaler_dim} features but {os.path.basename(model_path)} '
            f'expects {model_dim} inputs. Retrain with train_base_model() so both '
            f'artifacts are written together from the same feature matrix.'
        )
    return {'scaler_dim': scaler_dim, 'model_dim': model_dim, 'model_path': model_path, 'in_sync': True}

def _write_training_meta(model_dir: str, *, mean: np.ndarray, std: np.ndarray, model: tf.keras.Model,
                          n_train: int, n_val: int, n_test: int, metrics: dict, csv_path: str) -> str:
    meta = {
        'timestamp_utc': datetime.now(timezone.utc).isoformat(),
        'source_csv': csv_path,
        'input_columns': get_input_columns(),
        'target_columns': get_target_columns(),
        'input_dim': int(mean.shape[0]),
        'output_dim': int(model.output_shape[-1]) if not isinstance(model.output_shape, list) else int(model.output_shape[0][-1]),
        'model_input_dim': int(model.input_shape[-1]) if not isinstance(model.input_shape, list) else int(model.input_shape[0][-1]),
        'rows': {'train': n_train, 'val': n_val, 'test': n_test, 'total': n_train + n_val + n_test},
        'metrics': metrics,
    }
    meta_path = os.path.join(model_dir, 'meta.json')
    with open(meta_path, 'w') as f:
        json.dump(meta, f, indent=2)
    return meta_path

def train_base_model(csv_path: str, model_dir: str, epochs: int, batch_size: int, validation_split: float = DEFAULT_VAL_SPLIT,
                      test_split: float = DEFAULT_TEST_SPLIT, chronological: bool = True):
    print(f'Loading training CSV from {csv_path}...')
    X_df, Y_df = load_training_csv(csv_path, allow_inputs_as_targets=False)
    n_samples = len(X_df)
    if n_samples < MIN_ROWS_TO_TRAIN:
        raise RuntimeError(f'Not enough rows to train the model. Need at least {MIN_ROWS_TO_TRAIN} rows, got {n_samples}.')

    os.makedirs(model_dir, exist_ok=True)

    use_holdout = n_samples >= MIN_ROWS_FOR_HOLDOUT_SPLIT and validation_split > 0.0
    if use_holdout:
        split = split_dataset(X_df, Y_df, val_frac=validation_split, test_frac=test_split, chronological=chronological)
        X_train, Y_train = split['X_train'].astype(np.float32), split['Y_train'].astype(np.float32)
        X_val, Y_val = split['X_val'].astype(np.float32), split['Y_val'].astype(np.float32)
        X_test, Y_test = split['X_test'].astype(np.float32), split['Y_test'].astype(np.float32)
        print(f'Split {n_samples} rows -> train={len(X_train)}, val={len(X_val)}, test={len(X_test)} '
              f'({"chronological" if chronological else "random"})')
    else:

        X_train, Y_train = X_df.values.astype(np.float32), Y_df.values.astype(np.float32)
        X_val = Y_val = X_test = Y_test = np.empty((0, X_train.shape[1]), dtype=np.float32)
        print(f'Only {n_samples} rows available (< {MIN_ROWS_FOR_HOLDOUT_SPLIT}); training on all rows with no test split.')

    mean, std = _fit_scaler(X_train)
    Xs_train = _apply_scaler(X_train, mean, std)
    Xs_val = _apply_scaler(X_val, mean, std) if len(X_val) else X_val
    Xs_test = _apply_scaler(X_test, mean, std) if len(X_test) else X_test

    input_dim = X_train.shape[1]
    output_dim = Y_train.shape[1]
    model = build_model(input_shape=(input_dim,))
    if model.output_shape[-1] != output_dim:
        raise RuntimeError(
            f'Model output dim {model.output_shape[-1]} does not match target dim {output_dim}. '
            f'build_model() must be updated to match the canonical target schema.'
        )

    callbacks = []
    if len(Xs_val):
        try:
            callbacks.append(tf.keras.callbacks.EarlyStopping(monitor='val_loss', patience=10, restore_best_weights=True))
        except Exception:
            pass
    try:
        ckpt_monitor = 'val_loss' if len(Xs_val) else 'loss'
        callbacks.append(tf.keras.callbacks.ModelCheckpoint(os.path.join(model_dir, 'best.keras'), save_best_only=True, monitor=ckpt_monitor))
    except Exception:
        pass

    fit_kwargs = dict(epochs=epochs, batch_size=batch_size, shuffle=True, callbacks=callbacks, verbose=1)
    if len(Xs_val):
        history = model.fit(Xs_train, Y_train, validation_data=(Xs_val, Y_val), **fit_kwargs)
    else:
        fit_kwargs['epochs'] = max(10, min(epochs, 100))
        fit_kwargs['batch_size'] = max(4, batch_size)
        history = model.fit(Xs_train, Y_train, **fit_kwargs)

    metrics = {k: float(v[-1]) for k, v in (history.history.items() if hasattr(history, 'history') else {})}

    if len(Xs_test):
        test_preds = model.predict(Xs_test, verbose=0)
        test_mse = float(np.mean((test_preds - Y_test) ** 2))
        test_mae = float(np.mean(np.abs(test_preds - Y_test)))
        metrics['test_mse'] = test_mse
        metrics['test_rmse'] = float(np.sqrt(test_mse))
        metrics['test_mae'] = test_mae
        print(f'Test metrics: rmse={metrics["test_rmse"]:.4f} mae={test_mae:.4f}')

    np.savez(os.path.join(model_dir, 'scaler.npz'), mean=mean, std=std)
    model_path = os.path.join(model_dir, 'model.keras')
    model.save(model_path)
    try:
        model.save(os.path.join(model_dir, 'best.keras'))
    except Exception:
        pass
    print(f'Saved scaler to {os.path.join(model_dir, "scaler.npz")}')
    print(f'Saved trained base model to {model_path}')

    sync = verify_model_scaler_sync(model_dir)
    print(f'Scaler/model sync verified: {sync}')

    meta_path = _write_training_meta(
        model_dir, mean=mean, std=std, model=model,
        n_train=len(X_train), n_val=len(X_val), n_test=len(X_test),
        metrics=metrics, csv_path=csv_path,
    )
    print(f'Wrote training metadata to {meta_path}')

    return metrics

def train_extended_model(
    csv_path: str,
    model_dir: str,
    epochs: int = 60,
    batch_size: int = 64,
    validation_split: float = DEFAULT_VAL_SPLIT,
    test_split: float = DEFAULT_TEST_SPLIT,
    sequence_length: int = SEQUENCE_LENGTH,
    window_stride: int = DEFAULT_WINDOW_STRIDE,
    physical_bounds: bool = True,
    force_dense: bool = False,
    model_kwargs: dict = None,
    df_override: "pd.DataFrame" = None,
    save_artifacts: bool = True,

    use_sample_weights: bool = False,
    use_cosine_decay: bool = False,
    use_recency_weights: bool = False,
):
    model_kwargs = _merge_temporal_kwargs(model_kwargs)
    if df_override is not None:
        df = df_override
    else:
        print(f'Loading extended training CSV from {csv_path}...')
        df = pd.read_csv(csv_path)
    missing = [c for c in ['date', 'site'] + EXTENDED_TRAINING_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f'Extended CSV missing required columns: {missing}')
    n_samples = len(df)
    if n_samples < MIN_ROWS_TO_TRAIN:
        raise RuntimeError(f'Not enough rows to train. Need at least {MIN_ROWS_TO_TRAIN}, got {n_samples}.')

    if save_artifacts:
        os.makedirs(model_dir, exist_ok=True)

    split = split_extended_dataset(df, val_frac=validation_split, test_frac=test_split, chronological=True)
    X_train, Y_train, g_train = split['X_train'].astype(np.float32), split['Y_train'].astype(np.float32), split['groups_train']
    X_val, Y_val, g_val = split['X_val'].astype(np.float32), split['Y_val'].astype(np.float32), split['groups_val']
    X_test, Y_test, g_test = split['X_test'].astype(np.float32), split['Y_test'].astype(np.float32), split['groups_test']
    print(f'Per-site chronological split: train={len(X_train)}, val={len(X_val)}, test={len(X_test)} '
          f'across {len(set(g_train))} sites')

    mean, std = _fit_scaler(X_train)
    Xs_train = _apply_scaler(X_train, mean, std)
    Xs_val = _apply_scaler(X_val, mean, std) if len(X_val) else X_val
    Xs_test = _apply_scaler(X_test, mean, std) if len(X_test) else X_test

    input_dim = X_train.shape[1]
    min_rows_per_site_for_window = sequence_length + 10
    site_counts = pd.Series(g_train).value_counts()
    use_temporal = (not force_dense) and bool((site_counts >= min_rows_per_site_for_window).any())

    build_kwargs = {k: v for k, v in model_kwargs.items()
                    if k in ('lstm_units', 'dense_units', 'dropout', 'l2_reg', 'learning_rate',
                             'use_attention', 'use_last_timestep_skip', 'clipnorm')}

    if use_temporal:
        print(f'Building per-site sliding windows (sequence_length={sequence_length}, stride={window_stride})...')
        Xw_train, Yw_train = make_sliding_windows_grouped(Xs_train, Y_train, g_train, sequence_length=sequence_length, stride=window_stride)
        Xw_val, Yw_val = (make_sliding_windows_grouped(Xs_val, Y_val, g_val, sequence_length=sequence_length, stride=window_stride)
                          if len(Xs_val) and pd.Series(g_val).value_counts().max() >= sequence_length else (np.empty((0, sequence_length, input_dim), dtype=np.float32), np.empty((0, Y_train.shape[1]), dtype=np.float32)))
        Xw_test, Yw_test = (make_sliding_windows_grouped(Xs_test, Y_test, g_test, sequence_length=sequence_length, stride=window_stride)
                            if len(Xs_test) and pd.Series(g_test).value_counts().max() >= sequence_length else (np.empty((0, sequence_length, input_dim), dtype=np.float32), np.empty((0, Y_train.shape[1]), dtype=np.float32)))
        print(f'Windows: train={len(Xw_train)}, val={len(Xw_val)}, test={len(Xw_test)}')
        model = build_temporal_model(sequence_length=sequence_length, num_features=input_dim, physical_bounds=physical_bounds, **build_kwargs)
        Xs_fit, Y_fit = Xw_train, Yw_train
        Xs_val_fit, Y_val_fit = Xw_val, Yw_val
        Xs_test_fit, Y_test_fit = Xw_test, Yw_test
    else:
        print('Not enough rows per site for a temporal window; training the dense expanded model instead.')
        dense_kwargs = {k: v for k, v in build_kwargs.items() if k == 'learning_rate'}
        model = build_model(input_shape=(input_dim,), physical_bounds=physical_bounds, **dense_kwargs)
        Xs_fit, Y_fit = Xs_train, Y_train
        Xs_val_fit, Y_val_fit = Xs_val, Y_val
        Xs_test_fit, Y_test_fit = Xs_test, Y_test

    y_std = np.std(Y_fit, axis=0).astype(np.float64)
    y_std = np.maximum(y_std, 1e-4)
    if model_kwargs.get('channel_priority') is not None:
        priority = np.asarray(model_kwargs['channel_priority'], dtype=np.float64)
        if priority.shape != (6,):
            raise ValueError(f'channel_priority must have length 6, got {priority.shape}')
    else:
        priority = DEFAULT_CHANNEL_PRIORITY.copy()

    if model_kwargs.get('boost_radiation_priority'):
        priority = priority.copy()
        priority[1] = max(float(priority[1]), 2.8)
    channel_scales = y_std / priority
    lr = float(model_kwargs.get('learning_rate', 1e-3))

    _cn = model_kwargs.get('clipnorm', 1.0)
    clipnorm = None if _cn in (None, False, 0, 0.0) else float(_cn)
    early_patience = int(model_kwargs.get('early_stopping_patience', 10))

    loss_type = str(model_kwargs.get('loss_type', 'huber')).lower()
    try:
        opt_kwargs = {}
        if clipnorm is not None:
            opt_kwargs['clipnorm'] = clipnorm
        if use_cosine_decay and epochs > 1:
            try:
                schedule = tf.keras.optimizers.schedules.CosineDecay(
                    initial_learning_rate=lr, decay_steps=max(1, epochs * max(1, len(Xs_fit) // max(1, batch_size))),
                    alpha=0.05,
                )
                opt = tf.keras.optimizers.Adam(learning_rate=schedule, **opt_kwargs)
                print(f'Using CosineDecay LR from {lr} over ~{epochs} epochs')
            except Exception:
                opt = tf.keras.optimizers.Adam(learning_rate=lr, **opt_kwargs)
        else:
            opt = tf.keras.optimizers.Adam(learning_rate=lr, **opt_kwargs)
        if loss_type in ('huber', 'plain_huber', 'plain'):
            model.compile(optimizer=opt, loss='huber', metrics=['mae'])
            print('Compiled with plain huber')
        elif loss_type in ('weighted_huber', 'channel_weighted_huber'):

            cw = model_kwargs.get('channel_loss_weights')
            if cw is None:
                cw = [1.0, 1.0, 1.4, 1.0, 1.0, 1.0]
            cw = np.asarray(cw, dtype=np.float64)
            if cw.shape != (6,):
                raise ValueError(f'channel_loss_weights must have length 6, got {cw.shape}')
            loss_fn = make_weighted_huber(cw)
            model.compile(optimizer=opt, loss=loss_fn, metrics=['mae'])
            print(f'Compiled with weighted_huber; channel_loss_weights={cw.tolist()}')
        else:
            loss_fn = make_channel_normalized_huber(channel_scales)
            model.compile(optimizer=opt, loss=loss_fn, metrics=['mae'])
            print(f'Compiled with channel_normalized_huber; scales={channel_scales.tolist()} priority={priority.tolist()}')
    except Exception as e:
        print(f'WARN: falling back to default huber ({e})')

    callbacks = []
    if len(Xs_val_fit):
        try:
            callbacks.append(tf.keras.callbacks.EarlyStopping(
                monitor='val_loss', patience=early_patience, restore_best_weights=True,
            ))

            use_reduce_lr = bool(model_kwargs.get('use_reduce_lr_on_plateau', False))
            if not use_cosine_decay and use_reduce_lr:
                rl_patience = int(model_kwargs.get('reduce_lr_patience', 5))
                rl_factor = float(model_kwargs.get('reduce_lr_factor', 0.5))
                rl_min = float(model_kwargs.get('reduce_lr_min', 1e-6))
                callbacks.append(tf.keras.callbacks.ReduceLROnPlateau(
                    monitor='val_loss', factor=rl_factor, patience=rl_patience,
                    min_lr=rl_min, verbose=1,
                ))
                print(f'ReduceLROnPlateau: factor={rl_factor} patience={rl_patience} min_lr={rl_min}')
        except Exception:
            pass
    if save_artifacts:
        try:
            ckpt_monitor = 'val_loss' if len(Xs_val_fit) else 'loss'
            callbacks.append(tf.keras.callbacks.ModelCheckpoint(os.path.join(model_dir, 'best.keras'), save_best_only=True, monitor=ckpt_monitor))
        except Exception:
            pass

    sw_train = _storm_sample_weights(Y_fit) if use_sample_weights else None
    if sw_train is not None and use_recency_weights:
        rw = _recency_sample_weights(g_train if not use_temporal else None, len(Y_fit))
        sw_train = np.clip(sw_train * rw, 0.5, 6.0).astype(np.float32)
        print(f'Recency×storm weights: mean={float(sw_train.mean()):.3f} max={float(sw_train.max()):.3f}')
    elif sw_train is not None:
        print(f'Storm sample weights: mean={float(sw_train.mean()):.3f} max={float(sw_train.max()):.3f}')
    fit_kwargs = dict(epochs=epochs, batch_size=batch_size, shuffle=True, callbacks=callbacks, verbose=1)
    if sw_train is not None:
        fit_kwargs['sample_weight'] = sw_train
    if len(Xs_val_fit):
        history = model.fit(Xs_fit, Y_fit, validation_data=(Xs_val_fit, Y_val_fit), **fit_kwargs)
    else:
        history = model.fit(Xs_fit, Y_fit, **fit_kwargs)

    metrics = {k: float(v[-1]) for k, v in (history.history.items() if hasattr(history, 'history') else {})}
    if loss_type in ('huber', 'plain_huber', 'plain'):
        metrics['loss_type'] = 'huber'
    elif loss_type in ('weighted_huber', 'channel_weighted_huber'):
        metrics['loss_type'] = 'weighted_huber'
        cw = model_kwargs.get('channel_loss_weights') or [1.0, 1.0, 1.4, 1.0, 1.0, 1.0]
        metrics['channel_loss_weights'] = [float(x) for x in cw]
    else:
        metrics['loss_type'] = 'channel_normalized_huber'
    metrics['channel_scales'] = [float(x) for x in channel_scales]
    metrics['channel_priority'] = [float(x) for x in priority]

    if len(Xs_test_fit):
        test_preds = model.predict(Xs_test_fit, verbose=0)
        test_mse = float(np.mean((test_preds - Y_test_fit) ** 2))
        test_mae = float(np.mean(np.abs(test_preds - Y_test_fit)))
        metrics['test_mse'] = test_mse
        metrics['test_rmse'] = float(np.sqrt(test_mse))
        metrics['test_mae'] = test_mae

        per_ch = {}
        norm_sq = []
        for i, name in enumerate(CORE_FEATURE_NAMES[: test_preds.shape[1]]):
            rmse_i = float(np.sqrt(np.mean((test_preds[:, i] - Y_test_fit[:, i]) ** 2)))
            per_ch[name] = rmse_i
            norm_sq.append(((test_preds[:, i] - Y_test_fit[:, i]) / channel_scales[i]) ** 2)
        metrics['test_rmse_per_channel'] = per_ch
        metrics['test_rmse_normalized'] = float(np.sqrt(np.mean(np.stack(norm_sq))))

        persistence_preds = Xs_test_fit[:, :6] if Xs_test_fit.ndim == 2 else Xs_test_fit[:, -1, :6]

        persistence_preds_unscaled = persistence_preds * std[:6] + mean[:6]
        pers_mse = float(np.mean((persistence_preds_unscaled - Y_test_fit) ** 2))
        pers_mae = float(np.mean(np.abs(persistence_preds_unscaled - Y_test_fit)))
        metrics['test_mse_persistence'] = pers_mse
        metrics['test_rmse_persistence'] = float(np.sqrt(pers_mse))
        metrics['test_mae_persistence'] = pers_mae
        pers_norm_sq = []
        for i in range(min(6, Y_test_fit.shape[1])):
            pers_norm_sq.append(((persistence_preds_unscaled[:, i] - Y_test_fit[:, i]) / channel_scales[i]) ** 2)
        metrics['test_rmse_normalized_persistence'] = float(np.sqrt(np.mean(np.stack(pers_norm_sq))))
        print(f'Test metrics: rmse={metrics["test_rmse"]:.4f} mae={test_mae:.4f}  |  '
              f'persistence baseline: rmse={metrics["test_rmse_persistence"]:.4f} mae={pers_mae:.4f}')
        print(f'Normalized test RMSE: {metrics["test_rmse_normalized"]:.4f}  |  '
              f'persistence normalized: {metrics["test_rmse_normalized_persistence"]:.4f}')
        for name, rmse_i in per_ch.items():
            print(f'  {name}: rmse={rmse_i:.4f}')

    if not save_artifacts:
        return metrics

    np.savez(os.path.join(model_dir, 'scaler.npz'), mean=mean, std=std)
    model_path = os.path.join(model_dir, 'model.keras')
    model.save(model_path)
    try:
        model.save(os.path.join(model_dir, 'best.keras'))
    except Exception:
        pass
    print(f'Saved scaler to {os.path.join(model_dir, "scaler.npz")}')
    print(f'Saved trained extended model to {model_path}')

    sync = verify_model_scaler_sync(model_dir)
    print(f'Scaler/model sync verified: {sync}')

    meta = {
        'timestamp_utc': datetime.now(timezone.utc).isoformat(),
        'source_csv': csv_path,
        'schema': 'extended_18_feature',
        'hybrid_system': 'temporal_lstm_plus_physics_adaptive_blend',
        'input_columns': get_extended_input_columns(),
        'target_columns': get_target_columns(),
        'input_dim': int(input_dim),
        'temporal': bool(use_temporal),
        'sequence_length': int(sequence_length) if use_temporal else None,
        'window_stride': int(window_stride) if use_temporal else None,
        'physical_bounds': bool(physical_bounds),
        'architecture': {
            'lstm_units': list(model_kwargs.get('lstm_units', ())),
            'dense_units': list(model_kwargs.get('dense_units', ())),
            'dropout': list(model_kwargs.get('dropout', ())),
            'use_attention': bool(model_kwargs.get('use_attention', False)),
            'use_last_timestep_skip': bool(model_kwargs.get('use_last_timestep_skip', False)),
            'l2_reg': float(model_kwargs.get('l2_reg', 1e-4)),
            'learning_rate': float(model_kwargs.get('learning_rate', 1e-3)),

            'clipnorm': (None if clipnorm is None else float(clipnorm)),
            'loss_type': metrics.get('loss_type'),
            'storm_sample_weights': bool(use_sample_weights),
            'cosine_decay': bool(use_cosine_decay),
            'recency_sample_weights': bool(use_recency_weights),
        },
        'sites': sorted(set(df['site'].tolist())),
        'rows': {'train': len(X_train), 'val': len(X_val), 'test': len(X_test), 'total': n_samples},
        'metrics': metrics,
    }
    meta_path = os.path.join(model_dir, 'meta.json')
    with open(meta_path, 'w') as f:
        json.dump(meta, f, indent=2)
    print(f'Wrote training metadata to {meta_path}')

    return metrics

def train_temporal_ensemble(
    csv_path: str,
    model_dir: str,
    n_models: int = 3,
    epochs: int = 50,
    batch_size: int = 64,
    sequence_length: int = SEQUENCE_LENGTH,
    window_stride: int = DEFAULT_WINDOW_STRIDE,
    base_model_kwargs: dict | None = None,
):
    os.makedirs(os.path.join(model_dir, 'ensemble'), exist_ok=True)
    variants = [
        {},
        {'lstm_units': (256, 128, 48), 'dropout': (0.32, 0.28, 0.22, 0.32, 0.28)},
        {'lstm_units': (192, 128, 64), 'dense_units': (256, 96), 'learning_rate': 8e-4},
    ]
    paths = []
    for i in range(n_models):
        seed = 1000 + i
        try:
            tf.random.set_seed(seed)
            np.random.seed(seed)
        except Exception:
            pass
        kw = _merge_temporal_kwargs(base_model_kwargs)
        kw.update(variants[i % len(variants)])
        member_dir = os.path.join(model_dir, 'ensemble', f'member_{i}')
        print(f'=== Temporal ensemble member {i + 1}/{n_models} (seed={seed}) → {member_dir} ===')
        train_extended_model(
            csv_path=csv_path,
            model_dir=member_dir,
            epochs=epochs,
            batch_size=batch_size,
            sequence_length=sequence_length,
            window_stride=window_stride,
            model_kwargs=kw,
            save_artifacts=True,
        )
        src = os.path.join(member_dir, 'model.keras')
        dst = os.path.join(model_dir, 'ensemble', f'model_{i}.keras')
        if os.path.exists(src):
            import shutil
            shutil.copy2(src, dst)
            paths.append(dst)

    member0_scaler = os.path.join(model_dir, 'ensemble', 'member_0', 'scaler.npz')
    if os.path.exists(member0_scaler):
        import shutil
        shutil.copy2(member0_scaler, os.path.join(model_dir, 'ensemble', 'scaler.npz'))
    np.savez(os.path.join(model_dir, 'ensemble', 'registry.npz'), paths=np.array(paths, dtype=object))
    print(f'Temporal ensemble registry: {len(paths)} members')
    return paths

def train_ensemble_from_csv(csv_path: str, output_dir: str, n_models: int, epochs: int, batch_size: int,
                             allow_inputs_as_targets: bool = False, validation_split: float = DEFAULT_VAL_SPLIT,
                             test_split: float = DEFAULT_TEST_SPLIT, chronological: bool = True):
    print(f'Loading training CSV for ensemble from {csv_path}...')
    X_df, Y_df = load_training_csv(csv_path, allow_inputs_as_targets=allow_inputs_as_targets)
    n_samples = len(X_df)
    if n_samples < MIN_ROWS_TO_TRAIN:
        raise RuntimeError(f'Not enough rows to train ensemble models. Need at least {MIN_ROWS_TO_TRAIN} rows, got {n_samples}.')

    os.makedirs(output_dir, exist_ok=True)

    if n_samples >= MIN_ROWS_FOR_HOLDOUT_SPLIT and validation_split > 0.0:
        split = split_dataset(X_df, Y_df, val_frac=validation_split, test_frac=test_split, chronological=chronological)
        X_train, Y_train = split['X_train'].astype(np.float32), split['Y_train'].astype(np.float32)
    else:
        X_train, Y_train = X_df.values.astype(np.float32), Y_df.values.astype(np.float32)

    mean, std = _fit_scaler(X_train)
    Xs_train = _apply_scaler(X_train, mean, std)

    np.savez(os.path.join(output_dir, 'scaler.npz'), mean=mean, std=std)

    paths = train_ensemble(Xs_train, Y_train, n_models=n_models, epochs=epochs, batch_size=batch_size, ensemble_dir=output_dir)
    print(f'Trained {len(paths)} ensemble models in {output_dir}')
    return paths

def main():
    parser = argparse.ArgumentParser(description='Ingest NOAA/SWPC data and retrain the lunar space weather model.')
    parser.add_argument('--start', type=str, default=None, help='Start date for remote fetch (YYYY-MM-DD)')
    parser.add_argument('--end', type=str, default=None, help='End date for remote fetch (YYYY-MM-DD)')
    parser.add_argument('--nasa-key', type=str, default=None, help='NASA API key; falls back to NASA_KEY env var or DEMO_KEY')
    parser.add_argument('--extra-url', action='append', default=[], help='Additional custom source URL in the form label=url')
    parser.add_argument('--source-dir', type=str, help='Directory containing local JSON/CSV source files to ingest (generic, single-file-per-source layout)')
    parser.add_argument('--ingest-raw-dir', type=str, help='Directory of raw SWPC JSON endpoint dumps to ingest via ingest_swpc_data (e.g. data/raw)')
    parser.add_argument('--augment-if-sparse', action='store_true', help='Apply physics-informed augmentation when --ingest-raw-dir yields too few real rows for a train/val/test split')
    parser.add_argument('--local-source', action='append', default=[], help='Additional local source in the form label=path')
    parser.add_argument('--out-dir', type=str, default='data/ingested', help='Directory to write ingested canonical datasets')
    parser.add_argument('--csv', type=str, default=None, help='Path to an existing canonical training CSV to use instead of fetching/ingesting')
    parser.add_argument('--csv-output', type=str, default=None, help='Path to write a single CSV training file when ingesting remote sources')
    parser.add_argument('--train-base', action='store_true', help='Train the base Keras model after ingestion')
    parser.add_argument('--train-ensemble', action='store_true', help='Train an ensemble after ingestion')
    parser.add_argument('--epochs', type=int, default=100, help='Epochs for base model training')
    parser.add_argument('--ensemble-epochs', type=int, default=50, help='Epochs for ensemble members')
    parser.add_argument('--batch-size', type=int, default=32, help='Training batch size')
    parser.add_argument('--n-models', type=int, default=3, help='Number of ensemble members')
    parser.add_argument('--validation-split', type=float, default=DEFAULT_VAL_SPLIT, help='validation split for training')
    parser.add_argument('--test-split', type=float, default=DEFAULT_TEST_SPLIT, help='test split for evaluation')
    parser.add_argument('--random-split', action='store_true', help='Use a random (rather than chronological) train/val/test split')
    parser.add_argument('--model-dir', type=str, default='saved_model', help='Directory to save/load the trained model and scaler')
    parser.add_argument('--parquet', action='store_true', help='Write ingested output as parquet chunks instead of CSV')
    args = parser.parse_args()

    nasa_key = args.nasa_key or os.environ.get('NASA_KEY', 'DEMO_KEY')
    extra_urls = {}
    for item in args.extra_url:
        if '=' in item:
            key, url = item.split('=', 1)
            extra_urls[key] = url

    local_sources = {}
    if args.source_dir:
        source_path = Path(args.source_dir)
        if not source_path.is_dir():
            raise RuntimeError(f'--source-dir must be a directory: {args.source_dir}')
        for path in sorted(source_path.glob('*.json')) + sorted(source_path.glob('*.csv')):
            label = path.stem
            if label in local_sources:
                label = f'{label}_{len(local_sources)}'
            local_sources[label] = str(path)

    for item in args.local_source:
        if '=' in item:
            key, path = item.split('=', 1)
            local_sources[key] = path

    if args.csv:
        csv_path = args.csv
    elif args.ingest_raw_dir:
        csv_path = ingest_raw_swpc_dir(args.ingest_raw_dir, args.out_dir, augment_if_sparse=args.augment_if_sparse)
    else:
        out_paths = fetch_and_ingest(args.start, args.end, nasa_key, extra_urls, args.out_dir, local_sources=local_sources or None, parquet=args.parquet)
        csv_path = out_paths[0]
        if args.csv_output:
            if args.parquet:
                raise RuntimeError('CSV output cannot be used with parquet ingestion.')
            csv_path = args.csv_output
            os.makedirs(os.path.dirname(csv_path) or '.', exist_ok=True)
            with open(out_paths[0], 'rb') as src, open(csv_path, 'wb') as dst:
                dst.write(src.read())
            print(f'Copied ingested dataset to {csv_path}')

    if args.train_base:
        metrics = train_base_model(
            csv_path, args.model_dir, epochs=args.epochs, batch_size=args.batch_size,
            validation_split=args.validation_split, test_split=args.test_split,
            chronological=not args.random_split,
        )
        print('Base model training metrics:', metrics)

    if args.train_ensemble:
        ensemble_paths = train_ensemble_from_csv(
            csv_path, os.path.join(args.model_dir, 'ensemble'), n_models=args.n_models,
            epochs=args.ensemble_epochs, batch_size=args.batch_size,
            validation_split=args.validation_split, test_split=args.test_split,
            chronological=not args.random_split,
        )
        print('Ensemble paths:')
        for p in ensemble_paths:
            print('-', p)

    print('Training pipeline complete.')

if __name__ == '__main__':
    main()
