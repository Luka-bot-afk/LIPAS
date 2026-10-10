
"""LIPAS."""
import argparse
import glob
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from training_pipeline import train_extended_model, train_temporal_ensemble

def _load_cfg(path: Path | None):
    if path is None:
        path = ROOT / 'configs' / 'hybrid_training_config.json'
    if path.exists():
        return json.loads(path.read_text())
    return {}

def main():
    pre = argparse.ArgumentParser(add_help=False)
    pre.add_argument('--config', type=str, default=None)
    pre_args, _ = pre.parse_known_args()
    cfg = _load_cfg(Path(pre_args.config) if pre_args.config else None)
    arch = cfg.get('architecture', {})
    train_cfg = cfg.get('training', {})

    parser = argparse.ArgumentParser()
    parser.add_argument('--config', type=str, default=None, help=                                )
    parser.add_argument('--csv', type=str, default=None, help='Extended-schema training CSV (defaults to newest in data/ingested_extended/)')
    parser.add_argument('--model-dir', type=str, default='saved_model_extended')
    parser.add_argument('--epochs', type=int, default=int(train_cfg.get('epochs', 60)))
    parser.add_argument('--batch-size', type=int, default=int(train_cfg.get('batch_size', 64)))
    parser.add_argument('--sequence-length', type=int, default=int(arch.get('sequence_length', cfg.get('sequence_length', 72))))
    parser.add_argument('--window-stride', type=int, default=int(arch.get('window_stride', cfg.get('window_stride', 7))))
    parser.add_argument('--validation-split', type=float, default=float(train_cfg.get('validation_split', 0.15)))
    parser.add_argument('--test-split', type=float, default=float(train_cfg.get('test_split', 0.15)))
    parser.add_argument('--force-dense', action='store_true')
    parser.add_argument('--no-physical-bounds', action='store_true')
    parser.add_argument('--no-attention', action='store_true')
    parser.add_argument('--no-skip', action='store_true')
    parser.add_argument('--no-sample-weights', action='store_true')
    parser.add_argument('--no-cosine-decay', action='store_true')
    parser.add_argument('--no-recency-weights', action='store_true')
    parser.add_argument('--ensemble', action='store_true', help='Also train temporal ensemble members')
    parser.add_argument('--n-ensemble', type=int, default=int(cfg.get('rigor', {}).get('ensemble_members', cfg.get('ensemble', {}).get('n_members', 3))))
    parser.add_argument('--lstm-units', type=str, default=None,
                         help='Comma-separated 3 ints, e.g. "256,96,32" (from hp_search.py best_params)')
    parser.add_argument('--dense-units', type=str, default=None,
                         help='Comma-separated 2 ints, e.g. "192,96"')
    parser.add_argument('--dropout', type=float, default=None,
                         help='Single dropout rate applied to all 5 dropout layers')
    parser.add_argument('--l2-reg', type=float, default=None)
    parser.add_argument('--learning-rate', type=float, default=None)
    parser.add_argument('--boost-radiation', action='store_true')
    parser.add_argument('--channel-priority', type=str, default=None,
                         help='Comma-separated 6 floats for channel loss priority')
    args = parser.parse_args()

    csv_path = args.csv
    if csv_path is None:
        candidates = sorted(glob.glob('data/ingested_extended/extended_training_*.csv'), key=os.path.getmtime)
        if not candidates:
            raise SystemExit('No extended training CSV found; run scripts/build_extended_dataset.py first.')
        csv_path = candidates[-1]

    model_kwargs = {
        'lstm_units': tuple(arch.get('lstm_units', [256, 128, 64])),
        'dense_units': tuple(arch.get('dense_units', [256, 128])),
        'dropout': tuple(arch.get('dropout', [0.3, 0.25, 0.2, 0.3, 0.25])),
        'l2_reg': float(arch.get('l2_reg', 1e-4)),
        'learning_rate': float(arch.get('learning_rate', 1e-3)),
        'clipnorm': float(arch.get('clipnorm', 1.0)),
        'use_attention': bool(arch.get('use_attention', True)) and not args.no_attention,
        'use_last_timestep_skip': bool(arch.get('use_last_timestep_skip', True)) and not args.no_skip,
        'boost_radiation_priority': bool(args.boost_radiation or train_cfg.get('boost_radiation', False)),
        'early_stopping_patience': int(train_cfg.get('early_stopping_patience', 14)),
    }
    if train_cfg.get('channel_priority'):
        model_kwargs['channel_priority'] = list(train_cfg['channel_priority'])
    if args.channel_priority:
        model_kwargs['channel_priority'] = [float(x) for x in args.channel_priority.split(',')]
    if args.lstm_units:
        model_kwargs['lstm_units'] = tuple(int(x) for x in args.lstm_units.split(','))
    if args.dense_units:
        model_kwargs['dense_units'] = tuple(int(x) for x in args.dense_units.split(','))
    if args.dropout is not None:
        model_kwargs['dropout'] = (args.dropout,) * 5
    if args.l2_reg is not None:
        model_kwargs['l2_reg'] = args.l2_reg
    if args.learning_rate is not None:
        model_kwargs['learning_rate'] = args.learning_rate

    metrics = train_extended_model(
        csv_path=csv_path,
        model_dir=args.model_dir,
        epochs=args.epochs,
        batch_size=args.batch_size,
        sequence_length=args.sequence_length,
        window_stride=args.window_stride,
        validation_split=args.validation_split,
        test_split=args.test_split,
        physical_bounds=not args.no_physical_bounds,
        force_dense=args.force_dense,
        model_kwargs=model_kwargs,
        use_sample_weights=not args.no_sample_weights,
        use_cosine_decay=not args.no_cosine_decay,
        use_recency_weights=not args.no_recency_weights,
    )
    print('Final metrics:', metrics)

    if args.ensemble:
        paths = train_temporal_ensemble(
            csv_path=csv_path,
            model_dir=args.model_dir,
            n_models=args.n_ensemble,
            epochs=max(30, args.epochs // 2),
            batch_size=args.batch_size,
            sequence_length=args.sequence_length,
            window_stride=args.window_stride,
            base_model_kwargs=model_kwargs,
        )
        print('Ensemble paths:', paths)

if __name__ == '__main__':
    main()
