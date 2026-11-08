#!/usr/bin/env bash
# Wave R2: merge R1a2 solar strength × R1c rad couple; climb margins. No mq tidal. No paper.
set -euo pipefail
# scripts/drastic_wins/ -> repo root is ../..
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
logrow "WAVE R2 START | - | - | - | merge R1a2 solar + R1c rad; no mq tidal |"

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
    (d / 'blend.json').write_text(json.dumps({'blend': blend, 'priors': priors, 'wave': 'R2'}, indent=2))

def solar_rule(scale_s, add_s, scale_f=None, add_f=None, scale_sep=None, add_sep=None):
    scale_f = scale_s if scale_f is None else scale_f
    add_f = add_s * 0.5 if add_f is None else add_f
    scale_sep = (scale_s + scale_f) / 2 if scale_sep is None else scale_sep
    add_sep = (add_s + add_f) / 2 if add_sep is None else add_sep
    return {
        'flare_rise': {'solar': {'scale': scale_f, 'add': add_f}},
        'storm': {'solar': {'scale': scale_s, 'add': add_s}},
        'sep_like': {'solar': {'scale': scale_sep, 'add': add_sep}},
    }

def with_rad(rules, gcr_scale, gcr_add, couple_s, couple_f=None, couple_sep=None, rad_scale_s=1.08, rad_scale_f=1.04, rad_scale_sep=1.10):
    couple_f = couple_s * 0.5 if couple_f is None else couple_f
    couple_sep = couple_s * 1.2 if couple_sep is None else couple_sep
    out = {'enabled': True}
    for lvl, (cs, rs, ca) in {
        'flare_rise': (couple_f, rad_scale_f, 0.0),
        'storm': (couple_s, rad_scale_s, 0.0),
        'sep_like': (couple_sep, rad_scale_sep, 0.005),
    }.items():
        base = dict(rules.get(lvl) or {})
        sol = dict(base.get('solar') or {})
        base['solar'] = sol
        base['radiation'] = {'scale': rs, 'add': ca, 'couple_from_solar': cs}
        out[lvl] = base
    return {
        'enabled': True,
        'rad_gcr_prior': {'enabled': True, 'scale': gcr_scale, 'add_mSv': gcr_add},
        'dust_ldex_prior': dict(l20_dust),
        'regime_rules': out,
    }

cands = {}

# R2m: merge R1a2 solar (1.12/0.4) + R1c rad couple/GCR
r = solar_rule(1.12, 0.4, scale_f=1.06, add_f=0.2, scale_sep=1.08, add_sep=0.3)
cands['R2m_a2_c'] = (base_blend, with_rad(r, 1.18, 0.018, 0.03, 0.015, 0.04))

# stronger solar + same rad
r = solar_rule(1.15, 0.55, scale_f=1.08, add_f=0.25, scale_sep=1.10, add_sep=0.35)
cands['R2m2_solar115_rad'] = (base_blend, with_rad(r, 1.18, 0.018, 0.03, 0.015, 0.04))

# R1a2 solar + harder rad couple
r = solar_rule(1.12, 0.4, scale_f=1.06, add_f=0.2, scale_sep=1.08, add_sep=0.3)
cands['R2m3_rad_hard'] = (base_blend, with_rad(r, 1.22, 0.022, 0.05, 0.025, 0.06, rad_scale_s=1.12, rad_scale_f=1.06, rad_scale_sep=1.14))

# max solar climb (watch quiet A)
r = solar_rule(1.18, 0.7, scale_f=1.10, add_f=0.3, scale_sep=1.12, add_sep=0.4)
cands['R2m4_solar118'] = (base_blend, with_rad(r, 1.18, 0.018, 0.03, 0.015, 0.04))

# persist-style via sep_like/storm higher add (no new hook): large storm add
r = solar_rule(1.12, 1.2, scale_f=1.06, add_f=0.5, scale_sep=1.10, add_sep=0.9)
cands['R2m5_solar_add_hard'] = (base_blend, with_rad(r, 1.20, 0.02, 0.04, 0.02, 0.05))

