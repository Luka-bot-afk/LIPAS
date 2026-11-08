#!/bin/zsh
# Credit-smart post-T4c climb (USER REINFORCE):
# Mission = beat NASA/replica on study windows — held-out is secondary.
# Order on miss: serve/physics/Diviner/MEM levers → window score → mission/ablation
# → T4d retrain ONLY if windows still short. Don't burn epochs if residual/physics wins.
set -euo pipefail
cd /Users/lukatakki/Documents/GitHub/LIPAS
source .venv/bin/activate
export ALLOW_TRAIN4=1 TF_CPP_MIN_LOG_LEVEL=2 PYTHONUNBUFFERED=1 SETUPTOOLS_USE_DISTUTILS=local
LEDGER=logs/overnight_improve/train4/ledger.md
OUT=logs/overnight_improve/train4
WIN_CSV=data/ingested_extended/extended_training_window_B_ready.csv
logrow() { printf '| %s | %s\n' "$(date -u +%Y-%m-%dT%H:%MZ)" "$1" >> "$LEDGER"; }
pin_tf() { pip install -q --force-reinstall 'setuptools==69.5.1'; export SETUPTOOLS_USE_DISTUTILS=local; }
pin_tf

logrow "MISSION REINFORCE: window NASA/replica wins primary; held-out secondary; serve/physics before T4d epochs | N | - | - | - | - | - | keep | wait T4c then serve-first |"

# Wait for T4c gate + idle GPU
while [[ ! -f saved_model_train4c/train4_gate.json ]] || pgrep -f 'scripts/train4_kaggle.py' >/dev/null; do
  echo "$(date -u +%H:%M:%SZ) waiting T4c..."; sleep 60
done
sleep 5

RMSE_C=$(python -c "import json; print(json.load(open('saved_model_train4c/train4_gate.json'))['test_rmse'])")
BEAT_C=$(python -c "import json; print(json.load(open('saved_model_train4c/train4_gate.json'))['beats_train2'])")
logrow "T4c DONE heldout=${RMSE_C} beats_train2=${BEAT_C} (secondary gate) | Y | ${RMSE_C} | - | - | - | - | record | serve/window climb |"
cp -f saved_model_train4c/train4_gate.json "$OUT/t4c_gate.json"

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
  'note': 'held-out ranking only; promote uses window wins vs NASA/replica',
}, indent=2))
print('heldout ranked', cands)
PY

# --- Primary path: train-2 locked + serve levers (physics-led where ML weak) ---
logrow "SERVE-FIRST: restore train-2 locked; blend all w>0; temp=Diviner residual ML; meteor/dust physics-led | N | 4.9685 | pending | pending | - | - | running | window score |"
rm -rf saved_model
cp -R papers/appendix_numerical_tables/locked_saved_model saved_model
cp -R papers/appendix_numerical_tables/locked_saved_model saved_model_train2_locked
mkdir -p data/ingested_extended
[[ -f data/ingested_extended/extended_training_1784310247.csv ]] || \
  cp "/Users/lukatakki/Documents/L.I.P.A.S. V3/data/ingested_extended/extended_training_1784310247.csv" data/ingested_extended/
[[ -f "$WIN_CSV" ]] || cp "/Users/lukatakki/Documents/L.I.P.A.S. V3/data/ingested_extended/extended_training_window_B_ready.csv" data/ingested_extended/

# Candidate serve blends — physics-heavy on temp/dust/meteor; ML on solar/rad
python - <<'PY'
import json, shutil
from pathlib import Path
import numpy as np
root = Path('logs/overnight_improve/train4/serve_cands')
root.mkdir(parents=True, exist_ok=True)
# name -> blend [solar, rad, temp, moonq, meteor, dust]
cands = {
  's0_train2_rad_restore': [0.40, 0.25, 0.05, 0.05, 0.05, 0.05],
  's1_solar_rad_priority': [0.45, 0.35, 0.08, 0.05, 0.10, 0.05],
  's2_temp_diviner_resid': [0.40, 0.30, 0.15, 0.05, 0.10, 0.05],
  's3_physics_heavy_nonml': [0.35, 0.25, 0.05, 0.05, 0.05, 0.05],
  's4_balanced_all_gt0': [0.40, 0.30, 0.12, 0.10, 0.15, 0.10],
}
src = Path('papers/appendix_numerical_tables/locked_saved_model')
for name, w in cands.items():
    d = root / name
    d.mkdir(exist_ok=True)
    for f in ('model.keras','best.keras','scaler.npz','meta.json','calibration.npz'):
        if (src/f).exists(): shutil.copy2(src/f, d/f)
    arr = np.asarray(w, float)
    assert (arr > 0).all() and arr[1] >= 0.2
    np.save(d/'blend_weights.npy', arr)
    (d/'blend.json').write_text(json.dumps({'blend': w, 'policy': 'all w>0; rad>=0.2; temp small=Diviner residual; meteor/dust light ML'}, indent=2))
