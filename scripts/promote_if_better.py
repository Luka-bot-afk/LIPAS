
"""LIPAS."""
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

def _rmse(meta: dict, key: str = 'test_rmse') -> float | None:
    m = (meta or {}).get('metrics') or {}
    v = m.get(key)
    return float(v) if v is not None else None

def _primary_score(meta: dict) -> tuple[float | None, str]:
    """Prefer channel-normalized RMSE when present (fair multi-hazard score)."""
    n = _rmse(meta, 'test_rmse_normalized')
    if n is not None:
        return n, 'test_rmse_normalized'
    return _rmse(meta, 'test_rmse'), 'test_rmse'

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--candidate', required=True)
    ap.add_argument('--target', default='saved_model')
    ap.add_argument('--force', action='store_true')
    args = ap.parse_args()

    cand = Path(args.candidate)
    tgt = Path(args.target)
    cand_meta = json.loads((cand / 'meta.json').read_text())
    tgt_meta = json.loads((tgt / 'meta.json').read_text()) if (tgt / 'meta.json').exists() else {}
    c_rmse, c_key = _primary_score(cand_meta)
    t_rmse, t_key = _primary_score(tgt_meta)
    print(f'candidate {c_key}={c_rmse}  (pooled test_rmse={_rmse(cand_meta)})')
    print(f'target    {t_key}={t_rmse}  (pooled test_rmse={_rmse(tgt_meta)})')
    if c_rmse is None:
        raise SystemExit('candidate meta.json missing metrics.test_rmse / test_rmse_normalized')

    if t_rmse is None:
        t_rmse = _rmse(tgt_meta)
        t_key = 'test_rmse'
        c_rmse = _rmse(cand_meta) if c_key != 'test_rmse' and _rmse(cand_meta) is not None else c_rmse
        c_key = 'test_rmse'
        print(f'fallback compare on pooled test_rmse: cand={c_rmse} tgt={t_rmse}')
    if not args.force and t_rmse is not None and c_rmse >= t_rmse:
        print('NOT promoting: candidate is not better.')
        raise SystemExit(2)

    from datetime import datetime, timezone
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    backup = tgt.parent / f'{tgt.name}_backup_pre_promote_{stamp}'
    if tgt.exists():
        shutil.copytree(tgt, backup)
        print(f'Backed up {tgt} -> {backup}')

        pointer = tgt.parent / f'{tgt.name}_backup_pre_promote'
        if pointer.exists():
            shutil.rmtree(pointer)
        shutil.copytree(backup, pointer)

    for name in ('model.keras', 'best.keras', 'best.h5', 'meta.json', 'scaler.npz', 'history.json'):
        src = cand / name
        if src.exists():
            shutil.copy2(src, tgt / name)
            print(f'copied {name}')

    for name in ('calibration.npz', 'blend_weights.npy', 'blend_and_calibration_report.json'):
        src = cand / name
        if src.exists():
            shutil.copy2(src, tgt / name)
            print(f'copied {name}')

    print('PROMOTED', cand, '->', tgt)

if __name__ == '__main__':
    main()
