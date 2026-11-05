#!/usr/bin/env python3
"""Kaggle GPU entrypoint for LIPAS Train4 GO-NIGHT ladder (T4a/T4b/T4c).

Hard rules:
- Prefer Kaggle GPU. Refuse local train unless ALLOW_TRAIN4=1.
- Gate: held-out test_rmse must beat train2 4.9685 to promote.
- Radiation ML blend must stay > 0 (never zero as a 'fix').
"""
from __future__ import annotations

import argparse
import json
import os
import random
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if not (ROOT / 'training_pipeline.py').exists():
    # Flat Kaggle pack: this file may live at repo root as train4_kaggle.py
    ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault('TF_CPP_MIN_LOG_LEVEL', '2')
os.environ.setdefault('MPLCONFIGDIR', '/tmp/mpl')

TRAIN2_RMSE = 4.9685
DEFAULT_CSV = 'data/ingested_extended/train7_training_locked_y_ext_drivers.csv'
BANNED_LABEL_CSV = '1784367035'


def _on_kaggle() -> bool:
    return Path('/kaggle/working').exists() or bool(os.environ.get('KAGGLE_KERNEL_RUN_TYPE'))


def _set_seeds(seed: int, determinism: bool = True) -> None:
    os.environ['PYTHONHASHSEED'] = str(seed)
    if determinism:
        os.environ.setdefault('TF_DETERMINISTIC_OPS', '1')
    random.seed(seed)
    try:
        import numpy as np
        np.random.seed(seed)
    except Exception:
        pass
    try:
        import tensorflow as tf
        tf.random.set_seed(seed)
        if determinism:
            try:
                tf.config.experimental.enable_op_determinism()
                print('TF op determinism: enabled (best-effort)')
            except Exception as e:
                print('TF op determinism: unavailable', e)
    except Exception:
        pass


def _load_cfg(path: Path) -> dict:
    return json.loads(path.read_text()) if path.exists() else {}


def _resolve_csv(cli_csv: str | None, cfg: dict) -> str:
    candidates = []
    if cli_csv:
        candidates.append(Path(cli_csv))
        candidates.append(ROOT / cli_csv)
    pinned = (cfg.get('training') or {}).get('csv_pinned') or DEFAULT_CSV
    candidates.extend([ROOT / pinned, Path(pinned)])
    for cand in candidates:
        if cand.exists():
            if BANNED_LABEL_CSV in cand.name and 'train7' not in cand.name and 'train4' not in cand.name:
                raise SystemExit(f'Refusing label-drift CSV: {cand}')
            return str(cand)
    raise SystemExit(f'Train4 CSV missing (wanted {pinned})')


def _write_blend(model_dir: Path, weights: list[float]) -> None:
    import numpy as np
    model_dir.mkdir(parents=True, exist_ok=True)
    arr = np.asarray(weights, dtype=np.float64)
    if arr.shape != (6,) or not (arr > 0).all():
        raise SystemExit(f'Refuse blend without all channels > 0: {weights}')
    np.save(model_dir / 'blend_weights.npy', arr)
    print('Wrote blend_weights', arr.tolist())


def _apply_residual_targets(df, residual_channels, mode: str = 'persistence_x'):
    """Replace selected Y channels with residual vs persistence (X hazard cols)."""
    import numpy as np
    import pandas as pd
    df = df.copy()
    target_cols = [
        'target_solar_activity', 'target_radiation_mSv', 'target_temperature_C',
        'target_moonquakes_per_day', 'target_meteor_flux_1e15', 'target_dust_g_cm3',
    ]
    x_cols = [
        'solar_activity', 'radiation_mSv', 'temperature_C',
        'moonquakes_per_day', 'meteor_flux_1e15', 'dust_g_cm3',
    ]
    for i in residual_channels:
        if mode != 'persistence_x':
            raise SystemExit(f'Unknown residual_mode {mode}')
        y = df[target_cols[i]].to_numpy(dtype=np.float64)
        x = df[x_cols[i]].to_numpy(dtype=np.float64)
        df[target_cols[i]] = (y - x).astype(np.float32)
        print(f'Residual target ch{i} ({target_cols[i]}): mean={float(np.mean(y-x)):.4f} std={float(np.std(y-x)):.4f}')
    return df


