#!/usr/bin/env bash
# Wave R3: post-regime soft persist + climb past R2m2. No paper. User lock: not READY until drastic.
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
logrow "WAVE R3 START | - | - | - | post-regime persist + solar climb; NOT_READY lock |"

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
    (d / 'blend.json').write_text(json.dumps({'blend': blend, 'priors': priors, 'wave': 'R3'}, indent=2))

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

def with_rad(rules, gcr_scale, gcr_add, couple_s, couple_f=None, couple_sep=None,
             rad_scale_s=1.08, rad_scale_f=1.04, rad_scale_sep=1.10, couple_max=None):
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
        rad = {'scale': rs, 'add': ca, 'couple_from_solar': cs}
        if couple_max is not None:
            rad['couple_max_add'] = couple_max
        base['radiation'] = rad
        out[lvl] = base
    return {
        'enabled': True,
        'rad_gcr_prior': {'enabled': True, 'scale': gcr_scale, 'add_mSv': gcr_add},
        'dust_ldex_prior': dict(l20_dust),
        'regime_rules': out,
    }

def soft_persist(alpha_storm=0.18, cap=5.0, levels=None, min_gap=2.0, flare=0.08, sep=0.22):
    levels = levels or ['storm', 'sep_like']
    return {
        'enabled': True, 'up_only': True, 'cap': cap, 'min_sa_gap': min_gap,
        'levels': levels,
        'alpha_by_level': {'flare_rise': flare, 'storm': alpha_storm, 'sep_like': sep},
    }

# R2m2 baseline priors (solar 1.15/0.55 + rad couple 0.03)
def m2_base():
    r = solar_rule(1.15, 0.55, scale_f=1.08, add_f=0.25, scale_sep=1.10, add_sep=0.35)
    return with_rad(r, 1.18, 0.018, 0.03, 0.015, 0.04)

cands = {}

# R3a: R2m2 + post-regime soft persist (storm/sep only, min gap)
p = m2_base()
p['solar_persist_pull'] = soft_persist(0.18, 5.0, ['storm', 'sep_like'], 2.0, sep=0.22)
cands['R3a_m2_soft_persist'] = (base_blend, p)

# R3a2: slightly harder soft persist
p = m2_base()
p['solar_persist_pull'] = soft_persist(0.28, 8.0, ['storm', 'sep_like'], 1.5, sep=0.32)
cands['R3a2_m2_persist_med'] = (base_blend, p)

# R3a3: storm-only soft persist + couple_max
p = with_rad(solar_rule(1.15, 0.55, scale_f=1.08, add_f=0.25, scale_sep=1.10, add_sep=0.35),
             1.18, 0.018, 0.03, 0.015, 0.04, couple_max=0.04)
p['solar_persist_pull'] = soft_persist(0.35, 10.0, ['storm'], 1.0, sep=0.0)
cands['R3a3_persist_storm_cmax'] = (base_blend, p)

# R3b: solar climb 1.20 with m2 rad (watch mq)
r = solar_rule(1.20, 0.65, scale_f=1.10, add_f=0.28, scale_sep=1.14, add_sep=0.45)
cands['R3b_solar120_m2rad'] = (base_blend, with_rad(r, 1.18, 0.018, 0.03, 0.015, 0.04))

# R3b2: solar 1.20 + soft mq terminator (no tidal — R1f killed tidal)
p = with_rad(solar_rule(1.20, 0.65, scale_f=1.10, add_f=0.28, scale_sep=1.14, add_sep=0.45),
             1.18, 0.018, 0.03, 0.015, 0.04)
p['moonquake_prior'] = {
    'enabled': True, 'scale': 1.0, 'add': 0.0,
    'terminator_bump': True, 'terminator_hours': 3.0, 'terminator_add': 0.25,
    'tidal_amp': 0.0,
}
cands['R3b2_solar120_mq_soft'] = (base_blend, p)

