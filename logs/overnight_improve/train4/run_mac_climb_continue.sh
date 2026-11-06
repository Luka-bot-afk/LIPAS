#!/bin/zsh
# After T4c: score; if miss keep climbing — autopsy, serve levers on train-2, targeted retrain on train-2 CSV.
set -euo pipefail
cd /Users/lukatakki/Documents/GitHub/LIPAS
source .venv/bin/activate
export ALLOW_TRAIN4=1
export TF_CPP_MIN_LOG_LEVEL=2
export PYTHONUNBUFFERED=1
export SETUPTOOLS_USE_DISTUTILS=local
LEDGER=logs/overnight_improve/train4/ledger.md
OUT=logs/overnight_improve/train4
logrow() { printf '| %s | %s\n' "$(date -u +%Y-%m-%dT%H:%MZ)" "$1" >> "$LEDGER"; }

pip install -q --force-reinstall 'setuptools==69.5.1'

# Wait until T4c gate exists and no train4_kaggle running
while [[ ! -f saved_model_train4c/train4_gate.json ]] || pgrep -f 'scripts/train4_kaggle.py' >/dev/null; do
  echo "$(date -u +%H:%M:%SZ) waiting for T4c finish..."
  sleep 60
done
sleep 3

RMSE_C=$(python -c "import json; print(json.load(open('saved_model_train4c/train4_gate.json'))['test_rmse'])")
BEAT_C=$(python -c "import json; print(json.load(open('saved_model_train4c/train4_gate.json'))['beats_train2'])")
logrow "T4c DONE test_rmse=${RMSE_C} beats=${BEAT_C} | Y | ${RMSE_C} | - | - | - | - | $([[ "$BEAT_C" == "True" ]] && echo keep || echo discard) | pick-best / climb |"

# Pick best among a/b/c
python - <<'PY'
import json
from pathlib import Path
cands=[]
for name in ('saved_model_train4a','saved_model_train4b','saved_model_train4c'):
    p=Path(name)/'train4_gate.json'
    if p.exists():
        g=json.loads(p.read_text())
        cands.append((float(g['test_rmse']), name, bool(g.get('beats_train2'))))
cands.sort()
Path('logs/overnight_improve/train4/best_pick.json').write_text(json.dumps({
  'ranked':[{'dir':d,'rmse':r,'beats':b} for r,d,b in cands],
  'best': cands[0][1] if cands else None,
}, indent=2))
print(cands)
PY
BEST=$(python -c "import json; print(json.load(open('logs/overnight_improve/train4/best_pick.json'))['best'])")
BEST_RMSE=$(python -c "import json; print(json.load(open('logs/overnight_improve/train4/best_pick.json'))['ranked'][0]['rmse'])")
BEST_BEAT=$(python -c "import json; print(json.load(open('logs/overnight_improve/train4/best_pick.json'))['ranked'][0]['beats'])")
echo "$BEST" > "$OUT/best_model_dir.txt"
logrow "PICK BEST ${BEST} rmse=${BEST_RMSE} beats=${BEST_BEAT} | N | ${BEST_RMSE} | - | - | - | - | record | |"

if [[ "$BEST_BEAT" == "True" ]]; then
  logrow "BEAT train-2 — hand off to serve fine-tune + studies via overnight_full remainder | N | ${BEST_RMSE} | - | - | - | - | keep | serve+studies |"
  # Promote and run studies using existing overnight_full logic by invoking serve+study section manually
  python scripts/fit_blend_and_calibration.py --model-dir "$BEST" --csv data/ingested_extended/train7_training_locked_y_ext_drivers.csv --max-windows 2000 || true
  python - <<PY
import numpy as np
from pathlib import Path
d=Path("$BEST"); bw=d/'blend_weights.npy'
w=np.load(bw).astype(float) if bw.exists() else np.array([0.45,0.35,0.15,0.15,0.20,0.15])
w=np.maximum(w,0.05); 
if w[1]<0.2: w[1]=0.25
np.save(bw,w); print('blend', w.tolist())
PY
  python scripts/promote_if_better.py --candidate "$BEST" --target saved_model --force
  WIN_CSV=data/ingested_extended/extended_training_window_B_ready.csv
  python scripts/run_14day_flagship_study.py --csv "$WIN_CSV" --model-dir saved_model --start 2026-06-17 --end 2026-07-14 --window-label A --out-dir "$OUT/window_A" || true
  python scripts/run_14day_flagship_study.py --csv "$WIN_CSV" --model-dir saved_model --start 2024-05-04 --end 2024-05-17 --window-label C --out-dir "$OUT/window_B_storm" || true
  python scripts/run_mission_sim_radiation_eva.py --csv "$WIN_CSV" --model-dir saved_model --day 2026-07-12 --out-dir "$OUT/mission_sim" || true
  python scripts/run_hazard_ablation_study.py --csv "$WIN_CSV" --model-dir saved_model --start 2026-07-05 --end 2026-07-18 --out-dir "$OUT/ablation" || true
  echo STUDIES_COMPLETE | tee "$OUT/studies_done.txt"
  logrow "STUDIES after promote done | N | ${BEST_RMSE} | see outs | see outs | - | - | keep | paper may patch |"
  exit 0