# mild temp day/night on merge (no ML, no mq)
p = with_rad(solar_rule(1.12, 0.4, scale_f=1.06, add_f=0.2, scale_sep=1.08, add_sep=0.3), 1.18, 0.018, 0.03, 0.015, 0.04)
p['seasonal_temp'] = {'enabled': True, 'diviner_pull': 0.08, 'day_add_C': -0.4, 'night_add_C': 0.6, 'seasonal_scale': 0.0}
cands['R2t_merge_temp_mild'] = (base_blend, p)

# quiet-safe: unsettled also gets tiny solar lift
p = with_rad(solar_rule(1.12, 0.4, scale_f=1.06, add_f=0.2, scale_sep=1.08, add_sep=0.3), 1.18, 0.018, 0.03, 0.015, 0.04)
p['regime_rules']['unsettled'] = {'solar': {'scale': 1.02, 'add': 0.05}, 'radiation': {'scale': 1.02, 'couple_from_solar': 0.008}}
cands['R2u_unsettled_soft'] = (base_blend, p)

# IMF/score soft via sep_like heavier + GCR
r = solar_rule(1.14, 0.5, scale_f=1.07, add_f=0.22, scale_sep=1.15, add_sep=0.55)
cands['R2s_sep_heavy'] = (base_blend, with_rad(r, 1.24, 0.025, 0.055, 0.02, 0.07, rad_scale_s=1.10, rad_scale_f=1.05, rad_scale_sep=1.16))

# persist pull (inputs[0]) + R1a2/R1c merge — capped uplift only
p = with_rad(solar_rule(1.12, 0.4, scale_f=1.06, add_f=0.2, scale_sep=1.08, add_sep=0.3), 1.18, 0.018, 0.03, 0.015, 0.04)
p['solar_persist_pull'] = {
    'enabled': True, 'up_only': True, 'cap': 10.0,
    'levels': ['storm', 'flare_rise', 'sep_like'],
    'alpha_by_level': {'flare_rise': 0.25, 'storm': 0.45, 'sep_like': 0.55},
}
cands['R2p_persist_merge'] = (base_blend, p)

p2 = with_rad(solar_rule(1.12, 0.4, scale_f=1.06, add_f=0.2, scale_sep=1.08, add_sep=0.3), 1.20, 0.02, 0.04, 0.02, 0.05)
p2['solar_persist_pull'] = {
    'enabled': True, 'up_only': True, 'cap': 14.0,
    'levels': ['storm', 'sep_like'],
    'alpha_by_level': {'storm': 0.55, 'sep_like': 0.65},
}
cands['R2p2_persist_storm_only'] = (base_blend, p2)

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
  R2m_a2_c \
  R2m2_solar115_rad \
  R2m3_rad_hard \
  R2m4_solar118 \
  R2m5_solar_add_hard \
  R2t_merge_temp_mild \
  R2u_unsettled_soft \
  R2s_sep_heavy \
  R2p_persist_merge \
  R2p2_persist_storm_only
do
  score_pair "$tag"
done

python - <<'PY'
import json
from pathlib import Path
out = Path('logs/overnight_improve/train4/cpu_levers')
rows = []
for p in sorted(out.glob('windows_R2*/window_wins.json')):
    rows.append(json.loads(p.read_text()))
l20 = out / 'windows_L20_may_dust_l16' / 'window_wins.json'
ref = json.loads(l20.read_text()) if l20.exists() else None
(out / 'drastic_R2_summary.json').write_text(json.dumps({'ref_L20': ref, 'cands': rows}, indent=2))
print('wrote', out / 'drastic_R2_summary.json', 'n=', len(rows))
PY

logrow "WAVE R2 DONE | - | - | - | see cpu_levers/drastic_R2_summary.json |"
echo "R2 complete"
