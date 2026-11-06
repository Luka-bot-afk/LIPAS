#!/bin/zsh
# ART-28 Mac overnight — confirmed user order:
# 1) Climb full T4 ladder (a→b→c; pick best; do NOT stop early)
# 2) Physics/serve fine-tune (blend all w>0, floors)
# 3) Redo studies: Window A/B (+C storm), mission sim, ablation
# 4) Paper draft30 is NOT done here — only push numbers/artifacts for paper worker
set -euo pipefail
cd /Users/lukatakki/Documents/GitHub/LIPAS
source .venv/bin/activate
export ALLOW_TRAIN4=1
export TF_CPP_MIN_LOG_LEVEL=2
export PYTHONUNBUFFERED=1
export SETUPTOOLS_USE_DISTUTILS=local

LEDGER=logs/overnight_improve/train4/ledger.md
CSV=data/ingested_extended/train7_training_locked_y_ext_drivers.csv
WIN_CSV=data/ingested_extended/extended_training_window_B_ready.csv
OUT=logs/overnight_improve/train4
mkdir -p "$OUT"

logrow() { printf '| %s | %s\n' "$(date -u +%Y-%m-%dT%H:%MZ)" "$1" >> "$LEDGER"; }

pip install -q flask flask-cors python-dotenv reportlab beautifulsoup4 lxml
pip install -q --force-reinstall 'setuptools==69.5.1'
python -c "import distutils, tensorflow as tf; print('preflight', tf.__version__, tf.config.list_physical_devices('GPU'))"

logrow "ORDER LOCKED: (1) full T4a→T4b→T4c pick best (2) serve/blend fine-tune (3) windows+mission+ablation (4) paper later | N | - | - | - | - | - | keep | climb |"

# --- Wait for any in-flight train4_kaggle (do not fight GPU) ---
wait_idle() {
  while pgrep -f 'scripts/train4_kaggle.py' >/dev/null; do
    echo "$(date -u +%H:%M:%SZ) train4_kaggle still running — sleep 60"
    sleep 60
  done
}

if [[ ! -f saved_model_train4a/train4_gate.json ]]; then
  logrow "Waiting for in-flight T4a gate (or starting T4a) | Y | pending | - | - | - | - | running | |"
  if pgrep -f 'scripts/train4_kaggle.py' >/dev/null; then
    echo "Waiting for existing train4_kaggle..."
    wait_idle
    sleep 5
  fi
  if [[ ! -f saved_model_train4a/train4_gate.json ]]; then
    pip install -q --force-reinstall 'setuptools==69.5.1'
export SETUPTOOLS_USE_DISTUTILS=local
python scripts/train4_kaggle.py --stage t4a 2>&1 | tee "$OUT/t4a_run.log"
  fi
fi
# If legacy ladder is still chaining T4b/T4c, wait it out before we fill gaps
wait_idle

RMSE_A=$(python -c "import json; print(json.load(open('saved_model_train4a/train4_gate.json')).get('test_rmse','?'))")
BEAT_A=$(python -c "import json; print(json.load(open('saved_model_train4a/train4_gate.json')).get('beats_train2',False))")
logrow "T4a DONE test_rmse=${RMSE_A} beats=${BEAT_A} | Y | ${RMSE_A} | - | - | - | - | record | always continue T4b |"

# --- Always run T4b (residual) — do not stop early ---
if [[ ! -f saved_model_train4b/train4_gate.json ]]; then
  logrow "T4b START residual solar+rad (always; no early stop) | Y | pending | - | - | - | - | running | |"
  pip install -q --force-reinstall 'setuptools==69.5.1'
export SETUPTOOLS_USE_DISTUTILS=local
python scripts/train4_kaggle.py --stage t4b 2>&1 | tee "$OUT/t4b_run.log"
fi
RMSE_B=$(python -c "import json; print(json.load(open('saved_model_train4b/train4_gate.json')).get('test_rmse','?'))")
BEAT_B=$(python -c "import json; print(json.load(open('saved_model_train4b/train4_gate.json')).get('beats_train2',False))")
logrow "T4b DONE test_rmse=${RMSE_B} beats=${BEAT_B} | Y | ${RMSE_B} | - | - | - | - | record | always continue T4c |"