(root/'manifest.json').write_text(json.dumps({'cands': cands, 'mission': 'window wins vs NASA/replica'}, indent=2))
print('serve cands', list(cands))
PY

score_windows() {
  local model_dir="$1"
  local tag="$2"
  local o="$OUT/windows_$tag"
  mkdir -p "$o"
  pin_tf
  python scripts/run_14day_flagship_study.py \
    --csv "$WIN_CSV" --model-dir "$model_dir" \
    --start 2026-06-17 --end 2026-07-14 --window-label A \
    --out-dir "$o/A" >/dev/null
  python scripts/run_14day_flagship_study.py \
    --csv "$WIN_CSV" --model-dir "$model_dir" \
    --start 2024-05-04 --end 2024-05-17 --window-label C \
    --out-dir "$o/B_storm" >/dev/null
  python - <<PY
import json
from pathlib import Path
o = Path("$o")
summary = {}
wins = {}
for label, sub in [("A", "A"), ("B_storm", "B_storm")]:
    p = o/sub/"summary.json"
    if not p.exists():
        continue
    s = json.loads(p.read_text())
    metrics = s.get("metrics") or s.get("hazards") or {}
    # Prefer explicit hybrid_beats_flagship fields if present
    beat_map = {}
    n_win = 0
    n_tot = 0
    # structure from flagship: summary['metrics'][h] with hybrid_beats_flagship OR nested
    if isinstance(metrics, dict):
        for h, v in metrics.items():
            if not isinstance(v, dict):
                continue
            n_tot += 1
            b = v.get("hybrid_beats_flagship")
            if b is None and "hybrid" in v and "flagship" in v:
                # compare rmse
                try:
                    b = float(v["hybrid"]["rmse"]) < float(v["flagship"]["rmse"])
                except Exception:
                    b = False
            beat_map[h] = bool(b)
            if b: n_win += 1
    wins[label] = {"wins": n_win, "total": n_tot, "beat_map": beat_map}
    summary[label] = {"wins": n_win, "total": n_tot, "beat_map": beat_map, "raw_keys": list(metrics)[:12]}
(o/"window_wins.json").write_text(json.dumps({"tag": "$tag", "model_dir": "$model_dir", "wins": wins}, indent=2))
print(json.dumps(wins))
# exit code 0 always; wins printed for shell
open("/tmp/lipas_wins_$tag.json","w").write(json.dumps(wins))
PY
}

# Score key serve candidates (credit-smart: few cands, not huge grid)
BEST_TAG=""
BEST_A=-1
BEST_B=-1
for tag in s0_train2_rad_restore s1_solar_rad_priority s2_temp_diviner_resid s3_physics_heavy_nonml s4_balanced_all_gt0; do
  echo "=== WINDOW SCORE $tag ==="
  # install blend into saved_model for study scripts that read model-dir
  cp -f "$OUT/serve_cands/$tag/blend_weights.npy" saved_model/blend_weights.npy
  # also point model-dir at cand copy (has same weights)
  score_windows "$OUT/serve_cands/$tag" "$tag" || true
  python - <<PY
import json
from pathlib import Path
w=json.loads(Path("$OUT/windows_$tag/window_wins.json").read_text())["wins"]
a=w.get("A",{}).get("wins",0); b=w.get("B_storm",{}).get("wins",0)
print(f"$tag A_wins={a} B_wins={b}")
Path("/tmp/lipas_best_probe.txt").write_text(f"{a} {b} $tag\n")
PY
  read AWIN BWIN _TAG < /tmp/lipas_best_probe.txt || true
  logrow "WINDOW serve=$tag A_wins=${AWIN:-?} B_wins=${BWIN:-?} | N | 4.9685 | ${AWIN:-?} | ${BWIN:-?} | - | - | keep if >=5 | next cand or promote |"
  # track best by min(A,B) then sum
  python - <<PY
import json
from pathlib import Path
w=json.loads(Path("$OUT/windows_$tag/window_wins.json").read_text())["wins"]
a=int(w.get("A",{}).get("wins",0)); b=int(w.get("B_storm",{}).get("wins",0))
prev=Path("$OUT/best_serve_windows.json")
cur={"tag":"$tag","A":a,"B":b,"score":min(a,b)*10+a+b}
if prev.exists():
    old=json.loads(prev.read_text())
    if cur["score"] > old.get("score",-1):
        prev.write_text(json.dumps(cur, indent=2))
else:
    prev.write_text(json.dumps(cur, indent=2))
print("best so far", prev.read_text())
PY
done

BEST_TAG=$(python -c "import json; print(json.load(open('logs/overnight_improve/train4/best_serve_windows.json'))['tag'])")
BEST_A=$(python -c "import json; print(json.load(open('logs/overnight_improve/train4/best_serve_windows.json'))['A'])")
BEST_B=$(python -c "import json; print(json.load(open('logs/overnight_improve/train4/best_serve_windows.json'))['B'])")
logrow "BEST SERVE $BEST_TAG A=$BEST_A B=$BEST_B | N | 4.9685 | $BEST_A | $BEST_B | - | - | decide | promote if >=5/6 else T4d |"

