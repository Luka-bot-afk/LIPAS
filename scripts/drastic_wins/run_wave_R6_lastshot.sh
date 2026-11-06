#!/usr/bin/env bash
# Wave R6 LAST-SHOT only — untried toward NASA-wow; then TRUE_WALL or READY_R6.
# Owner: bc-43fb58ef (sole Mac). Base: R5s2_soft_plus_ew @ e7e31c1.
# Do NOT regrind R1–R5 killed families. No paper.
# Families: residual ridge/GBM gate→bias, lunar_physics knobs, caution@0 FA guard.
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
STUDIES=studies/drastic_wins
WIN_CSV=data/ingested_extended/extended_training_window_B_ready.csv
SRC=papers/appendix_numerical_tables/locked_saved_model
mkdir -p "$OUT/cands" "$STUDIES/r6_residual_gate"
[[ -f "$LEDGER" ]] || printf '| utc | tag | A_wins | B_wins | notes |\n|---|---|---:|---:|---|\n' >"$LEDGER"
logrow() { printf '| %s | %s\n' "$(date -u +%Y-%m-%dT%H:%MZ)" "$1" >> "$LEDGER"; }
logrow "WAVE R6 LASTSHOT START | - | - | - | residual+lunar+caution FA; owner bc-43fb58ef |"

echo "=== residual ridge/GBM gate ==="
python scripts/drastic_wins/probe_residual_gate.py \
  data/ingested_extended/train7_training_locked_y_ext_drivers.csv \
  "$STUDIES/r6_residual_gate"

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
A_LST_BINS = [
    {'start': 0, 'end': 5, 'add': -4.5},
    {'start': 5, 'end': 11, 'add': 15.0},
    {'start': 11, 'end': 14, 'add': -1.0},
    {'start': 14, 'end': 17, 'add': -14.0},
    {'start': 17, 'end': 18, 'add': 20.0},
    {'start': 18, 'end': 24, 'add': -11.0},
]

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
    (d / 'blend.json').write_text(json.dumps({'blend': blend, 'priors': priors, 'wave': 'R6'}, indent=2))

def r5s2_base():
    """READY_R5 best — last-shot base."""
    return {
        'enabled': True,
        'rad_gcr_prior': {'enabled': True, 'scale': 1.18, 'add_mSv': 0.018},
        'dust_ldex_prior': dict(l20_dust),
        'seasonal_temp': {
            'enabled': True, 'diviner_pull': 0.0, 'seasonal_scale': 0.0,
            'day_add_C': 0.0, 'night_add_C': 0.0,
            'lst_bins': {'enabled': True, 'scale': 0.40, 'bins': A_LST_BINS},
        },
        'regime_rules': {
            'enabled': True,
            'flare_rise': {
                'solar': {'scale': 1.10, 'add': 0.28},
                'radiation': {'scale': 1.04, 'add': 0.0, 'couple_from_solar': 0.015, 'couple_max_add': 0.04},
            },
            'storm': {
                'solar': {'scale': 1.20, 'add': 0.65},
                'radiation': {'scale': 1.08, 'add': 0.0, 'couple_from_solar': 0.03, 'couple_max_add': 0.06},
            },
            'sep_like': {
                'solar': {'scale': 1.14, 'add': 0.45},
                'radiation': {'scale': 1.10, 'add': 0.005, 'couple_from_solar': 0.04, 'couple_max_add': 0.07},
            },
        },
        'soft_regime_mix': {
            'enabled': True, 'score_lo': 0.5, 'score_hi': 2.0,
            'solar_add_at_hi': 2.0, 'rad_add_at_hi': 0.07,
        },
        'early_warning_rad': {
            'enabled': True, 'levels': ['flare_rise', 'storm', 'sep_like', 'unsettled'],
            'score_gain': 0.02, 'add_cap': 0.05, 'input_solar_gain': 0.003, 'input_solar_cap': 0.03,
        },
    }

