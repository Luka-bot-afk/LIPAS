#!/usr/bin/env bash
# Wave R1: regime-rulebook hybrid-only priors on frozen train-2 LSTM (L20 blend base).
# Mac/cloud: score Window A + storm B only. No mission/ablation/paper.
set -euo pipefail
# scripts/drastic_wins/ -> repo root is ../..
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"
if [[ -f .venv/bin/activate ]]; then
  # shellcheck disable=SC1091
  source .venv/bin/activate
fi
export ALLOW_TRAIN4=1 TF_CPP_MIN_LOG_LEVEL=2 PYTHONUNBUFFERED=1
export SETUPTOOLS_USE_DISTUTILS=local CUDA_VISIBLE_DEVICES="${CUDA_VISIBLE_DEVICES:-}"
LEDGER=logs/overnight_improve/train4/drastic_wins_ledger.md
OUT=logs/overnight_improve/train4/cpu_levers
WIN_CSV=data/ingested_extended/extended_training_window_B_ready.csv
SRC=papers/appendix_numerical_tables/locked_saved_model
mkdir -p "$OUT" logs/overnight_improve/train4/cpu_levers/cands
[[ -f "$LEDGER" ]] || printf '| utc | tag | A_wins | B_wins | notes |\n|---|---|---:|---:|---|\n' >"$LEDGER"
logrow() { printf '| %s | %s\n' "$(date -u +%Y-%m-%dT%H:%MZ)" "$1" >> "$LEDGER"; }
logrow "WAVE R1 START | - | - | - | regime solar/rad/mq/temp + GCR variants |"

python - <<'PY'
import json, shutil
from pathlib import Path
import numpy as np

root = Path('logs/overnight_improve/train4/cpu_levers/cands')
src = Path('papers/appendix_numerical_tables/locked_saved_model')
base_blend = [0.40, 0.15, 0.02, 0.02, 0.03, 0.01]
l20_dust = {
    'enabled': True,
    'scale': 1.0,
    'add_g_cm3': 0.0,
    'may_trough': {
        'enabled': True, 'doy_start': 121, 'doy_end': 151,
        'scale': 0.975, 'add_g_cm3': -0.03,
    },
}
l20_gcr = {'enabled': True, 'scale': 1.15, 'add_mSv': 0.015}

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
    (d / 'blend.json').write_text(json.dumps({'blend': blend, 'priors': priors, 'wave': 'R1'}, indent=2))

cands = {}

# --- Mac first lever: solar storm climatology + flare-rise (hybrid-only) ---
cands['R1s_solar_clim_pull15'] = (
    base_blend,
    {
        'enabled': True,
        'rad_gcr_prior': dict(l20_gcr),
        'dust_ldex_prior': dict(l20_dust),
        'solar_storm_climatology': {
            'enabled': True,
            'target': 22.0,
            'blend': 0.15,
            'levels': ['storm', 'flare_rise', 'sep_like'],
            'pull_by_level': {'flare_rise': 0.08, 'storm': 0.18, 'sep_like': 0.20},
        },
        'regime_rules': {'enabled': True},
    },
)
cands['R1s2_solar_clim_pull25'] = (
    base_blend,
    {
        'enabled': True,
        'rad_gcr_prior': dict(l20_gcr),
        'dust_ldex_prior': dict(l20_dust),
        'solar_storm_climatology': {
            'enabled': True,
            'target': 24.0,
            'blend': 0.25,
            'levels': ['storm', 'flare_rise', 'sep_like', 'unsettled'],
            'pull_by_level': {'unsettled': 0.05, 'flare_rise': 0.12, 'storm': 0.28, 'sep_like': 0.30},
            'doy_amp': 1.5,
            'doy_phase': 125.0,
        },
        'regime_rules': {
            'enabled': True,
            'flare_rise': {'solar': {'scale': 1.03, 'add': 0.1}},
            'storm': {'solar': {'scale': 1.05, 'add': 0.15}},
        },
    },
)
cands['R1s3_solar_clim_low_target'] = (
    base_blend,
    {
        'enabled': True,
        'rad_gcr_prior': dict(l20_gcr),
        'dust_ldex_prior': dict(l20_dust),
        # If physics over-predicts storm solar labels, pull DOWN toward quieter storm mean.
        'solar_storm_climatology': {
            'enabled': True,
            'target': 16.0,
            'blend': 0.20,
            'levels': ['storm', 'flare_rise', 'sep_like'],
            'pull_by_level': {'flare_rise': 0.10, 'storm': 0.22, 'sep_like': 0.18},
        },
        'regime_rules': {'enabled': True},
    },
)

