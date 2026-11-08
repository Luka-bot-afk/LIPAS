#!/usr/bin/env bash
# Wave R4: TEMP-focused on R3b solar/rad base. Avoid R3t kill (night_add=+). No paper.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"
if [[ -f .venv/bin/activate ]]; then
  # shellcheck disable=SC1091
  source .venv/bin/activate
fi
export ALLOW_TRAIN4=1 TF_CPP_MIN_LOG_LEVEL=2 PYTHONUNBUFFERED=1
export SETUPTOOLS_USE_DISTUTILS=local
LEDGER=logs/overnight_improve/train4/drastic_wins_ledger.md
OUT=logs/overnight_improve/train4/cpu_levers
WIN_CSV=data/ingested_extended/extended_training_window_B_ready.csv
SRC=papers/appendix_numerical_tables/locked_saved_model
mkdir -p "$OUT/cands"
[[ -f "$LEDGER" ]] || printf '| utc | tag | A_wins | B_wins | notes |\n|---|---|---:|---:|---|\n' >"$LEDGER"
logrow() { printf '| %s | %s\n' "$(date -u +%Y-%m-%dT%H:%MZ)" "$1" >> "$LEDGER"; }
logrow "WAVE R4 START | - | - | - | TEMP on R3b base; correct day+/night- ; NOT_READY lock |"

python - <<'PY'
import json, shutil
from pathlib import Path
import numpy as np

root = Path('logs/overnight_improve/train4/cpu_levers/cands')
src = Path('papers/appendix_numerical_tables/locked_saved_model')
base_blend = [0.40, 0.15, 0.02, 0.02, 0.03, 0.01]
l20_dust = {
    'enabled': True, 'scale': 1.0, 'add_g_cm3': 0.0,
    'may_trough': {'enabled': True, 'doy_start': 121, 'doy_end': 151, 'scale': 0.975, 'add_g_cm3': -0.03},
}

def pack(name, blend, priors):
    d = root / name
    d.mkdir(exist_ok=True)
    for f in ('model.keras', 'best.keras', 'scaler.npz', 'meta.json', 'calibration.npz'):
        if (src / f).exists():
            shutil.copy2(src / f, d / f)
    arr = np.asarray(blend, float)
    assert (arr > 0).all() and arr[1] > 0
    np.save(d / 'blend_weights.npy', arr)
    (d / 'archive_priors.json').write_text(json.dumps(priors, indent=2))
    (d / 'blend.json').write_text(json.dumps({'blend': blend, 'priors': priors, 'wave': 'R4'}, indent=2))

# R3b solar/rad base (KEEP gains)
def r3b_base():
    return {
        'enabled': True,
        'rad_gcr_prior': {'enabled': True, 'scale': 1.18, 'add_mSv': 0.018},
        'dust_ldex_prior': dict(l20_dust),
        'regime_rules': {
            'enabled': True,
            'flare_rise': {
                'solar': {'scale': 1.10, 'add': 0.28},
                'radiation': {'scale': 1.04, 'add': 0.0, 'couple_from_solar': 0.015},
            },
            'storm': {
                'solar': {'scale': 1.20, 'add': 0.65},
                'radiation': {'scale': 1.08, 'add': 0.0, 'couple_from_solar': 0.03},
            },
            'sep_like': {
                'solar': {'scale': 1.14, 'add': 0.45},
                'radiation': {'scale': 1.10, 'add': 0.005, 'couple_from_solar': 0.04},
            },
        },
    }

# A-optimal LST adds (fraction applied via scale): morning+15, aft-14, eve-11, late-4.5, dusk+37
A_LST_BINS = [
    {'start': 0, 'end': 5, 'add': -4.5},
    {'start': 5, 'end': 11, 'add': 15.0},
    {'start': 11, 'end': 14, 'add': -1.0},
    {'start': 14, 'end': 17, 'add': -14.0},
    {'start': 17, 'end': 18, 'add': 20.0},  # capped vs raw +37
    {'start': 18, 'end': 24, 'add': -11.0},
]

cands = {}

# --- Corrected day+/night- (R3t had night=+ KILL) ---
p = r3b_base()
p['seasonal_temp'] = {'enabled': True, 'diviner_pull': 0.0, 'seasonal_scale': 0.0,
                      'day_add_C': 1.5, 'night_add_C': -2.0}
cands['R4t_dn_correct_mild'] = (base_blend, p)

p = r3b_base()
p['seasonal_temp'] = {'enabled': True, 'diviner_pull': 0.0, 'seasonal_scale': 0.0,
                      'day_add_C': 3.0, 'night_add_C': -4.0}
cands['R4t2_dn_correct_med'] = (base_blend, p)

p = r3b_base()
p['seasonal_temp'] = {'enabled': True, 'diviner_pull': 0.0, 'seasonal_scale': 0.0,
                      'day_add_C': 5.0, 'night_add_C': -6.5}