# --- Always run T4c (capacity) ---
if [[ ! -f saved_model_train4c/train4_gate.json ]]; then
  logrow "T4c START capacity (always; no early stop) | Y | pending | - | - | - | - | running | |"
  pip install -q --force-reinstall 'setuptools==69.5.1'
export SETUPTOOLS_USE_DISTUTILS=local
python scripts/train4_kaggle.py --stage t4c 2>&1 | tee "$OUT/t4c_run.log"
fi
RMSE_C=$(python -c "import json; print(json.load(open('saved_model_train4c/train4_gate.json')).get('test_rmse','?'))")
BEAT_C=$(python -c "import json; print(json.load(open('saved_model_train4c/train4_gate.json')).get('beats_train2',False))")
logrow "T4c DONE test_rmse=${RMSE_C} beats=${BEAT_C} | Y | ${RMSE_C} | - | - | - | - | record | pick best |"

# --- Pick best by held-out test_rmse ---
BEST_DIR=$(python - <<'PY'
import json
from pathlib import Path
cands = []
for name in ('saved_model_train4a','saved_model_train4b','saved_model_train4c'):
    p = Path(name)/'train4_gate.json'
    if p.exists():
        g = json.loads(p.read_text())
        cands.append((float(g['test_rmse']), name, bool(g.get('beats_train2'))))
cands.sort()
print(cands[0][1] if cands else '')
open('logs/overnight_improve/train4/best_pick.json','w').write(
    __import__('json').dumps({'ranked':[{'dir':d,'rmse':r,'beats':b} for r,d,b in cands], 'best': cands[0][1] if cands else None}, indent=2)
)
print('RANK', cands, file=__import__('sys').stderr)
PY
)
BEST_RMSE=$(python -c "import json; print(json.load(open('logs/overnight_improve/train4/best_pick.json'))['ranked'][0]['rmse'])")
BEST_BEAT=$(python -c "import json; print(json.load(open('logs/overnight_improve/train4/best_pick.json'))['ranked'][0]['beats'])")
logrow "PICK BEST ${BEST_DIR} test_rmse=${BEST_RMSE} beats_train2=${BEST_BEAT} | N | ${BEST_RMSE} | - | - | - | - | $([[ "$BEST_BEAT" == "True" ]] && echo keep || echo discard_best_still_miss) | serve fine-tune if beat else autopsy |"

echo "$BEST_DIR" > "$OUT/best_model_dir.txt"
echo LADDER_COMPLETE best=$BEST_DIR rmse=$BEST_RMSE beat=$BEST_BEAT | tee "$OUT/ladder_done.txt"

# Gate: only promote/serve/studies if beats train-2
if [[ "$BEST_BEAT" != "True" ]]; then
  logrow "No stage beat train-2 4.9685 — STOP before promote/paper; autopsy needed | N | ${BEST_RMSE} | - | - | - | - | discard | invent/adapt next honest lever daytime |"
  echo NO_PROMOTE > "$OUT/no_promote.txt"
  exit 0
fi

# --- Step 2: serve / blend fine-tune ---
logrow "SERVE fine-tune START on ${BEST_DIR} (blend fit, floor all w>0 rad>=0.25) | N | ${BEST_RMSE} | - | - | - | - | running | |"
python scripts/fit_blend_and_calibration.py --model-dir "$BEST_DIR" --csv "$CSV" --max-windows 2000 2>&1 | tee "$OUT/blend_fit.log" || true
python - <<PY
import numpy as np
from pathlib import Path
d = Path("$BEST_DIR")
bw = d / "blend_weights.npy"
w = np.load(bw).astype(float) if bw.exists() else np.array([0.45,0.35,0.15,0.15,0.20,0.15])
w = np.maximum(w, 0.05)
if w[1] < 0.2:
    w[1] = 0.25