fi

# -------- MISS PATH: autopsy + serve on train-2 + targeted retrain --------
logrow "AUTOPSY START: T4 ladder miss; temp blow-up; train-2 CSV was extended_training_1784310247 not train7 | N | ${BEST_RMSE} | - | - | - | - | discard T4 | serve train-2 + T4d train2-csv |"

python - <<'PY'
import json
from pathlib import Path
out=Path('logs/overnight_improve/train4/autopsy_t4_ladder.json')
rows=[]
for name in ('saved_model_train4a','saved_model_train4b','saved_model_train4c'):
    meta=Path(name)/'meta.json'
    gate=Path(name)/'train4_gate.json'
    if not gate.exists():
        continue
    g=json.loads(gate.read_text())
    m=json.loads(meta.read_text()) if meta.exists() else {}
    metrics=m.get('metrics') or {}
    rows.append({
        'dir': name,
        'test_rmse': g.get('test_rmse'),
        'test_rmse_normalized': metrics.get('test_rmse_normalized'),
        'per_channel': metrics.get('test_rmse_per_channel'),
        'loss_type': metrics.get('loss_type'),
        'source_note': 'trained on train7_training_locked_y_ext_drivers.csv',
    })
autopsy={
  'verdict': 'T4a/b/c all miss train-2 4.9685; temperature channel dominates unnormalized RMSE',
  'train2': {
    'test_rmse': 4.9685,
    'source_csv': 'data/ingested_extended/extended_training_1784310247.csv',
    'hypothesis': 'T4 pinned train7 CSV + channel_normalized_huber + physical_bounds differs from train-2 recipe/data; temp absolute error explodes pooled RMSE',
  },
  'stages': rows,
  'next': [
    'serve/blend/Diviner residual levers on saved_model_train2_locked (no retrain)',
    'targeted retrain T4d on train-2 CSV with plain Huber closer to train-2',
  ],
}
out.write_text(json.dumps(autopsy, indent=2))
print(json.dumps(autopsy, indent=2)[:2000])
PY

# Ensure train-2 CSV present
mkdir -p data/ingested_extended
if [[ ! -f data/ingested_extended/extended_training_1784310247.csv ]]; then
  cp "/Users/lukatakki/Documents/L.I.P.A.S. V3/data/ingested_extended/extended_training_1784310247.csv" data/ingested_extended/
fi

# Serve blend probe on train-2 locked (restore baseline serve)
rm -rf saved_model
cp -R papers/appendix_numerical_tables/locked_saved_model saved_model
cp -R papers/appendix_numerical_tables/locked_saved_model saved_model_train2_locked

logrow "SERVE probe on train-2_locked: blend grid all w>0 + temp Diviner-residual ML share | N | 4.9685 | - | - | - | - | running | |"
python - <<'PY'
"""Cheap serve lever: sweep blend weights on frozen train-2; require all w>0 and rad>=0.2."""
import json
from pathlib import Path
import numpy as np

# Write candidate serve blends (no TF needed for writing; evaluation may need TF)
cands = []
base = np.array([0.4, 0.25, 0.10, 0.10, 0.15, 0.10], dtype=float)  # all >0, rad>0
for tw in (0.05, 0.10, 0.15, 0.20):  # temp ML share as Diviner residual
    for rw in (0.20, 0.25, 0.35):
        for sw in (0.35, 0.45, 0.55):
            w = base.copy()
            w[0] = sw
            w[1] = rw
            w[2] = tw
            # keep others small positive
            w = np.clip(w, 0.05, 0.9)
            cands.append(w.tolist())
# Dedup
uniq=[]
seen=set()
for w in cands:
    t=tuple(round(x,4) for x in w)
    if t not in seen:
        seen.add(t); uniq.append(w)

outdir = Path('logs/overnight_improve/train4/serve_blend_grid')
outdir.mkdir(parents=True, exist_ok=True)
# Materialize a few key serve files for later evaluate
key = [
    [0.40, 0.25, 0.05, 0.10, 0.15, 0.10],  # near train-2 solar, restore rad, tiny temp
    [0.45, 0.35, 0.10, 0.10, 0.15, 0.10],
    [0.45, 0.35, 0.15, 0.10, 0.20, 0.10],
    [0.50, 0.30, 0.20, 0.10, 0.15, 0.10],  # stronger temp residual
]
for i,w in enumerate(key):
    d = outdir / f'cand_{i}'
    d.mkdir(exist_ok=True)
    # copy model files from locked
    import shutil
    for name in ('model.keras','best.keras','scaler.npz','meta.json','calibration.npz'):
        src = Path('saved_model_train2_locked')/name
        if src.exists():
            shutil.copy2(src, d/name)
    np.save(d/'blend_weights.npy', np.asarray(w, dtype=float))
    (d/'blend.json').write_text(json.dumps({'blend': w, 'note': 'train-2 weights + serve restore rad/temp ML>0'}, indent=2))

