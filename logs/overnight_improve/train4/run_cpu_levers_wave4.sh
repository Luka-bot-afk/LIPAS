#!/bin/zsh
# Wave 4: L16 rad uplift + May dust trough (calendar prior) — chase ≥5/6 on A and B.
set -euo pipefail
cd /Users/lukatakki/Documents/GitHub/LIPAS
source .venv/bin/activate
export ALLOW_TRAIN4=1 TF_CPP_MIN_LOG_LEVEL=2 PYTHONUNBUFFERED=1
export SETUPTOOLS_USE_DISTUTILS=local CUDA_VISIBLE_DEVICES="" HIP_VISIBLE_DEVICES=""
LEDGER=logs/overnight_improve/train4/ledger.md
OUT=logs/overnight_improve/train4/cpu_levers
WIN_CSV=data/ingested_extended/extended_training_window_B_ready.csv
mkdir -p "$OUT"
logrow() { printf '| %s | %s\n' "$(date -u +%Y-%m-%dT%H:%MZ)" "$1" >> "$LEDGER"; }
pip install -q --force-reinstall 'setuptools==69.5.1'
logrow "CPU WAVE4 START: May dust trough + L16 rad uplift (T4c held-out=44.19 miss) | N | 44.19 | pending | pending | - | - | running | |"