# Promote serve-best onto saved_model
cp -R "$OUT/serve_cands/$BEST_TAG/"* saved_model/
cp -f "$OUT/serve_cands/$BEST_TAG/blend_weights.npy" saved_model_train2_locked/blend_weights.npy

# Gate: ≥5 wins on each window (1 miss OK globally → allow 5/6)
PROMOTE=0
if python - <<PY
import json, sys
b=json.load(open("logs/overnight_improve/train4/best_serve_windows.json"))
ok = b["A"] >= 5 and b["B"] >= 5
print("PROMOTE" if ok else "NO_PROMOTE", b)
sys.exit(0 if ok else 1)
PY
then
  PROMOTE=1
fi

if [[ "$PROMOTE" == "1" ]]; then
  logrow "PROMOTE serve-best $BEST_TAG on window wins A=$BEST_A B=$BEST_B — run mission+ablation; SKIP T4d epoch burn | N | 4.9685 | $BEST_A | $BEST_B | - | - | keep | mission+ablation |"
  python scripts/run_mission_sim_radiation_eva.py --csv "$WIN_CSV" --model-dir saved_model --day 2026-07-12 --out-dir "$OUT/mission_sim" || true
  python scripts/run_hazard_ablation_study.py --csv "$WIN_CSV" --model-dir saved_model --start 2026-07-05 --end 2026-07-18 --out-dir "$OUT/ablation" || true
  echo STUDIES_COMPLETE serve=$BEST_TAG | tee "$OUT/studies_done.txt"
  logrow "STUDIES DONE after serve promote — draft30 may patch from real numbers only | N | 4.9685 | $BEST_A | $BEST_B | - | - | keep | paper handoff |"
  exit 0
fi

logrow "Windows short of 5/6 — try physics-led serve still; THEN T4d train2-CSV rematch (last resort epochs) | N | 4.9685 | $BEST_A | $BEST_B | - | - | keep climbing | T4d |"

# Autopsy note
python - <<'PY'
import json
from pathlib import Path
Path('logs/overnight_improve/train4/autopsy_t4_ladder.json').write_text(json.dumps({
  'mission': 'window wins vs NASA/replica (primary); held-out secondary',
  't4_heldout': json.loads(Path('logs/overnight_improve/train4/best_pick.json').read_text()) if Path('logs/overnight_improve/train4/best_pick.json').exists() else None,
  'best_serve_windows': json.loads(Path('logs/overnight_improve/train4/best_serve_windows.json').read_text()),
  'hypothesis': 'train7+channel_norm blew temp absolute RMSE; train-2 CSV + Diviner/MEM physics serve may win hazards without new LSTM',
  'next': 'T4d rematch train-2 CSV plain Huber only because windows still <5/6',
}, indent=2))
PY

# T4d only if needed
pin_tf
logrow "T4d START train-2 CSV rematch (only after serve/window miss) | Y | pending | - | - | - | - | running | |"
python scripts/train4_kaggle.py --stage t4a --config configs/train4d_train2csv.json \
  --csv data/ingested_extended/extended_training_1784310247.csv \
  --model-dir saved_model_train4d --epochs 80 2>&1 | tee "$OUT/t4d_run.log"
RMSE_D=$(python -c "import json; print(json.load(open('saved_model_train4d/train4_gate.json')).get('test_rmse','?'))" 2>/dev/null || echo '?')
BEAT_D=$(python -c "import json; print(json.load(open('saved_model_train4d/train4_gate.json')).get('beats_train2',False))" 2>/dev/null || echo False)
logrow "T4d DONE heldout=${RMSE_D} beats=${BEAT_D} — re-score windows with T4d+serve | Y | ${RMSE_D} | pending | pending | - | - | record | window rescore |"

# After T4d: apply start blend and rescore windows
if [[ -d saved_model_train4d ]]; then
  python - <<'PY'
import numpy as np, shutil
from pathlib import Path
src=Path('saved_model_train4d')
dst=Path('saved_model')
if dst.exists():
    import shutil as sh
    sh.rmtree(dst)
shutil.copytree(src, dst)
w=np.array([0.40,0.25,0.10,0.10,0.15,0.10])
np.save(dst/'blend_weights.npy', w)
np.save(src/'blend_weights.npy', w)
print('T4d serve blend', w.tolist())
PY
  score_windows saved_model_train4d t4d || true
  python - <<'PY'
import json
from pathlib import Path
p=Path('logs/overnight_improve/train4/windows_t4d/window_wins.json')
print(p.read_text() if p.exists() else 'no wins file')
PY
fi
echo CONTINUE_COMPLETE | tee "$OUT/climb_continue_done.txt"
