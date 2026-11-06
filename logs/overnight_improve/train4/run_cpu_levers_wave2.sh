#!/bin/zsh
# Wave 2 CPU levers: rad-floor adaptive fix + invented seasonal/Diviner archive priors.
# Overlap Metal T4c; force TF onto CPU.
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
logrow "CPU WAVE2 START: rad ML floor + seasonal/Diviner archive priors (parallel Metal T4c) | N | - | pending | pending | - | - | running | overlap |"

python - <<'PY'
import json, shutil
from pathlib import Path
import numpy as np

root = Path('logs/overnight_improve/train4/cpu_levers/cands')
root.mkdir(parents=True, exist_ok=True)
src = Path('papers/appendix_numerical_tables/locked_saved_model')

# [solar, rad, temp, moonq, meteor, dust] — all >0, rad>=0.2
cands = {
  # Rescore L0 under adaptive rad-floor fix (no archive prior)
  'L6_rad_floor_L0':          [0.40, 0.25, 0.05, 0.05, 0.05, 0.05],
  # Ultra physics on near-miss channels
  'L7_ultra_physics':         [0.40, 0.20, 0.02, 0.02, 0.03, 0.02],
  # Seasonal + Diviner hybrid-only prior (default pull)
  'L8_seasonal_temp_prior':   [0.40, 0.22, 0.04, 0.02, 0.05, 0.02],
  # Stronger Diviner pull on temp
  'L9_diviner_pull_strong':   [0.40, 0.22, 0.06, 0.02, 0.05, 0.02],
  # Solar emphasis + rad floor for storm B solar break-tie
  'L10_solar_rad_floor':      [0.48, 0.20, 0.03, 0.02, 0.04, 0.02],
  # Combo aimed at A rad/temp/moonq + B dust/rad
  'L11_combo_near_miss':      [0.42, 0.20, 0.03, 0.015, 0.04, 0.015],
  # Physics-heavy + mild seasonal scale
  'L12_phys_seasonal_mild':   [0.38, 0.22, 0.03, 0.02, 0.04, 0.02],
}

prior_specs = {
  'L6_rad_floor_L0': None,  # adaptive fix only
  'L7_ultra_physics': None,
  'L8_seasonal_temp_prior': {
      'enabled': True,
      'seasonal_temp': {
          'enabled': True,
          'diviner_pull': 0.18,
          'seasonal_scale': 1.0,
          'climatology_path': 'data/archives/diviner/enabled/site_climatology.json',
          'seasonal_path': 'data/archives/diviner/enabled/seasonal_temp_prior.json',
      },
  },
  'L9_diviner_pull_strong': {
      'enabled': True,
      'seasonal_temp': {
          'enabled': True,
          'diviner_pull': 0.32,
          'seasonal_scale': 1.25,
          'climatology_path': 'data/archives/diviner/enabled/site_climatology.json',
          'seasonal_path': 'data/archives/diviner/enabled/seasonal_temp_prior.json',
      },
  },
  'L10_solar_rad_floor': {
      'enabled': True,
      'seasonal_temp': {
          'enabled': True,
          'diviner_pull': 0.12,
          'seasonal_scale': 0.75,
          'climatology_path': 'data/archives/diviner/enabled/site_climatology.json',
          'seasonal_path': 'data/archives/diviner/enabled/seasonal_temp_prior.json',
      },
  },
  'L11_combo_near_miss': {
      'enabled': True,
      'seasonal_temp': {
          'enabled': True,
          'diviner_pull': 0.22,
          'seasonal_scale': 1.0,
          'climatology_path': 'data/archives/diviner/enabled/site_climatology.json',
          'seasonal_path': 'data/archives/diviner/enabled/seasonal_temp_prior.json',
      },
  },
  'L12_phys_seasonal_mild': {
      'enabled': True,
      'seasonal_temp': {
          'enabled': True,
          'diviner_pull': 0.10,
          'seasonal_scale': 0.5,
          'climatology_path': 'data/archives/diviner/enabled/site_climatology.json',
          'seasonal_path': 'data/archives/diviner/enabled/seasonal_temp_prior.json',
      },
  },
}

for name, w in cands.items():
    d = root / name
    d.mkdir(exist_ok=True)
    for f in ('model.keras', 'best.keras', 'scaler.npz', 'meta.json', 'calibration.npz'):
        if (src / f).exists():
            shutil.copy2(src / f, d / f)
    arr = np.asarray(w, float)
    assert (arr > 0).all() and arr[1] >= 0.2, (name, w)
    np.save(d / 'blend_weights.npy', arr)
    priors = prior_specs.get(name)
    if priors:
        (d / 'archive_priors.json').write_text(json.dumps(priors, indent=2))
    elif (d / 'archive_priors.json').exists():
        (d / 'archive_priors.json').unlink()
    (d / 'blend.json').write_text(json.dumps({
        'blend': w,
        'archive_priors': bool(priors),
        'notes': 'wave2: rad ML floor + optional hybrid-only seasonal/Diviner prior',
    }, indent=2))

