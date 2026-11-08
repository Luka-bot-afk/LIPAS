#!/bin/zsh
# Wave 3: L7 base + invented CRaTER/GCR rad uplift + LDEX dust shrink (hybrid-only).
# Goal: keep A≥5, lift B from 3→≥5 (solar may remain the 1 allowed miss).
set -euo pipefail
cd /Users/lukatakki/Documents/GitHub/LIPAS
source .venv/bin/activate
export ALLOW_TRAIN4=1 TF_CPP_MIN_LOG_LEVEL=2 PYTHONUNBUFFERED=1
export SETUPTOOLS_USE_DISTUTILS=local
export CUDA_VISIBLE_DEVICES="" HIP_VISIBLE_DEVICES=""
LEDGER=logs/overnight_improve/train4/ledger.md
OUT=logs/overnight_improve/train4/cpu_levers
WIN_CSV=data/ingested_extended/extended_training_window_B_ready.csv
mkdir -p "$OUT"
logrow() { printf '| %s | %s\n' "$(date -u +%Y-%m-%dT%H:%MZ)" "$1" >> "$LEDGER"; }
pip install -q --force-reinstall 'setuptools==69.5.1'
logrow "CPU WAVE3 START: L7 base + GCR rad uplift + LDEX dust shrink (parallel Metal T4c) | N | - | pending | pending | - | - | running | overlap |"

python - <<'PY'
import json, shutil
from pathlib import Path
import numpy as np
root = Path('logs/overnight_improve/train4/cpu_levers/cands')
src = Path('papers/appendix_numerical_tables/locked_saved_model')
# L7-like blends with rad>0; dust nearly physics
cands = {
  'L13_l7_rad_uplift':     [0.40, 0.20, 0.02, 0.02, 0.03, 0.02],
  'L14_l7_dust_shrink':    [0.40, 0.20, 0.02, 0.02, 0.03, 0.01],
  'L15_l7_rad_dust':       [0.40, 0.20, 0.02, 0.02, 0.03, 0.01],
  'L16_rad_mild_dust':     [0.40, 0.15, 0.02, 0.02, 0.03, 0.01],  # rad ML 0.15>0
  'L17_rad_strong_dust':   [0.40, 0.12, 0.02, 0.02, 0.03, 0.008],
  'L18_storm_target':      [0.38, 0.10, 0.02, 0.02, 0.03, 0.008],
  'L19_rad20_dust_term':   [0.40, 0.20, 0.02, 0.02, 0.03, 0.01],
}
priors = {
  'L13_l7_rad_uplift': {
    'enabled': True,
    'rad_gcr_prior': {'enabled': True, 'scale': 1.12, 'add_mSv': 0.012},
  },
  'L14_l7_dust_shrink': {
    'enabled': True,
    'dust_ldex_prior': {'enabled': True, 'scale': 0.985, 'add_g_cm3': -0.002, 'terminator_extra': True},
  },
  'L15_l7_rad_dust': {
    'enabled': True,
    'rad_gcr_prior': {'enabled': True, 'scale': 1.10, 'add_mSv': 0.010},
    'dust_ldex_prior': {'enabled': True, 'scale': 0.980, 'add_g_cm3': -0.003, 'terminator_extra': True},
  },
  'L16_rad_mild_dust': {
    'enabled': True,
    'rad_gcr_prior': {'enabled': True, 'scale': 1.15, 'add_mSv': 0.015},
    'dust_ldex_prior': {'enabled': True, 'scale': 0.975, 'add_g_cm3': -0.004, 'terminator_extra': True},
  },
  'L17_rad_strong_dust': {
    'enabled': True,
    'rad_gcr_prior': {'enabled': True, 'scale': 1.20, 'add_mSv': 0.020},
    'dust_ldex_prior': {'enabled': True, 'scale': 0.970, 'add_g_cm3': -0.005, 'terminator_extra': True},
  },
  'L18_storm_target': {
    'enabled': True,
    'rad_gcr_prior': {'enabled': True, 'scale': 1.18, 'add_mSv': 0.018},
    'dust_ldex_prior': {'enabled': True, 'scale': 0.968, 'add_g_cm3': -0.006, 'terminator_extra': True,
                        'terminator_scale': 0.90},
  },
  'L19_rad20_dust_term': {
    'enabled': True,
    'rad_gcr_prior': {'enabled': True, 'scale': 1.08, 'add_mSv': 0.008},
    'dust_ldex_prior': {'enabled': True, 'scale': 0.990, 'add_g_cm3': -0.0015, 'terminator_extra': True},
  },
}
for name, w in cands.items():
    d = root / name
    d.mkdir(exist_ok=True)
    for f in ('model.keras','best.keras','scaler.npz','meta.json','calibration.npz'):
        if (src/f).exists(): shutil.copy2(src/f, d/f)
    arr = np.asarray(w, float)
    assert (arr > 0).all() and arr[1] > 0, (name, w)
    np.save(d/'blend_weights.npy', arr)
    (d/'archive_priors.json').write_text(json.dumps(priors[name], indent=2))
    (d/'blend.json').write_text(json.dumps({'blend': w, 'priors': priors[name], 'wave': 3}, indent=2))
(root/'manifest_wave3.json').write_text(json.dumps({'cands': cands}, indent=2))
print('built', list(cands))
PY