gate = json.loads(Path('studies/drastic_wins/r6_residual_gate/residual_gate.json').read_text())
resid_prior = gate.get('residual_correct_prior') or {'enabled': False}
print('residual gate abort_metal', gate.get('abort_metal_retrain'), 'allow', gate.get('allow_residual_correct'))

cands = {}
cands['R6_base_r5s2'] = (base_blend, r5s2_base())

# --- Caution@0 false-alarm fix (quiet rad cap) ---
p = r5s2_base()
p['false_alarm_guard'] = {'enabled': True, 'levels': ['quiet'], 'quiet_rad_cap': 0.090}
cands['R6c_caution_cap090'] = (base_blend, p)

p = r5s2_base()
p['false_alarm_guard'] = {
    'enabled': True, 'levels': ['quiet'], 'quiet_rad_cap': 0.092, 'quiet_solar_cap': 12.5,
}
cands['R6c2_caution_cap092_solar'] = (base_blend, p)

# Milder GCR in quiet via formula quiet knob + FA guard (combo)
p = r5s2_base()
p['false_alarm_guard'] = {'enabled': True, 'levels': ['quiet'], 'quiet_rad_cap': 0.088}
p['lunar_physics_knobs'] = {
    'enabled': True, 'blend': 0.40,
    'radiation_knobs': {'quiet': 0.012, 'kp_storm': 0.006, 'sep_sa': 0.012},
}
cands['R6c3_caution_lunar_quiet'] = (base_blend, p)

# --- lunar_physics formula knobs (storm-leaning / kp power) ---
p = r5s2_base()
p['lunar_physics_knobs'] = {
    'enabled': True, 'blend': 0.45,
    'solar_knobs': {'kp_coef': 1.05, 'kp_pow': 1.45, 'bz_coef': 0.45, 'quiet': 4.5},
    'radiation_knobs': {'kp_storm': 0.0075, 'kp5': 0.014, 'sep_sa': 0.015},
}
cands['R6p_lunar_storm_kp'] = (base_blend, p)

p = r5s2_base()
p['lunar_physics_knobs'] = {
    'enabled': True, 'blend': 0.30,
    'solar_knobs': {'sa_w': 0.48, 'driven_w': 0.52, 'kp_coef': 0.95},
    'radiation_knobs': {'quiet': 0.015, 'lat_gain': 0.06, 'sep_sa': 0.014},
}
cands['R6p2_lunar_mild'] = (base_blend, p)

# --- Residual bias (only if gate allows) ---
if resid_prior.get('enabled'):
    p = r5s2_base()
    p['residual_correct'] = dict(resid_prior)
    p['residual_correct']['enabled'] = True
    # Drop solar unless explicitly allowed
    allow = gate.get('allow_residual_correct') or {}
    if not allow.get('solar'):
        p['residual_correct'].pop('solar', None)
    if not allow.get('radiation'):
        p['residual_correct'].pop('radiation', None)
    if not allow.get('temperature'):
        p['residual_correct'].pop('temperature', None)
    cands['R6r_resid_bias'] = (base_blend, p)

    # residual + caution guard
    p = r5s2_base()
    p['residual_correct'] = dict(cands['R6r_resid_bias'][1]['residual_correct'])
    p['false_alarm_guard'] = {'enabled': True, 'levels': ['quiet'], 'quiet_rad_cap': 0.090}
    cands['R6x_resid_caution'] = (base_blend, p)
else:
    print('SKIP residual_correct cands — gate prior disabled')

# Wall combo: caution + mild lunar (no residual regrind)
p = r5s2_base()
p['false_alarm_guard'] = {'enabled': True, 'levels': ['quiet'], 'quiet_rad_cap': 0.090}
p['lunar_physics_knobs'] = {
    'enabled': True, 'blend': 0.30,
    'solar_knobs': {'kp_coef': 1.0, 'kp_pow': 1.40},
    'radiation_knobs': {'kp_storm': 0.007, 'sep_sa': 0.013},
}
cands['R6x_caution_lunar'] = (base_blend, p)

for name, (blend, priors) in cands.items():
    pack(name, blend, priors)