manifest = {'wave': 2, 'cands': cands, 'priors': {k: bool(v) for k, v in prior_specs.items()}}
(root / 'manifest_wave2.json').write_text(json.dumps(manifest, indent=2))
print('built', list(cands))
PY

score_pair() {
  local tag="$1"
  local model_dir="$OUT/cands/$tag"
  local o="$OUT/windows_$tag"
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
o = Path("$o")
wins = {}
for label, sub in [("A", "A"), ("B_storm", "B_storm")]:
    p = o / sub / "summary.json"
    if not p.exists():
        wins[label] = {"wins": None}
        print("MISSING", label, (o / (sub[0] + ".err")).read_text()[-800:] if (o / (sub[0] + ".err")).exists() else "")
        continue
    m = (json.loads(p.read_text()).get("metrics") or {})
    beat = {}
    n = t = 0
    for h, v in m.items():
        if not isinstance(v, dict) or "hybrid" not in v:
            continue
        t += 1
        hr = float(v["hybrid"]["rmse"]); fr = float(v["flagship"]["rmse"])
        b = hr < fr
        beat[h] = b
        if b:
            n += 1
    wins[label] = {"wins": n, "total": t, "beat_map": beat}
(o / "window_wins.json").write_text(json.dumps({"tag": "$tag", "wins": wins}, indent=2))
print("$tag", json.dumps(wins))
a = wins.get("A", {}).get("wins"); b = wins.get("B_storm", {}).get("wins")
a_i = -1 if a is None else int(a); b_i = -1 if b is None else int(b)
score = (min(a_i, b_i) if a_i >= 0 and b_i >= 0 else -1) * 10 + max(a_i, 0) + max(b_i, 0)
cur = {"tag": "$tag", "A": a_i, "B": b_i, "score": score}
bestp = Path("$OUT/best.json")
prev = json.loads(bestp.read_text()) if bestp.exists() else {"score": -999}
if score > prev.get("score", -999):
    bestp.write_text(json.dumps(cur, indent=2))
    src = Path("$model_dir"); dst = Path("$OUT/best_package")
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)
    print("NEW_BEST", cur)
else:
    print("RESULT", cur, "BEST", prev)
# refresh progress summary
completed = []
best = {"tag": None, "A": -1, "B": -1, "score": -999}
for p in sorted(Path("$OUT").glob("windows_*/window_wins.json")):
    w = json.loads(p.read_text())
    tag = w.get("tag") or p.parent.name.replace("windows_", "")
    ww = w.get("wins") or {}
    a = (ww.get("A") or {}).get("wins")
    b = (ww.get("B_storm") or {}).get("wins")
    am = (ww.get("A") or {}).get("beat_map")
    bm = (ww.get("B_storm") or {}).get("beat_map")
    if a is None or b is None:
        continue
    completed.append({"tag": tag, "A_wins": a, "B_wins": b, "A_map": am, "B_map": bm})
    sc = min(a, b) * 10 + a + b
    if sc > best["score"]:
        best = {"tag": tag, "A": a, "B": b, "score": sc}
Path("$OUT/progress_summary.json").write_text(json.dumps({
    "best_so_far": best,
    "completed": completed,
    "note": "primary mission = window wins vs NASA/replica; held-out secondary",
}, indent=2))
hit = a_i >= 5 and b_i >= 5
print("HIT_5_OF_6" if hit else "SHORT_OF_BAR", cur)
PY
  A=$(python -c "import json; print(json.load(open('$o/window_wins.json'))['wins'].get('A',{}).get('wins'))")
  B=$(python -c "import json; print(json.load(open('$o/window_wins.json'))['wins'].get('B_storm',{}).get('wins'))")
  printf '| %s | CPU WAVE2 %s WindowA=%s/6 WindowB_storm=%s/6 (parallel Metal T4c) | N | - | %s | %s | - | - | keep best | |\n' \
    "$(date -u +%Y-%m-%dT%H:%MZ)" "$tag" "$A" "$B" "$A" "$B" >> "$LEDGER"
  if [[ "$A" == "5" || "$A" == "6" ]] && [[ "$B" == "5" || "$B" == "6" ]]; then
    echo "BAR_HIT $tag A=$A B=$B" | tee "$OUT/BAR_HIT.txt"
    logrow "BAR HIT $tag A=${A}/6 B=${B}/6 — stop wave2; prepare mission+ablation | Y | - | ${A} | ${B} | - | - | PROMOTE CAND | mission sim |"
  fi
}

for tag in L6_rad_floor_L0 L7_ultra_physics L8_seasonal_temp_prior L9_diviner_pull_strong L10_solar_rad_floor L11_combo_near_miss L12_phys_seasonal_mild; do
  if [[ -f "$OUT/BAR_HIT.txt" ]]; then
    echo "Stopping early — bar already hit"
    break
  fi
  score_pair "$tag"
done

echo CPU_WAVE2_COMPLETE | tee "$OUT/wave2_done.txt"
cat "$OUT/best.json"
cat "$OUT/progress_summary.json"
logrow "CPU WAVE2 DONE best=$(cat $OUT/best.json) | N | - | see best | see best | - | - | keep | await T4c or next wave |"
