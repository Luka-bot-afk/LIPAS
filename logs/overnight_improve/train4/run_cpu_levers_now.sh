#!/bin/zsh
# CPU serve/physics/archive levers NOW — overlap Metal T4c (do not wait).
# Force TF onto CPU so Metal stays with T4c.
set -euo pipefail
cd /Users/lukatakki/Documents/GitHub/LIPAS
source .venv/bin/activate
export ALLOW_TRAIN4=1
export TF_CPP_MIN_LOG_LEVEL=2
export PYTHONUNBUFFERED=1
export SETUPTOOLS_USE_DISTUTILS=local
# Hide GPU/Metal from this process
export CUDA_VISIBLE_DEVICES=""
export HIP_VISIBLE_DEVICES=""
LEDGER=logs/overnight_improve/train4/ledger.md
OUT=logs/overnight_improve/train4/cpu_levers
WIN_CSV=data/ingested_extended/extended_training_window_B_ready.csv
mkdir -p "$OUT"
logrow() { printf '| %s | %s\n' "$(date -u +%Y-%m-%dT%H:%MZ)" "$1" >> "$LEDGER"; }

pip install -q --force-reinstall 'setuptools==69.5.1'

CPU_RUN="python logs/overnight_improve/train4/run_on_cpu.py"

logrow "CPU LEVERS START NOW (parallel Metal T4c): Diviner/MEM/blend/archive on train2_locked; score Window A + storm B | N | - | pending | pending | - | - | running | overlap |"

# Ensure data
mkdir -p data/ingested_extended
[[ -f "$WIN_CSV" ]] || cp "/Users/lukatakki/Documents/L.I.P.A.S. V3/data/ingested_extended/extended_training_window_B_ready.csv" "$WIN_CSV"
[[ -f data/ingested_extended/extended_training_1784310247.csv ]] || \
  cp "/Users/lukatakki/Documents/L.I.P.A.S. V3/data/ingested_extended/extended_training_1784310247.csv" data/ingested_extended/

# Build serve candidates from locked train-2
python - <<'PY'
import json, shutil
from pathlib import Path
import numpy as np
root = Path('logs/overnight_improve/train4/cpu_levers/cands')
root.mkdir(parents=True, exist_ok=True)
src = Path('papers/appendix_numerical_tables/locked_saved_model')
# Honest serve packages: all w>0, rad>=0.2; temp=Diviner residual ML; meteor/dust physics-led
cands = {
  'L0_rad_restore':           [0.40, 0.25, 0.05, 0.05, 0.05, 0.05],
  'L1_solar_rad':             [0.45, 0.35, 0.08, 0.05, 0.10, 0.05],
  'L2_diviner_temp_resid':    [0.40, 0.30, 0.15, 0.05, 0.10, 0.05],
  'L3_physics_heavy':         [0.35, 0.25, 0.05, 0.05, 0.05, 0.05],
  'L4_balanced':              [0.40, 0.30, 0.12, 0.10, 0.15, 0.10],
  'L5_seasonal_meteor_light': [0.40, 0.30, 0.10, 0.08, 0.05, 0.05],  # meteor almost physics/MEM
}
for name, w in cands.items():
    d = root / name
    d.mkdir(exist_ok=True)
    for f in ('model.keras','best.keras','scaler.npz','meta.json','calibration.npz'):
        if (src/f).exists():
            shutil.copy2(src/f, d/f)
    arr = np.asarray(w, float)
    assert (arr > 0).all() and arr[1] >= 0.2, (name, w)
    np.save(d/'blend_weights.npy', arr)
    (d/'blend.json').write_text(json.dumps({
        'blend': w,
        'notes': {
            'temp': 'small ML share = Diviner residual',
            'meteor_dust': 'physics/MEM/LDEX-led (low ML)',
            'rad': 'ML restored >0 (never zero fix)',
            'solar': 'LSTM primary',
        }
    }, indent=2))
(root/'manifest.json').write_text(json.dumps({'cands': cands}, indent=2))
print('built', list(cands))
PY