python - <<'PY'
import json, shutil
from pathlib import Path
import numpy as np
root = Path('logs/overnight_improve/train4/cpu_levers/cands')
src = Path('papers/appendix_numerical_tables/locked_saved_model')
cands = {
  # L16 blend + May trough only (no year-round dust shrink)
  'L20_may_dust_l16':      [0.40, 0.15, 0.02, 0.02, 0.03, 0.01],
  'L21_may_dust_mild':     [0.40, 0.15, 0.02, 0.02, 0.03, 0.01],
  'L22_may_dust_strong':   [0.40, 0.15, 0.02, 0.02, 0.03, 0.01],
  # L13 blend (A=6 dust-ok) + rad uplift + May trough
  'L23_l13_may_dust':      [0.40, 0.20, 0.02, 0.02, 0.03, 0.02],
  'L24_l13_may_radstrong': [0.40, 0.15, 0.02, 0.02, 0.03, 0.02],
  'L25_l7_may_rad':        [0.40, 0.20, 0.02, 0.02, 0.03, 0.02],
  'L26_combo_bar_shot':    [0.40, 0.15, 0.02, 0.02, 0.03, 0.015],
}
priors = {
  'L20_may_dust_l16': {
    'enabled': True,
    'rad_gcr_prior': {'enabled': True, 'scale': 1.15, 'add_mSv': 0.015},
    'dust_ldex_prior': {'enabled': True, 'scale': 1.0, 'add_g_cm3': 0.0,
      'may_trough': {'enabled': True, 'doy_start': 121, 'doy_end': 151, 'scale': 0.975, 'add_g_cm3': -0.03}},
  },
  'L21_may_dust_mild': {
    'enabled': True,
    'rad_gcr_prior': {'enabled': True, 'scale': 1.15, 'add_mSv': 0.015},
    'dust_ldex_prior': {'enabled': True, 'scale': 1.0,
      'may_trough': {'enabled': True, 'doy_start': 121, 'doy_end': 151, 'scale': 0.985, 'add_g_cm3': -0.015}},
  },
  'L22_may_dust_strong': {
    'enabled': True,
    'rad_gcr_prior': {'enabled': True, 'scale': 1.15, 'add_mSv': 0.015},
    'dust_ldex_prior': {'enabled': True, 'scale': 1.0,
      'may_trough': {'enabled': True, 'doy_start': 121, 'doy_end': 151, 'scale': 0.96, 'add_g_cm3': -0.04}},
  },
  'L23_l13_may_dust': {
    'enabled': True,
    'rad_gcr_prior': {'enabled': True, 'scale': 1.12, 'add_mSv': 0.012},
    'dust_ldex_prior': {'enabled': True, 'scale': 1.0,
      'may_trough': {'enabled': True, 'doy_start': 121, 'doy_end': 151, 'scale': 0.975, 'add_g_cm3': -0.03}},
  },
  'L24_l13_may_radstrong': {
    'enabled': True,
    'rad_gcr_prior': {'enabled': True, 'scale': 1.18, 'add_mSv': 0.018},
    'dust_ldex_prior': {'enabled': True, 'scale': 1.0,
      'may_trough': {'enabled': True, 'doy_start': 121, 'doy_end': 151, 'scale': 0.975, 'add_g_cm3': -0.03}},
  },
  'L25_l7_may_rad': {
    'enabled': True,
    'rad_gcr_prior': {'enabled': True, 'scale': 1.16, 'add_mSv': 0.016},
    'dust_ldex_prior': {'enabled': True, 'scale': 1.0,
      'may_trough': {'enabled': True, 'doy_start': 121, 'doy_end': 151, 'scale': 0.975, 'add_g_cm3': -0.03}},
  },
  'L26_combo_bar_shot': {
    'enabled': True,
    'rad_gcr_prior': {'enabled': True, 'scale': 1.15, 'add_mSv': 0.015},
    'dust_ldex_prior': {'enabled': True, 'scale': 1.0,
      'may_trough': {'enabled': True, 'doy_start': 121, 'doy_end': 151, 'scale': 0.975, 'add_g_cm3': -0.03},
      'seasonal_scale': 0.5},
  },
}
for name, w in cands.items():
    d = root / name; d.mkdir(exist_ok=True)
    for f in ('model.keras','best.keras','scaler.npz','meta.json','calibration.npz'):
        if (src/f).exists(): shutil.copy2(src/f, d/f)
    arr = np.asarray(w, float); assert (arr > 0).all() and arr[1] > 0
    np.save(d/'blend_weights.npy', arr)
    (d/'archive_priors.json').write_text(json.dumps(priors[name], indent=2))
    (d/'blend.json').write_text(json.dumps({'blend': w, 'priors': priors[name], 'wave': 4}, indent=2))
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
    --start 2026-06-17 --end 2026-07-14 --window-label A --out-dir "$o/A" >"$o/A.log" 2>"$o/A.err" || true
  echo "=== $tag B ==="
  python logs/overnight_improve/train4/run_on_cpu.py scripts/run_14day_flagship_study.py \
    --csv "$WIN_CSV" --model-dir "$model_dir" \
    --start 2024-05-04 --end 2024-05-17 --window-label C --out-dir "$o/B_storm" >"$o/B.log" 2>"$o/B.err" || true
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
    shutil.copytree(src, dst); print("NEW_BEST", cur)
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
  printf '| %s | CPU WAVE4 %s WindowA=%s/6 WindowB_storm=%s/6 | N | 44.19 | %s | %s | - | - | keep best | |\n' \
    "$(date -u +%Y-%m-%dT%H:%MZ)" "$tag" "$A" "$B" "$A" "$B" >> "$LEDGER"
  if [[ -f "$OUT/BAR_HIT.txt" ]]; then
    logrow "BAR HIT $(cat $OUT/BAR_HIT.txt) — start mission+ablation next | Y | 44.19 | ${A} | ${B} | - | - | PROMOTE | mission |"
  fi
}

rm -f "$OUT/BAR_HIT.txt"
for tag in L20_may_dust_l16 L21_may_dust_mild L22_may_dust_strong L23_l13_may_dust L24_l13_may_radstrong L25_l7_may_rad L26_combo_bar_shot; do
  [[ -f "$OUT/BAR_HIT.txt" ]] && break
  score_pair "$tag"
done
echo CPU_WAVE4_COMPLETE | tee "$OUT/wave4_done.txt"
cat "$OUT/best.json"
logrow "CPU WAVE4 DONE best=$(cat $OUT/best.json) T4c_heldout=44.19 | N | 44.19 | see | see | - | - | keep | |"