def cheap_checks(csv_path: str, out_dir: Path) -> dict:
    """Fast probes: residual ridge skill + channel std audit (no full retrain)."""
    import numpy as np
    import pandas as pd
    from sklearn.linear_model import Ridge
    from sklearn.model_selection import train_test_split

    out_dir.mkdir(parents=True, exist_ok=True)
    df = pd.read_csv(csv_path)
    feature_cols = [
        'solar_activity', 'radiation_mSv', 'temperature_C', 'moonquakes_per_day',
        'meteor_flux_1e15', 'dust_g_cm3', 'lat', 'lon', 'local_solar_time',
        'hour_of_day', 'day_of_month', 'month_of_year', 'solar_wind_speed',
        'solar_wind_density', 'imf_bz', 'kp_index', 'regolith_depth', 'thermal_inertia',
    ]
    target_cols = [
        'target_solar_activity', 'target_radiation_mSv', 'target_temperature_C',
        'target_moonquakes_per_day', 'target_meteor_flux_1e15', 'target_dust_g_cm3',
    ]
    missing = [c for c in feature_cols + target_cols if c not in df.columns]
    if missing:
        raise SystemExit(f'cheap_checks missing cols: {missing}')

    # Subsample for speed
    n = min(len(df), 80000)
    sub = df.sample(n=n, random_state=42) if len(df) > n else df
    X = sub[feature_cols].to_numpy(dtype=np.float64)
    report = {'n_rows_used': int(n), 'channels': {}, 'recommend_retrain': False}
    for i, name in enumerate(target_cols):
        y = sub[name].to_numpy(dtype=np.float64)
        phys = sub[feature_cols[i]].to_numpy(dtype=np.float64)
        resid = y - phys
        # Circular label flag: high corr(y, phys)
        corr = float(np.corrcoef(y, phys)[0, 1]) if np.std(y) > 0 and np.std(phys) > 0 else 0.0
        Xtr, Xte, rtr, rte, ytr, yte = train_test_split(X, resid, y, test_size=0.2, random_state=42)
        ridge = Ridge(alpha=1.0)
        ridge.fit(Xtr, rtr)
        pred = ridge.predict(Xte)
        rmse_resid = float(np.sqrt(np.mean((pred - rte) ** 2)))
        rmse_zero = float(np.sqrt(np.mean(rte ** 2)))  # physics-only residual RMSE
        skill = 1.0 - (rmse_resid / rmse_zero) if rmse_zero > 1e-9 else 0.0
        ch = {
            'corr_label_vs_physics_x': corr,
            'residual_ridge_rmse': rmse_resid,
            'physics_residual_rmse': rmse_zero,
            'ridge_skill_vs_physics': skill,
            'circular_risk': bool(corr > 0.98),
            'residual_has_skill': bool(skill > 0.02 and corr < 0.98),
        }
        report['channels'][name] = ch
        print(f'cheap {name}: corr={corr:.3f} ridge_skill={skill:.3f} circular={ch["circular_risk"]}')
    # Recommend residual retrain if solar or rad show skill
    solar_ok = report['channels'][target_cols[0]].get('residual_has_skill')
    rad_ok = report['channels'][target_cols[1]].get('residual_has_skill')
    report['recommend_retrain'] = bool(solar_ok or rad_ok or True)  # always climb ladder per plan
    report['recommend_residual_head'] = bool(solar_ok or rad_ok)
    out_path = out_dir / 'cheap_checks.json'
    out_path.write_text(json.dumps(report, indent=2))
    print('Wrote', out_path)
    return report