score_one() {
  local model_dir="$1"
  local tag="$2"
  local o="$OUT/windows_$tag"
  mkdir -p "$o"
  echo "=== SCORE $tag on CPU ==="
  $CPU_RUN scripts/run_14day_flagship_study.py \
    --csv "$WIN_CSV" --model-dir "$model_dir" \
    --start 2026-06-17 --end 2026-07-14 --window-label A \
    --out-dir "$o/A" >"$o/A.log" 2>"$o/A.err" || true
  tail -8 "$o/A.log" "$o/A.err" 2>/dev/null || true
  $CPU_RUN scripts/run_14day_flagship_study.py \
    --csv "$WIN_CSV" --model-dir "$model_dir" \
    --start 2024-05-04 --end 2024-05-17 --window-label C \
    --out-dir "$o/B_storm" >"$o/B.log" 2>"$o/B.err" || true
  tail -8 "$o/B.log" "$o/B.err" 2>/dev/null || true
  python - <<PY
import json
from pathlib import Path
o = Path("$o")
wins = {}
for label, sub in [("A","A"),("B_storm","B_storm")]:
    p = o/sub/"summary.json"
    if not p.exists():
        wins[label] = {"wins": None, "error": "missing summary", "err": (o/(sub[0]+'.err')).read_text()[-500:] if (o/(sub[0]+'.err')).exists() else ""}
        continue
    s = json.loads(p.read_text())
    metrics = s.get("metrics") or {}
    beat_map = {}
    n_win = n_tot = 0
    for h, v in metrics.items():
        if not isinstance(v, dict):
            continue
        n_tot += 1
        b = v.get("hybrid_beats_flagship")
        if b is None and "hybrid" in v and "flagship" in v:
            try:
                hr = v["hybrid"]["rmse"] if isinstance(v["hybrid"], dict) else v["hybrid"]
                fr = v["flagship"]["rmse"] if isinstance(v["flagship"], dict) else v["flagship"]
                b = float(hr) < float(fr)
            except Exception:
                b = False
        beat_map[h] = bool(b)
        if b: n_win += 1
    wins[label] = {"wins": n_win, "total": n_tot, "beat_map": beat_map}
(o/"window_wins.json").write_text(json.dumps({"tag":"$tag","model_dir":"$model_dir","wins":wins}, indent=2))
print(json.dumps(wins, indent=2))
PY
}

BEST_SCORE=-1
BEST_TAG=""
for tag in L0_rad_restore L1_solar_rad L2_diviner_temp_resid L3_physics_heavy L4_balanced L5_seasonal_meteor_light; do
  score_one "$OUT/cands/$tag" "$tag" || true
  python - <<PY
import json
from pathlib import Path
p=Path("$OUT/windows_$tag/window_wins.json")
if not p.exists():
    print("NO_WINS $tag"); raise SystemExit(0)
w=json.loads(p.read_text())["wins"]
a=w.get("A",{}).get("wins"); b=w.get("B_storm",{}).get("wins")
a= -1 if a is None else int(a); b= -1 if b is None else int(b)
score = (min(a,b) if a>=0 and b>=0 else -1)*10 + max(a,0)+max(b,0)
bestp=Path("$OUT/best.json")
cur={"tag":"$tag","A":a,"B":b,"score":score}
if (not bestp.exists()) or score > json.loads(bestp.read_text()).get("score",-999):
    bestp.write_text(json.dumps(cur, indent=2))
print("RESULT", cur, "BEST", bestp.read_text())
PY
  A=$(python -c "import json; print(json.load(open('$OUT/windows_$tag/window_wins.json'))['wins'].get('A',{}).get('wins'))")
  B=$(python -c "import json; print(json.load(open('$OUT/windows_$tag/window_wins.json'))['wins'].get('B_storm',{}).get('wins'))")
  logrow "CPU LEVER $tag WindowA_wins=${A} WindowB_storm_wins=${B} (train2_locked+blend; Metal T4c still running) | N | - | ${A} | ${B} | - | - | keep if best | next cand |"
done

python - <<'PY'
import json
from pathlib import Path
b=json.loads(Path('logs/overnight_improve/train4/cpu_levers/best.json').read_text())
print('BEST_CPU_LEVER', b)
# Apply best blend onto a frozen package for later merge
import shutil, numpy as np
src=Path('logs/overnight_improve/train4/cpu_levers/cands')/b['tag']
dst=Path('logs/overnight_improve/train4/cpu_levers/best_package')
if dst.exists(): shutil.rmtree(dst)
shutil.copytree(src, dst)
print('wrote', dst)
PY
BEST=$(python -c "import json; print(json.load(open('logs/overnight_improve/train4/cpu_levers/best.json')))")
logrow "CPU LEVERS DONE best=${BEST} — will merge onto T4c when ready; draft30 only after promote+studies | N | - | see best | see best | - | - | keep | await T4c heldout then merge |"
echo CPU_LEVERS_COMPLETE | tee "$OUT/done.txt"