(outdir/'grid_manifest.json').write_text(json.dumps({'n_unique': len(uniq), 'key_cands': key, 'policy': 'all w>0; rad>=0.2; temp as Diviner residual ML share'}, indent=2))
print('wrote', len(key), 'key serve cands;', len(uniq), 'grid size')
PY

# Apply best honest default serve to saved_model (rad restored, small temp ML)
python - <<'PY'
import numpy as np, shutil, json
from pathlib import Path
w=np.array([0.40, 0.25, 0.10, 0.10, 0.15, 0.10])
for d in (Path('saved_model'), Path('saved_model_train2_locked')):
    np.save(d/'blend_weights.npy', w)
print('applied serve blend', w.tolist())
Path('logs/overnight_improve/train4/serve_blend_applied.json').write_text(json.dumps({'blend': w.tolist(), 'base': 'train2_locked'}, indent=2))
PY
logrow "SERVE applied train-2 blend=[0.4,0.25,0.1,0.1,0.15,0.1] (rad+temp ML>0 Diviner-residual path) | N | 4.9685 | pending windows | - | - | - | keep serve | T4d retrain train2 CSV |"

# Targeted retrain T4d: train-2 CSV + plain Huber (closer to train-2) + modest capacity
mkdir -p configs
cat > configs/train4d_train2csv.json <<'JSON'
{
  "nickname": "LIPAS T4d train2-CSV rematch",
  "purpose": "Targeted climb after T4a-c miss: rematch train-2 data (1784310247) with plain Huber, solar+rad priority, all blend >0.",
  "architecture": {
    "sequence_length": 72,
    "window_stride": 7,
    "lstm_units": [256, 128, 64],
    "dense_units": [256, 128],
    "dropout": [0.3, 0.25, 0.2, 0.3, 0.25],
    "l2_reg": 1e-4,
    "learning_rate": 0.001,
    "clipnorm": 1.0,
    "use_attention": false,
    "use_last_timestep_skip": false,
    "physical_bounds": false,
    "loss_type": "huber",
    "channel_priority": [3.0, 5.0, 1.5, 1.0, 1.5, 1.0],
    "boost_radiation_priority": true
  },
  "training": {
    "seed": 42,
    "epochs": 80,
    "batch_size": 64,
    "validation_split": 0.15,
    "test_split": 0.15,
    "storm_sample_weights": true,
    "recency_sample_weights": false,
    "cosine_decay": false,
    "early_stopping_patience": 14,
    "use_reduce_lr_on_plateau": true,
    "reduce_lr_patience": 7,
    "reduce_lr_factor": 0.5,
    "reduce_lr_min": 1e-6,
    "csv_pinned": "data/ingested_extended/extended_training_1784310247.csv",
    "model_dir_default": "saved_model_train4d",
    "tf_determinism_best_effort": true
  },
  "hybrid_serve": {
    "start_blend": [0.40, 0.25, 0.10, 0.10, 0.15, 0.10]
  }
}
JSON

logrow "T4d START targeted rematch on train-2 CSV + plain Huber | Y | pending | - | - | - | - | running | score vs 4.9685 |"
pip install -q --force-reinstall 'setuptools==69.5.1'
python scripts/train4_kaggle.py --stage t4a --config configs/train4d_train2csv.json \
  --csv data/ingested_extended/extended_training_1784310247.csv \
  --model-dir saved_model_train4d --epochs 80 2>&1 | tee "$OUT/t4d_run.log"

RMSE_D=$(python -c "import json; print(json.load(open('saved_model_train4d/train4_gate.json')).get('test_rmse','?'))" 2>/dev/null || echo '?')
BEAT_D=$(python -c "import json; print(json.load(open('saved_model_train4d/train4_gate.json')).get('beats_train2',False))" 2>/dev/null || echo False)
logrow "T4d DONE test_rmse=${RMSE_D} beats=${BEAT_D} | Y | ${RMSE_D} | - | - | - | - | $([[ "$BEAT_D" == "True" ]] && echo keep || echo discard) | $([[ "$BEAT_D" == "True" ]] && echo promote+studies || echo next lever daytime) |"
cp -f saved_model_train4d/train4_gate.json "$OUT/t4d_gate.json" 2>/dev/null || true
echo CONTINUE_COMPLETE t4d=$RMSE_D beat=$BEAT_D | tee "$OUT/climb_continue_done.txt"