print('built', sorted(cands))
Path('studies/drastic_wins/R6_CANDS.json').write_text(json.dumps(sorted(cands), indent=2))
PY

run_mission_proxy() {
  local tag="$1"
  local model_dir="$OUT/cands/$tag"
  local mo="$OUT/mission_$tag"
  mkdir -p "$mo"
  if [[ -f logs/overnight_improve/train4/run_on_cpu.py ]]; then
    python logs/overnight_improve/train4/run_on_cpu.py scripts/run_mission_sim_radiation_eva.py \
      --model-dir "$model_dir" --out-dir "$mo" \
      >"$mo/mission.log" 2>"$mo/mission.err" || true
  else
    python scripts/run_mission_sim_radiation_eva.py \
      --model-dir "$model_dir" --out-dir "$mo" \
      >"$mo/mission.log" 2>"$mo/mission.err" || true
  fi
  python - <<PY
import json
from pathlib import Path
mo = Path("$mo")
ev = {}
p = mo / 'events.json'
if p.exists():
    ev = json.loads(p.read_text())
out = {
    'tag': '$tag',
    'lipas_first_caution_t_min': ev.get('lipas_first_caution_t_min'),
    'lipas_first_nogo_t_min': ev.get('lipas_first_nogo_t_min'),
    'nasa_goes_first_caution_t_min': ev.get('nasa_goes_first_caution_t_min'),
    'nasa_goes_first_nogo_t_min': ev.get('nasa_goes_first_nogo_t_min'),
    'nogo_lead_vs_goes_min': (
        None if ev.get('lipas_first_nogo_t_min') is None or ev.get('nasa_goes_first_nogo_t_min') is None
        else ev['nasa_goes_first_nogo_t_min'] - ev['lipas_first_nogo_t_min']
    ),
}
(mo / 'lead_proxy.json').write_text(json.dumps(out, indent=2))
print('mission', out)
PY
}

score_pair() {
  local tag="$1"
  local model_dir="$OUT/cands/$tag"
  local o="$OUT/windows_$tag"
  mkdir -p "$o/A" "$o/B_storm" "$o/C_stress"
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
  echo "=== $tag C stress ==="
  python logs/overnight_improve/train4/run_on_cpu.py scripts/run_14day_flagship_study.py \
    --csv "$WIN_CSV" --model-dir "$model_dir" \
    --start 2026-07-05 --end 2026-07-18 --window-label A --out-dir "$o/C_stress" \
    >"$o/C.log" 2>"$o/C.err" || true

  run_mission_proxy "$tag"

  python - <<PY
import json
from pathlib import Path
o = Path("$o")
wins = {}
deltas = {}
abs_h = {}
for label, sub in [("A", "A"), ("B_storm", "B_storm"), ("C_stress", "C_stress")]:
    p = o / sub / "summary.json"
    if not p.exists():
        wins[label] = {"wins": None}
        continue
    m = (json.loads(p.read_text()).get("metrics") or {})
    beat = {}; dlt = {}; ah = {}; n = t = 0
    for h, v in m.items():
        if not isinstance(v, dict) or "hybrid" not in v:
            continue
        t += 1
        hr = float(v["hybrid"]["rmse"]); fr = float(v["flagship"]["rmse"])
        b = hr < fr; beat[h] = b; dlt[h] = fr - hr; ah[h] = hr
        if b: n += 1
    wins[label] = {"wins": n, "total": t, "beat_map": beat}
    deltas[label] = dlt
    abs_h[label] = ah
lead = {}
lp = Path("$OUT/mission_$tag/lead_proxy.json")
if lp.exists():
    lead = json.loads(lp.read_text())
payload = {
    "tag": "$tag",
    "wins": wins,
    "deltas_flagship_minus_hybrid": deltas,
    "abs_hybrid_rmse": abs_h,
    "mission_lead_proxy": lead,
}
(o / "window_wins.json").write_text(json.dumps(payload, indent=2))
Path("$STUDIES/R6_INTERIM_latest.json").write_text(json.dumps(payload, indent=2))
print("$tag", json.dumps({k: wins[k].get("wins") for k in wins}), "caution", lead.get("lipas_first_caution_t_min"), "nogo", lead.get("lipas_first_nogo_t_min"))
a = wins.get("A", {}).get("wins"); b = wins.get("B_storm", {}).get("wins")
note = f"nogo={lead.get('lipas_first_nogo_t_min')};caution={lead.get('lipas_first_caution_t_min')}"
open("$LEDGER", "a").write(
    f"| {__import__('datetime').datetime.utcnow().strftime('%Y-%m-%dT%H:%MZ')} | $tag | {a} | {b} | {note} |\n"
)
# Abort residual family early if A/B regress vs R5s2 held bar
if "$tag".startswith("R6r") or "$tag".startswith("R6x_resid"):
    ah = abs_h.get("B_storm") or {}
    solar_b = ah.get("solar_activity")
    rad_b = ah.get("radiation_mSv")
    # R5s2 refs
    if solar_b is not None and solar_b > 15.2239 + 0.15:
        print("ABORT residual cand: solar B regress", solar_b)
    if rad_b is not None and rad_b > 0.0940 + 0.015:
        print("ABORT residual cand: rad B regress", rad_b)
    if a is not None and a < 6:
        print("ABORT residual cand: A wins", a)
    if b is not None and b < 6:
        print("ABORT residual cand: B wins", b)
PY
}