# R1a: storm/flare solar physics-scale to break B tie
cands['R1a_storm_solar_108'] = (
    base_blend,
    {
        'enabled': True,
        'rad_gcr_prior': dict(l20_gcr),
        'dust_ldex_prior': dict(l20_dust),
        'regime_rules': {
            'enabled': True,
            'flare_rise': {'solar': {'scale': 1.05, 'add': 0.15}},
            'storm': {'solar': {'scale': 1.08, 'add': 0.25}},
            'sep_like': {'solar': {'scale': 1.06, 'add': 0.2}},
        },
    },
)
cands['R1a2_storm_solar_112'] = (
    base_blend,
    {
        'enabled': True,
        'rad_gcr_prior': dict(l20_gcr),
        'dust_ldex_prior': dict(l20_dust),
        'regime_rules': {
            'enabled': True,
            'flare_rise': {'solar': {'scale': 1.06, 'add': 0.2}},
            'storm': {'solar': {'scale': 1.12, 'add': 0.4}},
            'sep_like': {'solar': {'scale': 1.08, 'add': 0.3}},
        },
    },
)
cands['R1a3_storm_solar_add_only'] = (
    base_blend,
    {
        'enabled': True,
        'rad_gcr_prior': dict(l20_gcr),
        'dust_ldex_prior': dict(l20_dust),
        'regime_rules': {
            'enabled': True,
            'flare_rise': {'solar': {'scale': 1.0, 'add': 0.35}},
            'storm': {'solar': {'scale': 1.0, 'add': 0.8}},
            'sep_like': {'solar': {'scale': 1.0, 'add': 0.6}},
        },
    },
)

# R1c: solar + rad coupling
cands['R1c_storm_couple'] = (
    base_blend,
    {
        'enabled': True,
        'rad_gcr_prior': {'enabled': True, 'scale': 1.18, 'add_mSv': 0.018},
        'dust_ldex_prior': dict(l20_dust),
        'regime_rules': {
            'enabled': True,
            'flare_rise': {
                'solar': {'scale': 1.05, 'add': 0.15},
                'radiation': {'scale': 1.04, 'add': 0.0, 'couple_from_solar': 0.015},
            },
            'storm': {
                'solar': {'scale': 1.08, 'add': 0.25},
                'radiation': {'scale': 1.08, 'add': 0.0, 'couple_from_solar': 0.03},
            },
            'sep_like': {
                'solar': {'scale': 1.06, 'add': 0.2},
                'radiation': {'scale': 1.10, 'add': 0.005, 'couple_from_solar': 0.04},
            },
        },
    },
)

# R1d: stronger GCR only (control)
cands['R1d_gcr_120'] = (
    base_blend,
    {
        'enabled': True,
        'rad_gcr_prior': {'enabled': True, 'scale': 1.20, 'add_mSv': 0.02},
        'dust_ldex_prior': dict(l20_dust),
        'regime_rules': {'enabled': True},
    },
)

# R1e: temp day/night bias (no ML raise)
cands['R1e_temp_daynight'] = (
    base_blend,
    {
        'enabled': True,
        'rad_gcr_prior': dict(l20_gcr),
        'dust_ldex_prior': dict(l20_dust),
        'seasonal_temp': {
            'enabled': True,
            'diviner_pull': 0.0,
            'seasonal_scale': 0.0,
            'day_add_C': -0.35,
            'night_add_C': 0.25,
        },
        'regime_rules': {'enabled': True},
    },
)

# R1f: moonquake tidal + terminator
cands['R1f_mq_tidal'] = (
    base_blend,
    {
        'enabled': True,
        'rad_gcr_prior': dict(l20_gcr),
        'dust_ldex_prior': dict(l20_dust),
        'moonquake_prior': {
            'enabled': True,
            'scale': 1.0,
            'add': 0.0,
            'terminator_bump': True,
            'terminator_hours': 4.0,
            'terminator_add': 0.8,
            'tidal_amp': 0.6,
            'tidal_phase_doy': 0.0,
        },
        'regime_rules': {
            'enabled': True,
            'storm': {'moonquakes': {'scale': 1.04, 'add': 0.2}},
            'unsettled': {'moonquakes': {'scale': 1.02, 'add': 0.1}},
        },
    },
)

# R1g: combo bar shot
cands['R1g_combo'] = (
    base_blend,
    {
        'enabled': True,
        'rad_gcr_prior': {'enabled': True, 'scale': 1.18, 'add_mSv': 0.018},
        'dust_ldex_prior': dict(l20_dust),
        'seasonal_temp': {
            'enabled': True,
            'day_add_C': -0.25,
            'night_add_C': 0.2,
            'seasonal_scale': 0.0,
        },
        'moonquake_prior': {
            'enabled': True,
            'terminator_bump': True,
            'terminator_add': 0.5,
            'tidal_amp': 0.4,
        },
        'regime_rules': {
            'enabled': True,
            'flare_rise': {
                'solar': {'scale': 1.05, 'add': 0.15},
                'radiation': {'scale': 1.04, 'couple_from_solar': 0.015},
            },
            'storm': {
                'solar': {'scale': 1.09, 'add': 0.3},
                'radiation': {'scale': 1.07, 'couple_from_solar': 0.025},
                'moonquakes': {'scale': 1.03, 'add': 0.15},
            },
            'sep_like': {
                'solar': {'scale': 1.07, 'add': 0.25},
                'radiation': {'scale': 1.10, 'add': 0.005, 'couple_from_solar': 0.035},
            },
        },
    },
)