cands['R4t3_dn_correct_optA'] = (base_blend, p)

# morning-heavy day window (5-17) — captures cold dawn
p = r3b_base()
p['seasonal_temp'] = {'enabled': True, 'diviner_pull': 0.0, 'seasonal_scale': 0.0,
                      'day_start_hour': 5.0, 'day_end_hour': 17.0,
                      'day_add_C': 4.0, 'night_add_C': -5.0}
cands['R4t4_dn_dawn_window'] = (base_blend, p)

# --- Diviner residual only (no day/night) ---
p = r3b_base()
p['seasonal_temp'] = {'enabled': True, 'diviner_pull': 0.03, 'seasonal_scale': 0.0,
                      'day_add_C': 0.0, 'night_add_C': 0.0}
cands['R4d_diviner_03'] = (base_blend, p)

p = r3b_base()
p['seasonal_temp'] = {'enabled': True, 'diviner_pull': 0.08, 'seasonal_scale': 0.0,
                      'day_add_C': 0.0, 'night_add_C': 0.0}
cands['R4d2_diviner_08'] = (base_blend, p)

p = r3b_base()
p['seasonal_temp'] = {'enabled': True, 'diviner_pull': 0.15, 'seasonal_scale': 0.0,
                      'day_add_C': 0.0, 'night_add_C': 0.0}
cands['R4d3_diviner_15'] = (base_blend, p)

# Diviner + corrected mild DN
p = r3b_base()
p['seasonal_temp'] = {'enabled': True, 'diviner_pull': 0.06, 'seasonal_scale': 0.0,
                      'day_add_C': 1.5, 'night_add_C': -2.0}
cands['R4d4_diviner_dn_mild'] = (base_blend, p)

# --- Seasonal archive ---
p = r3b_base()
p['seasonal_temp'] = {'enabled': True, 'diviner_pull': 0.0, 'seasonal_scale': 0.5,
                      'day_add_C': 0.0, 'night_add_C': 0.0}
cands['R4s_seasonal_05'] = (base_blend, p)

p = r3b_base()
p['seasonal_temp'] = {'enabled': True, 'diviner_pull': 0.0, 'seasonal_scale': 1.0,
                      'day_add_C': 0.0, 'night_add_C': 0.0}
cands['R4s2_seasonal_10'] = (base_blend, p)

p = r3b_base()
p['seasonal_temp'] = {'enabled': True, 'diviner_pull': 0.05, 'seasonal_scale': 0.5,
                      'day_add_C': 1.0, 'night_add_C': -1.5}
cands['R4s3_seasonal_div_dn'] = (base_blend, p)

# --- LST bins (fraction of A-optimal) ---
p = r3b_base()
p['seasonal_temp'] = {
    'enabled': True, 'diviner_pull': 0.0, 'seasonal_scale': 0.0,
    'day_add_C': 0.0, 'night_add_C': 0.0,
    'lst_bins': {'enabled': True, 'scale': 0.25, 'bins': A_LST_BINS},
}
cands['R4l_lst_bins_25'] = (base_blend, p)

p = r3b_base()
p['seasonal_temp'] = {
    'enabled': True, 'diviner_pull': 0.0, 'seasonal_scale': 0.0,
    'day_add_C': 0.0, 'night_add_C': 0.0,
    'lst_bins': {'enabled': True, 'scale': 0.40, 'bins': A_LST_BINS},
}
cands['R4l2_lst_bins_40'] = (base_blend, p)

p = r3b_base()
p['seasonal_temp'] = {
    'enabled': True, 'diviner_pull': 0.04, 'seasonal_scale': 0.0,
    'day_add_C': 0.0, 'night_add_C': 0.0,
    'lst_bins': {'enabled': True, 'scale': 0.30, 'bins': A_LST_BINS},
}
cands['R4l3_lst30_div04'] = (base_blend, p)

# --- Physics pull asymmetric ---
p = r3b_base()
p['seasonal_temp'] = {
    'enabled': True, 'diviner_pull': 0.0, 'seasonal_scale': 0.0,
    'day_add_C': 0.0, 'night_add_C': 0.0,
    'physics_pull': {'enabled': True, 'alpha_up': 0.35, 'alpha_down': 0.35},
}
cands['R4p_physics_pull_35'] = (base_blend, p)

p = r3b_base()
p['seasonal_temp'] = {
    'enabled': True, 'diviner_pull': 0.0, 'seasonal_scale': 0.0,
    'day_add_C': 1.5, 'night_add_C': -2.0,
    'physics_pull': {'enabled': True, 'alpha_up': 0.25, 'alpha_down': 0.25},
}
cands['R4p2_phys_dn_mild'] = (base_blend, p)

# --- Regime temperature (quiet cooler night via unsettled/quiet) ---
p = r3b_base()
p['regime_rules']['quiet'] = {'temperature': {'add': -1.0}}
p['regime_rules']['unsettled'] = {'temperature': {'add': -0.5}}
p['seasonal_temp'] = {'enabled': True, 'diviner_pull': 0.0, 'seasonal_scale': 0.0,
                      'day_add_C': 2.0, 'night_add_C': -2.5}