# Score short list only
TAGS=$(python - <<'PY'
import json
from pathlib import Path
print(' '.join(json.loads(Path('studies/drastic_wins/R6_CANDS.json').read_text())))
PY
)

for tag in $TAGS; do
  score_pair "$tag"
done

python - <<'PY'
import json
from pathlib import Path
out = Path('logs/overnight_improve/train4/cpu_levers')
studies = Path('studies/drastic_wins')
rows = []
for p in sorted(out.glob('windows_R6*/window_wins.json')):
    rows.append(json.loads(p.read_text()))

def key_metrics(r):
    abs_h = r.get('abs_hybrid_rmse') or {}
    a = abs_h.get('A') or {}
    b = abs_h.get('B_storm') or {}
    lead = r.get('mission_lead_proxy') or {}
    return {
        'tag': r.get('tag'),
        'A_wins': (r.get('wins') or {}).get('A', {}).get('wins'),
        'B_wins': (r.get('wins') or {}).get('B_storm', {}).get('wins'),
        'C_wins': (r.get('wins') or {}).get('C_stress', {}).get('wins'),
        'solar_B': b.get('solar_activity'),
        'rad_B': b.get('radiation_mSv'),
        'temp_A': a.get('temperature_C'),
        'caution': lead.get('lipas_first_caution_t_min'),
        'nogo': lead.get('lipas_first_nogo_t_min'),
        'goes_nogo': lead.get('nasa_goes_first_nogo_t_min'),
        'goes_caution': lead.get('nasa_goes_first_caution_t_min'),
    }

R5 = {'solar_B': 15.2239, 'rad_B': 0.0940, 'temp_A': 19.8488, 'nogo': 55, 'caution': 0}
scored = [key_metrics(r) for r in rows]

def rank(m):
    if m['A_wins'] is None or m['B_wins'] is None:
        return (-1,)
    a6b6 = 1 if (m['A_wins'] >= 6 and m['B_wins'] >= 6) else 0
    # Prefer fixed caution (not 0 false-alarm) while holding nogo ≤ R5
    caution_ok = 1 if (m['caution'] is not None and m['caution'] >= 40) else 0
    caution_mid = 1 if (m['caution'] is not None and 15 <= m['caution'] < 40) else 0
    nogo = m['nogo'] if m['nogo'] is not None else 999
    solar = -(m['solar_B'] or 99)
    rad = -(m['rad_B'] or 99)
    temp = -(m['temp_A'] or 99)
    return (a6b6, caution_ok, caution_mid, -(nogo), solar, rad, temp)

scored_sorted = sorted(scored, key=rank, reverse=True)
best = scored_sorted[0] if scored_sorted else None