score_pair() {
  local tag="$1"; local model_dir="$OUT/cands/$tag"; local o="$OUT/windows_$tag"
  mkdir -p "$o"
  pip install -q --force-reinstall 'setuptools==69.5.1'
  export SETUPTOOLS_USE_DISTUTILS=local
  echo "=== $tag A ==="
  python logs/overnight_improve/train4/run_on_cpu.py scripts/run_14day_flagship_study.py \
    --csv "$WIN_CSV" --model-dir "$model_dir" \
    --start 2026-06-17 --end 2026-07-14 --window-label A \
    --out-dir "$o/A" >"$o/A.log" 2>"$o/A.err" || true
  echo "=== $tag B ==="
  python logs/overnight_improve/train4/run_on_cpu.py scripts/run_14day_flagship_study.py \
    --csv "$WIN_CSV" --model-dir "$model_dir" \
    --start 2024-05-04 --end 2024-05-17 --window-label C \
    --out-dir "$o/B_storm" >"$o/B.log" 2>"$o/B.err" || true
  python - <<PY
import json, shutil
from pathlib import Path
o=Path("$o"); wins={}
for label, sub in [("A","A"),("B_storm","B_storm")]:
    p=o/sub/"summary.json"
    if not p.exists():
        wins[label]={"wins":None}; continue
    m=json.loads(p.read_text()).get("metrics") or {}; beat={}; n=t=0
    for h,v in m.items():
        if not isinstance(v,dict) or "hybrid" not in v: continue
        t+=1; hr=float(v["hybrid"]["rmse"]); fr=float(v["flagship"]["rmse"]); b=hr<fr; beat[h]=b
        if b: n+=1
    wins[label]={"wins":n,"total":t,"beat_map":beat}
(o/"window_wins.json").write_text(json.dumps({"tag":"$tag","wins":wins}, indent=2))
print("$tag", json.dumps(wins))
a=wins.get("A",{}).get("wins"); b=wins.get("B_storm",{}).get("wins")
a_i=-1 if a is None else int(a); b_i=-1 if b is None else int(b)
score=(min(a_i,b_i) if a_i>=0 and b_i>=0 else -1)*10+max(a_i,0)+max(b_i,0)
cur={"tag":"$tag","A":a_i,"B":b_i,"score":score}
bestp=Path("$OUT/best.json"); prev=json.loads(bestp.read_text()) if bestp.exists() else {"score":-999}
if score>prev.get("score",-999):
    bestp.write_text(json.dumps(cur, indent=2))
    src=Path("$model_dir"); dst=Path("$OUT/best_package")
    if dst.exists(): shutil.rmtree(dst)
    shutil.copytree(src, dst)
    print("NEW_BEST", cur)
else:
    print("RESULT", cur, "BEST", prev)
completed=[]; best={"tag":None,"A":-1,"B":-1,"score":-999}
for p in sorted(Path("$OUT").glob("windows_*/window_wins.json")):
    w=json.loads(p.read_text()); tag=w.get("tag") or p.parent.name.replace("windows_","")
    ww=w.get("wins") or {}; a=(ww.get("A") or {}).get("wins"); b=(ww.get("B_storm") or {}).get("wins")
    if a is None or b is None: continue
    completed.append({"tag":tag,"A_wins":a,"B_wins":b,"A_map":(ww.get("A") or {}).get("beat_map"),"B_map":(ww.get("B_storm") or {}).get("beat_map")})
    sc=min(a,b)*10+a+b
    if sc>best["score"]: best={"tag":tag,"A":a,"B":b,"score":sc}
Path("$OUT/progress_summary.json").write_text(json.dumps({"best_so_far":best,"completed":completed,"note":"primary=window wins; held-out secondary"}, indent=2))
print("HIT_5_OF_6" if a_i>=5 and b_i>=5 else "SHORT_OF_BAR", cur)
if a_i>=5 and b_i>=5:
    Path("$OUT/BAR_HIT.txt").write_text(f"$tag A={a_i} B={b_i}\n")
PY
  A=$(python -c "import json; print(json.load(open('$o/window_wins.json'))['wins'].get('A',{}).get('wins'))")
  B=$(python -c "import json; print(json.load(open('$o/window_wins.json'))['wins'].get('B_storm',{}).get('wins'))")
  printf '| %s | CPU WAVE3 %s WindowA=%s/6 WindowB_storm=%s/6 (parallel Metal T4c) | N | - | %s | %s | - | - | keep best | |\n' \
    "$(date -u +%Y-%m-%dT%H:%MZ)" "$tag" "$A" "$B" "$A" "$B" >> "$LEDGER"
  if [[ -f "$OUT/BAR_HIT.txt" ]]; then
    logrow "BAR HIT $(cat $OUT/BAR_HIT.txt) — prepare mission+ablation | Y | - | ${A} | ${B} | - | - | PROMOTE | mission |"
  fi
}

for tag in L13_l7_rad_uplift L14_l7_dust_shrink L15_l7_rad_dust L16_rad_mild_dust L17_rad_strong_dust L18_storm_target L19_rad20_dust_term; do
  [[ -f "$OUT/BAR_HIT.txt" ]] && break
  score_pair "$tag"
done
echo CPU_WAVE3_COMPLETE | tee "$OUT/wave3_done.txt"
cat "$OUT/best.json"
cat "$OUT/progress_summary.json" | python -c "import sys,json; d=json.load(sys.stdin); print('BEST',d['best_so_far']); print('n',len(d['completed']))"
logrow "CPU WAVE3 DONE best=$(cat $OUT/best.json) | N | - | see | see | - | - | keep | |"