# R3c: R2m5-class solar add + m2 rad + couple_max
r = solar_rule(1.12, 1.0, scale_f=1.06, add_f=0.45, scale_sep=1.10, add_sep=0.7)
cands['R3c_add_hard_cmax'] = (base_blend, with_rad(r, 1.18, 0.018, 0.03, 0.015, 0.04, couple_max=0.05))

# R3d: soft clim morph ON TOP of m2 (R1s naked clim killed; try tiny pull with regime)
p = m2_base()
p['solar_storm_climatology'] = {
    'enabled': True, 'target': 24.0, 'pull': 0.08,
    'levels': ['storm', 'sep_like'],
    'pull_by_level': {'storm': 0.10, 'sep_like': 0.12},
}
cands['R3d_m2_soft_clim'] = (base_blend, p)

# R3e: m2 + soft persist + soft clim (stack)
p = m2_base()
p['solar_persist_pull'] = soft_persist(0.20, 6.0, ['storm', 'sep_like'], 2.0, sep=0.25)
p['solar_storm_climatology'] = {
    'enabled': True, 'target': 23.0, 'pull': 0.06,
    'levels': ['storm', 'sep_like'],
}
cands['R3e_m2_persist_clim'] = (base_blend, p)

# R3t: night-only tiny temp (no diviner — R2t killed day/night+diviner)
p = m2_base()
p['seasonal_temp'] = {
    'enabled': True, 'diviner_pull': 0.0, 'seasonal_scale': 0.0,
    'day_add_C': 0.0, 'night_add_C': 0.25,
}
cands['R3t_night_temp_025'] = (base_blend, p)

# R3f: physics_band_clip temp-only on m2 (channels filter)
p = m2_base()
p['physics_band_clip'] = {'enabled': True, 'frac': 0.08, 'channels': ['temperature']}
cands['R3f_temp_band_clip'] = (base_blend, p)

# R3g: harder GCR + couple_max (rad climb without sep_heavy blowup)
r = solar_rule(1.15, 0.55, scale_f=1.08, add_f=0.25, scale_sep=1.10, add_sep=0.35)
cands['R3g_rad_climb_cmax'] = (base_blend, with_rad(
    r, 1.28, 0.028, 0.045, 0.02, 0.055,
    rad_scale_s=1.12, rad_scale_f=1.06, rad_scale_sep=1.14, couple_max=0.06,
))

# R3h: aggressive post-regime persist only (no extra solar scale beyond m2) — chase B solar ~12 safely
p = m2_base()
p['solar_persist_pull'] = soft_persist(0.45, 14.0, ['storm'], 0.5, sep=0.0)
cands['R3h_persist_storm_hard'] = (base_blend, p)

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
  R3a_m2_soft_persist \
  R3a2_m2_persist_med \
  R3a3_persist_storm_cmax \
  R3b_solar120_m2rad \
  R3b2_solar120_mq_soft \
  R3c_add_hard_cmax \
  R3d_m2_soft_clim \
  R3e_m2_persist_clim \
  R3t_night_temp_025 \
  R3f_temp_band_clip \
  R3g_rad_climb_cmax \
  R3h_persist_storm_hard
do
  score_pair "$tag"
done

python - <<'PY'
import json
from pathlib import Path
out = Path('logs/overnight_improve/train4/cpu_levers')
rows = []
for p in sorted(out.glob('windows_R3*/window_wins.json')):
    rows.append(json.loads(p.read_text()))
l20 = out / 'windows_L20_may_dust_l16' / 'window_wins.json'
ref = json.loads(l20.read_text()) if l20.exists() else None
m2 = out / 'windows_R2m2_solar115_rad' / 'window_wins.json'
best_r2 = json.loads(m2.read_text()) if m2.exists() else None
(out / 'drastic_R3_summary.json').write_text(json.dumps({
    'ref_L20': ref, 'best_R2_m2': best_r2, 'cands': rows,
    'promote': 'NOT_READY', 'note': 'user lock: R2m2-class still climb territory',
}, indent=2))
print('wrote', out / 'drastic_R3_summary.json', 'n=', len(rows))
PY

logrow "WAVE R3 DONE | - | - | - | see cpu_levers/drastic_R3_summary.json |"
echo "R3 complete"