cands['R4r_regime_temp_dn'] = (base_blend, p)

for name, (blend, priors) in cands.items():
    pack(name, blend, priors)
print('built', sorted(cands))
PY

score_pair() {
  local tag="$1"
  local model_dir="$OUT/cands/$tag"
  local o="$OUT/windows_$tag"
  mkdir -p "$o/A" "$o/B_storm"
  echo "=== $tag A ==="
  python logs/overnight_improve/train4/run_on_cpu.py scripts/run_14day_flagship_study.py \
    --csv "$WIN_CSV" --model-dir "$model_dir" \
    --start 2026-06-17 --end 2026-07-14 --window-label A --out-dir "$o/A" \
    >"$o/A.log" 2>"$o/A.err" || true
  echo "=== $tag B ==="
  python logs/overnight_improve/train4/run_on_cpu.py scripts/run_14day_flagship_study.py \
    --csv "$WIN_CSV" --model-dir "$model_dir" \
    --start 2024-05-04 --end 2024-05-17 --window-label C --out-dir "$o/B_storm" \
    >"$o/B.log" 2>"$o/B.err" || true
  python - <<PY
import json
from pathlib import Path
o = Path("$o")
wins = {}
deltas = {}
abs_h = {}
for label, sub in [("A", "A"), ("B_storm", "B_storm")]:
    p = o / sub / "summary.json"
    if not p.exists():
        wins[label] = {"wins": None}
        continue
    m = (json.loads(p.read_text()).get("metrics") or {})
    beat = {}
    dlt = {}
    ah = {}
    n = t = 0
    for h, v in m.items():
        if not isinstance(v, dict) or "hybrid" not in v:
            continue
        t += 1
        hr = float(v["hybrid"]["rmse"])
        fr = float(v["flagship"]["rmse"])
        b = hr < fr
        beat[h] = b
        dlt[h] = fr - hr
        ah[h] = hr
        if b:
            n += 1
    wins[label] = {"wins": n, "total": t, "beat_map": beat}
    deltas[label] = dlt
    abs_h[label] = ah
payload = {"tag": "$tag", "wins": wins, "deltas_flagship_minus_hybrid": deltas, "abs_hybrid_rmse": abs_h}
(o / "window_wins.json").write_text(json.dumps(payload, indent=2))
print("$tag", json.dumps(payload))
a = wins.get("A", {}).get("wins")
b = wins.get("B_storm", {}).get("wins")
ta = (abs_h.get("A") or {}).get("temperature_C")
note = f"tempA={ta}"
open("logs/overnight_improve/train4/drastic_wins_ledger.md", "a").write(
    f"| {__import__('datetime').datetime.utcnow().strftime('%Y-%m-%dT%H:%MZ')} | $tag | {a} | {b} | {note} |\n"
)
# interim push helper artifact
Path("studies/drastic_wins").mkdir(parents=True, exist_ok=True)
Path("studies/drastic_wins/R4_INTERIM_latest.json").write_text(json.dumps(payload, indent=2))
PY
}

for tag in \
  R4t_dn_correct_mild \
  R4t2_dn_correct_med \
  R4t3_dn_correct_optA \
  R4t4_dn_dawn_window \
  R4d_diviner_03 \
  R4d2_diviner_08 \
  R4d3_diviner_15 \
  R4d4_diviner_dn_mild \
  R4s_seasonal_05 \
  R4s2_seasonal_10 \
  R4s3_seasonal_div_dn \
  R4l_lst_bins_25 \
  R4l2_lst_bins_40 \
  R4l3_lst30_div04 \
  R4p_physics_pull_35 \
  R4p2_phys_dn_mild \
  R4r_regime_temp_dn
do
  score_pair "$tag"
done

python - <<'PY'
import json
from pathlib import Path
out = Path('logs/overnight_improve/train4/cpu_levers')
rows = []
for p in sorted(out.glob('windows_R4*/window_wins.json')):
    rows.append(json.loads(p.read_text()))
ref = {}
for tag in ('L20_may_dust_l16', 'R3b_solar120_m2rad', 'R2m2_solar115_rad'):
    wp = out / f'windows_{tag}' / 'window_wins.json'
    if wp.exists():
        ref[tag] = json.loads(wp.read_text())
(out / 'drastic_R4_summary.json').write_text(json.dumps({
    'refs': ref, 'cands': rows, 'promote': 'NOT_READY',
    'focus': 'TEMP on R3b base; avoid R3t night_add=+ kill',
}, indent=2))
print('wrote', out / 'drastic_R4_summary.json', 'n=', len(rows))
PY

logrow "WAVE R4 DONE | - | - | - | see cpu_levers/drastic_R4_summary.json |"
echo "R4 complete"