beat_r5 = False
caution_fixed = False
if best and best['A_wins'] == 6 and best['B_wins'] == 6:
    caution_fixed = best.get('caution') is not None and best['caution'] >= 40
    beat_r5 = (
        (best.get('solar_B') is not None and best['solar_B'] < R5['solar_B'] - 0.25)
        or (best.get('rad_B') is not None and best['rad_B'] < R5['rad_B'] - 0.01)
        or (best.get('temp_A') is not None and best['temp_A'] < R5['temp_A'] - 0.25)
        or (best.get('nogo') is not None and best['nogo'] <= R5['nogo'] - 10)
        or (caution_fixed and best.get('nogo') is not None and best['nogo'] <= R5['nogo'] + 5
            and (best.get('solar_B') or 99) <= R5['solar_B'] + 0.15
            and (best.get('rad_B') or 99) <= R5['rad_B'] + 0.01)
    )

# TRUE_WALL if no clear NASA-wow climb beyond R5s2 on untried families
promote = 'READY_R6' if beat_r5 else 'TRUE_WALL'
gate = json.loads((studies / 'r6_residual_gate' / 'residual_gate.json').read_text())

summary = {
    'wave': 'R6_lastshot',
    'owner': 'bc-43fb58ef',
    'base': 'R5s2_soft_plus_ew',
    'base_tip': 'e7e31c1',
    'promote': promote,
    'beat_r5s2': beat_r5,
    'caution_fixed': caution_fixed,
    'best': best,
    'ranked': scored_sorted,
    'residual_gate': {
        'abort_metal_retrain': gate.get('abort_metal_retrain'),
        'allow_residual_correct': gate.get('allow_residual_correct'),
        'channels': {k: {kk: vv for kk, vv in v.items() if kk in (
            'ridge_skill', 'gbm_skill', 'residual_has_skill', 'circular_risk'
        )} for k, v in (gate.get('channels') or {}).items()},
    },
    'cands': rows,
    'note': 'Last-shot only: residual ridge/GBM gate, lunar_physics knobs, caution@0 FA. No paper.',
}
(out / 'drastic_R6_summary.json').write_text(json.dumps(summary, indent=2))
(studies / 'R6_FINAL.json').write_text(json.dumps(summary, indent=2))

md = [
    '# Drastic wins R6 LAST-SHOT — FINAL (Mac)',
    '',
    f"**Promote: {promote}**",
    '',
    f"Best: `{best and best.get('tag')}`",
    '',
    f"- A/B/C wins: {best and best.get('A_wins')}/{best and best.get('B_wins')}/{best and best.get('C_wins')}",
    f"- solar B / rad B / temp A: {best and best.get('solar_B')} / {best and best.get('rad_B')} / {best and best.get('temp_A')}",
    f"- LIPAS caution / NO-GO (min): {best and best.get('caution')} / {best and best.get('nogo')} (GOES caution/NO-GO {best and best.get('goes_caution')}/{best and best.get('goes_nogo')})",
    '',
    '## Residual gate',
    f"- abort_metal_retrain: **{gate.get('abort_metal_retrain')}** ({gate.get('abort_reason', '')[:80]}…)",
    f"- allow_residual_correct: `{gate.get('allow_residual_correct')}`",
    '',
    '## Wall rule',
    '- READY_R6 only if clear beat of R5s2 on solar/rad/temp/NO-GO **or** caution≥40 with windows held.',
    '- Else **TRUE_WALL** — untried last-shot families exhausted.',
    '',
    'No paper.',
]
(studies / 'R6_FINAL.md').write_text('\n'.join(md) + '\n')
# also sync studies ledger copy
led = Path('studies/drastic_wins/ledger.md')
src_led = Path('logs/overnight_improve/train4/drastic_wins_ledger.md')
if src_led.exists():
    led.write_text(src_led.read_text())
print('R6 summary', promote, best)
PY

logrow "WAVE R6 LASTSHOT DONE | - | - | - | see studies/drastic_wins/R6_FINAL.md |"
echo "R6 lastshot complete"