def train_stage(stage: str, cfg: dict, csv_path: str, model_dir: Path, epochs: int | None, seed: int | None) -> dict:
    import pandas as pd
    import training_pipeline as tp

    arch = cfg.get('architecture') or {}
    train = cfg.get('training') or {}
    seed = int(seed if seed is not None else train.get('seed', 42))
    epochs = int(epochs if epochs is not None else train.get('epochs', 80))
    batch_size = int(train.get('batch_size', 64))
    _set_seeds(seed, determinism=bool(train.get('tf_determinism_best_effort', True)))

    print(f'=== TRAIN4 {stage.upper()} ===')
    print('seed', seed, 'epochs', epochs, 'csv', csv_path)
    print('GPUs check via TF:')
    import tensorflow as tf
    gpus = tf.config.list_physical_devices('GPU')
    print('GPUs', gpus)
    if _on_kaggle() and not gpus:
        raise SystemExit('BLOCKER: Kaggle kernel has no GPU — refusing CPU train')

    df_override = None
    residual_channels = list(arch.get('residual_channels') or [])
    if stage.lower().startswith('t4b') or residual_channels:
        if not residual_channels:
            residual_channels = [0, 1]
        df_override = _apply_residual_targets(
            pd.read_csv(csv_path),
            residual_channels,
            mode=str(arch.get('residual_mode', 'persistence_x')),
        )

    model_kwargs = {
        'lstm_units': tuple(arch.get('lstm_units', [256, 128, 64])),
        'dense_units': tuple(arch.get('dense_units', [256, 128])),
        'dropout': tuple(arch.get('dropout', [0.3, 0.25, 0.2, 0.3, 0.25])),
        'l2_reg': float(arch.get('l2_reg', 1e-4)),
        'learning_rate': float(arch.get('learning_rate', 1e-3)),
        'clipnorm': arch.get('clipnorm', 1.0),
        'use_attention': bool(arch.get('use_attention', False)),
        'use_last_timestep_skip': bool(arch.get('use_last_timestep_skip', False)),
        'loss_type': str(arch.get('loss_type', 'channel_normalized_huber')),
        'channel_priority': list(arch.get('channel_priority', [3.0, 5.0, 1.0, 1.0, 1.5, 1.0])),
        'boost_radiation_priority': bool(arch.get('boost_radiation_priority', True)),
        'early_stopping_patience': int(train.get('early_stopping_patience', 14)),
        'use_reduce_lr_on_plateau': bool(train.get('use_reduce_lr_on_plateau', True)),
        'reduce_lr_patience': int(train.get('reduce_lr_patience', 7)),
        'reduce_lr_factor': float(train.get('reduce_lr_factor', 0.5)),
        'reduce_lr_min': float(train.get('reduce_lr_min', 1e-6)),
    }
    if arch.get('channel_loss_weights'):
        model_kwargs['channel_loss_weights'] = list(arch['channel_loss_weights'])
    if model_kwargs['use_attention'] or model_kwargs['use_last_timestep_skip']:
        print('WARN: attention/skip enabled — train3 historically failed; proceeding as configured')

    metrics = tp.train_extended_model(
        csv_path,
        str(model_dir),
        epochs=epochs,
        batch_size=batch_size,
        validation_split=float(train.get('validation_split', 0.15)),
        test_split=float(train.get('test_split', 0.15)),
        physical_bounds=bool(arch.get('physical_bounds', True)),
        sequence_length=int(arch.get('sequence_length', 72)),
        window_stride=int(arch.get('window_stride', 7)),
        model_kwargs=model_kwargs,
        use_sample_weights=bool(train.get('storm_sample_weights', True)),
        use_cosine_decay=bool(train.get('cosine_decay', False)),
        use_recency_weights=bool(train.get('recency_sample_weights', False)),
        df_override=df_override,
    )
    print('=== METRICS ===')
    print(json.dumps(metrics, indent=2, default=str))
    tr = float(metrics.get('test_rmse', 1e9))
    beats = tr < TRAIN2_RMSE
    print(f'Gate: test_rmse={tr:.4f} vs train2 {TRAIN2_RMSE} → {"BEATS" if beats else "DOES NOT BEAT"}')

    serve_blend = list((cfg.get('hybrid_serve') or {}).get('start_blend', [0.45, 0.35, 0.15, 0.15, 0.20, 0.15]))
    _write_blend(model_dir, serve_blend)

    # Annotate meta if present
    meta_path = model_dir / 'meta.json'
    if meta_path.exists():
        meta = json.loads(meta_path.read_text())
        meta['train4_stage'] = stage
        meta['beats_train2'] = beats
        meta['train2_rmse_gate'] = TRAIN2_RMSE
        meta['blend_weights'] = serve_blend
        meta['channel_ml_blend_weights'] = {
            'solar_activity': serve_blend[0],
            'radiation_mSv': serve_blend[1],
            'temperature_C': serve_blend[2],
            'moonquakes_per_day': serve_blend[3],
            'meteor_flux_1e15': serve_blend[4],
            'dust_g_cm3': serve_blend[5],
        }
        meta['blend_policy_note'] = (
            'GO-NIGHT train4: all channels ML share > 0; radiation restored (not zeroed).'
        )
        meta_path.write_text(json.dumps(meta, indent=2))

    # Optional blend fit (may overwrite weights — re-assert rad > 0 after)
    blend_py = None
    for cand in (ROOT / 'scripts' / 'fit_blend_and_calibration.py', ROOT / 'fit_blend_and_calibration.py'):
        if cand.exists():
            blend_py = cand
            break
    if blend_py is not None:
        subprocess.run(
            [sys.executable, str(blend_py), '--model-dir', str(model_dir), '--csv', csv_path, '--max-windows', '2000'],
            cwd=str(ROOT), check=False,
        )
        # Enforce radiation > 0 after fit
        import numpy as np
        bw_path = model_dir / 'blend_weights.npy'
        if bw_path.exists():
            bw = np.load(bw_path).astype(np.float64)
            if bw.shape == (6,):
                bw = np.maximum(bw, 0.05)
                if bw[1] < 0.2:
                    bw[1] = 0.25
                np.save(bw_path, bw)
                print('Post-fit blend floored (rad>=0.25, all>=0.05):', bw.tolist())

    gate = {
        'stage': stage,
        'test_rmse': tr,
        'train2_rmse': TRAIN2_RMSE,
        'beats_train2': beats,
        'target_hit': tr <= 4.0,
        'timestamp_utc': datetime.now(timezone.utc).isoformat(),
        'gpus': [str(g) for g in gpus],
    }
    (model_dir / 'train4_gate.json').write_text(json.dumps(gate, indent=2))
    return {'metrics': metrics, 'gate': gate}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--stage', type=str, default='t4a',
                    choices=['cheap', 't4a', 't4b', 't4c', 'cheap+t4a'])
    ap.add_argument('--csv', type=str, default=None)
    ap.add_argument('--model-dir', type=str, default=None)
    ap.add_argument('--config', type=str, default=None)
    ap.add_argument('--epochs', type=int, default=None)
    ap.add_argument('--seed', type=int, default=None)
    args = ap.parse_args()

    if not _on_kaggle():
        if os.environ.get('ALLOW_TRAIN4', '') != '1':
            print('REFUSE: Train4 does not auto-start locally (Kaggle GPU only).')
            print('Set ALLOW_TRAIN4=1 only for intentional non-Kaggle runs.')
            return 2
        if (ROOT / 'logs' / 'STOP_TRAIN4').exists():
            print('STOP_TRAIN4 present — refusing.')
            return 2

    stage = args.stage
    cfg_map = {
        't4a': 'configs/train4a.json',
        't4b': 'configs/train4b.json',
        't4c': 'configs/train4c.json',
        'cheap': 'configs/train4a.json',
        'cheap+t4a': 'configs/train4a.json',
    }
    cfg_path = Path(args.config) if args.config else (ROOT / cfg_map[stage.split('+')[-1] if stage != 'cheap' else 't4a'])
    if not cfg_path.exists():
        # Flat pack may place json at root
        alt = ROOT / cfg_path.name
        cfg_path = alt if alt.exists() else cfg_path
    cfg = _load_cfg(cfg_path)
    csv_path = _resolve_csv(args.csv, cfg)

    default_dir = (cfg.get('training') or {}).get('model_dir_default', f'saved_model_train4{stage[-1] if stage[-1].isalpha() else "a"}')
    if stage.startswith('cheap') and 't4' not in stage:
        default_dir = 'logs/overnight_improve/train4/cheap'
    model_dir = Path(args.model_dir) if args.model_dir else (Path('/kaggle/working') / Path(default_dir).name if _on_kaggle() else ROOT / default_dir)

    print('ROOT', ROOT)
    print('stage', stage, 'config', cfg_path, 'exists', cfg_path.exists())
    print('csv', csv_path)
    print('model_dir', model_dir)

    if stage in ('cheap', 'cheap+t4a'):
        cheap_out = Path('/kaggle/working/cheap_checks') if _on_kaggle() else (ROOT / 'logs/overnight_improve/train4/cheap')
        cheap_checks(csv_path, cheap_out)
        if stage == 'cheap':
            return 0

    train_name = 't4a' if stage == 'cheap+t4a' else stage
    result = train_stage(train_name, cfg, csv_path, model_dir, args.epochs, args.seed)
    print('DONE', json.dumps(result['gate'], indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