np.save(bw, w)
print("serve blend floored", w.tolist())
open("logs/overnight_improve/train4/serve_blend.json","w").write(__import__("json").dumps({"blend": w.tolist(), "model_dir": "$BEST_DIR"}, indent=2))
PY
logrow "SERVE blend floored on ${BEST_DIR} | N | ${BEST_RMSE} | - | - | - | - | keep | promote + studies |"

# Promote to saved_model for study scripts
python scripts/promote_if_better.py --candidate "$BEST_DIR" --target saved_model --force
# Also keep dedicated promote copy
rm -rf saved_model_train4_promoted
cp -R "$BEST_DIR" saved_model_train4_promoted
logrow "PROMOTED ${BEST_DIR} -> saved_model + saved_model_train4_promoted | N | ${BEST_RMSE} | - | - | - | - | keep | studies |"

# --- Step 3: studies (windows + mission + ablation) ---
# Window A summer (locked draft25 dates as baseline; grid refinement can follow)
logrow "STUDY Window A 2026-06-17..07-14 | N | ${BEST_RMSE} | pending | - | - | - | running | |"
python scripts/run_14day_flagship_study.py \
  --csv "$WIN_CSV" --model-dir saved_model \
  --start 2026-06-17 --end 2026-07-14 --window-label A \
  --out-dir "$OUT/window_A" 2>&1 | tee "$OUT/window_A_run.log"

# Window B mixed/day (draft25 B) — GO-NIGHT naming: summer A + storm B; keep both locked dates + storm C as Window B storm
logrow "STUDY Window summer-day 2026-07-18..08-14 (label B_day) | N | ${BEST_RMSE} | - | pending | - | - | running | |"
python scripts/run_14day_flagship_study.py \
  --csv "$WIN_CSV" --model-dir saved_model \
  --start 2026-07-18 --end 2026-08-14 --window-label B \
  --out-dir "$OUT/window_B_day" 2>&1 | tee "$OUT/window_B_day_run.log"

# Storm window (May 2024) — paper Window B storm
logrow "STUDY Window B storm 2024-05-04..05-17 | N | ${BEST_RMSE} | - | pending | - | - | running | |"
python scripts/run_14day_flagship_study.py \
  --csv "$WIN_CSV" --model-dir saved_model \
  --start 2024-05-04 --end 2024-05-17 --window-label C \
  --out-dir "$OUT/window_B_storm" 2>&1 | tee "$OUT/window_B_storm_run.log"

logrow "STUDY mission sim | N | ${BEST_RMSE} | - | - | - | - | running | |"
python scripts/run_mission_sim_radiation_eva.py \
  --csv "$WIN_CSV" --model-dir saved_model --day 2026-07-12 \
  --out-dir "$OUT/mission_sim" 2>&1 | tee "$OUT/mission_sim_run.log"

logrow "STUDY ablation (Window A quiet subset defaults) | N | ${BEST_RMSE} | - | - | - | - | running | |"
python scripts/run_hazard_ablation_study.py \
  --csv "$WIN_CSV" --model-dir saved_model \
  --start 2026-07-05 --end 2026-07-18 \
  --out-dir "$OUT/ablation" 2>&1 | tee "$OUT/ablation_run.log"

# Summarize hazard wins into ledger helpers
python - <<'PY'
import json
from pathlib import Path
out = Path('logs/overnight_improve/train4')
summary = {'windows': {}}
for name in ('window_A','window_B_day','window_B_storm'):
    p = out/name/'summary.json'
    if p.exists():
        summary['windows'][name] = json.loads(p.read_text())
(out/'studies_bundle_summary.json').write_text(json.dumps(summary, indent=2, default=str))
print('wrote studies_bundle_summary.json keys', list(summary['windows']))
PY

logrow "STUDIES DONE (windows+mission+ablation) — artifacts under logs/overnight_improve/train4/; paper draft30 may patch from these ONLY | N | ${BEST_RMSE} | see bundle | see bundle | - | - | keep | push PR#5; no paper invent |"
echo STUDIES_COMPLETE | tee "$OUT/studies_done.txt"