# R2a: selective more solar ML (quiet) — still storm-capped by adaptive gate
cands['R2a_wsolar_50'] = (
    [0.50, 0.15, 0.02, 0.02, 0.03, 0.01],
    {
        'enabled': True,
        'rad_gcr_prior': dict(l20_gcr),
        'dust_ldex_prior': dict(l20_dust),
        'regime_rules': {
            'enabled': True,
            'storm': {'solar': {'scale': 1.08, 'add': 0.25}},
            'flare_rise': {'solar': {'scale': 1.05, 'add': 0.15}},
        },
    },
)
cands['R2b_wrad_20'] = (
    [0.40, 0.20, 0.02, 0.02, 0.03, 0.01],
    {
        'enabled': True,
        'rad_gcr_prior': dict(l20_gcr),
        'dust_ldex_prior': dict(l20_dust),
        'regime_rules': {
            'enabled': True,
            'storm': {
                'solar': {'scale': 1.08, 'add': 0.25},
                'radiation': {'scale': 1.06, 'couple_from_solar': 0.02},
            },
        },
    },
)

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
  if [[ -f logs/overnight_improve/train4/run_on_cpu.py ]]; then
    python logs/overnight_improve/train4/run_on_cpu.py scripts/run_14day_flagship_study.py \
      --csv "$WIN_CSV" --model-dir "$model_dir" \
      --start 2026-06-17 --end 2026-07-14 --window-label A --out-dir "$o/A" \
      >"$o/A.log" 2>"$o/A.err" || true
  else
    python scripts/run_14day_flagship_study.py \
      --csv "$WIN_CSV" --model-dir "$model_dir" \
      --start 2026-06-17 --end 2026-07-14 --window-label A --out-dir "$o/A" \
      >"$o/A.log" 2>"$o/A.err" || true
  fi
  echo "=== $tag B ==="
  if [[ -f logs/overnight_improve/train4/run_on_cpu.py ]]; then
    python logs/overnight_improve/train4/run_on_cpu.py scripts/run_14day_flagship_study.py \
      --csv "$WIN_CSV" --model-dir "$model_dir" \
      --start 2024-05-04 --end 2024-05-17 --window-label C --out-dir "$o/B_storm" \
      >"$o/B.log" 2>"$o/B.err" || true
  else
    python scripts/run_14day_flagship_study.py \
      --csv "$WIN_CSV" --model-dir "$model_dir" \
      --start 2024-05-04 --end 2024-05-17 --window-label C --out-dir "$o/B_storm" \
      >"$o/B.log" 2>"$o/B.err" || true
  fi
  python - <<PY
import json
from pathlib import Path
o = Path("$o")
wins = {}
deltas = {}
for label, sub in [("A", "A"), ("B_storm", "B_storm")]:
    p = o / sub / "summary.json"
    if not p.exists():
        wins[label] = {"wins": None}
        continue
    m = (json.loads(p.read_text()).get("metrics") or {})
    beat = {}
    dlt = {}
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
        if b:
            n += 1
    wins[label] = {"wins": n, "total": t, "beat_map": beat}
    deltas[label] = dlt
payload = {"tag": "$tag", "wins": wins, "deltas_flagship_minus_hybrid": deltas}
(o / "window_wins.json").write_text(json.dumps(payload, indent=2))
print("$tag", json.dumps(payload))
a = wins.get("A", {}).get("wins")
b = wins.get("B_storm", {}).get("wins")
note = "solarB=" + str(wins.get("B_storm", {}).get("beat_map", {}).get("solar_activity"))
open("logs/overnight_improve/train4/drastic_wins_ledger.md", "a").write(
    f"| {__import__('datetime').datetime.utcnow().strftime('%Y-%m-%dT%H:%MZ')} | $tag | {a} | {b} | {note} |\n"
)
PY
}

for tag in \
  R1s_solar_clim_pull15 \
  R1s2_solar_clim_pull25 \
  R1s3_solar_clim_low_target \
  R1a_storm_solar_108 \
  R1a2_storm_solar_112 \
  R1a3_storm_solar_add_only \
  R1c_storm_couple \
  R1d_gcr_120 \
  R1e_temp_daynight \
  R1f_mq_tidal \
  R1g_combo \
  R2a_wsolar_50 \
  R2b_wrad_20
do
  score_pair "$tag"
done

python - <<'PY'
import json
from pathlib import Path
out = Path('logs/overnight_improve/train4/cpu_levers')
rows = []
for p in sorted(out.glob('windows_R*/window_wins.json')):
    rows.append(json.loads(p.read_text()))
# also include L20 reference if present
l20 = out / 'windows_L20_may_dust_l16' / 'window_wins.json'
ref = json.loads(l20.read_text()) if l20.exists() else None
(out / 'drastic_R1_summary.json').write_text(json.dumps({'ref_L20': ref, 'cands': rows}, indent=2))
print('wrote', out / 'drastic_R1_summary.json', 'n=', len(rows))
PY

logrow "WAVE R1 DONE | - | - | - | see cpu_levers/drastic_R1_summary.json |"
echo "R1 complete"
