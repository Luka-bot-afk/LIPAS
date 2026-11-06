#!/usr/bin/env bash
# Wave R5: NEW families only on R4l2 READY base — climb until wall.
# Owner: bc-4bbf4026 on Mac 2414b5dd. Sibling bc-9b4346a4 STAND DOWN if conflict (one R5 tmux).
# Scores: Window A + storm B + stress C + cheap mission caution/NO-GO lead proxy.
# Full mission/ablation studies package later — design keeps solar↔rad coupling alive.
# No paper.
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
mkdir -p "$OUT/cands" "$STUDIES"
[[ -f "$LEDGER" ]] || printf '| utc | tag | A_wins | B_wins | notes |\n|---|---|---:|---:|---|\n' >"$LEDGER"
logrow() { printf '| %s | %s\n' "$(date -u +%Y-%m-%dT%H:%MZ)" "$1" >> "$LEDGER"; }
logrow "WAVE R5 START | - | - | - | R4l2 base; NEW families; mission lead proxy; wall climb; owner bc-4bbf4026 |"

# Kill stale sibling R5 tmux if present (single-owner lock)
if command -v tmux >/dev/null 2>&1; then
  if tmux has-session -t "lipas-r5-sweep" 2>/dev/null; then
    echo "NOTE: reusing tmux session lipas-r5-sweep (one R5 only)"
  else
    tmux new-session -d -s "lipas-r5-sweep" -c "$ROOT" -- "${SHELL:-zsh}" -l || true
  fi
fi

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
    (d / 'blend.json').write_text(json.dumps({'blend': blend, 'priors': priors, 'wave': 'R5'}, indent=2))

def r4l2_base():
    """READY package R4l2_lst_bins_40 — do not regress solar/rad/temp gains."""
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
                # keep couple for ablation story (solar removal should still hurt rad)
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
    }

cands = {}

# Baseline echo (control)
cands['R5_base_r4l2'] = (base_blend, r4l2_base())

# --- Quiet solar (A) without touching storm ---
p = r4l2_base()
p['quiet_solar_prior'] = {'enabled': True, 'scale': 0.97, 'add': -0.15}
cands['R5q_quiet_solar_shrink'] = (base_blend, p)

p = r4l2_base()
p['quiet_solar_prior'] = {'enabled': True, 'scale': 1.03, 'add': 0.20}
cands['R5q2_quiet_solar_lift'] = (base_blend, p)

# --- Early-warning rad (mission NO-GO / caution lead) ---
p = r4l2_base()
p['early_warning_rad'] = {
    'enabled': True, 'levels': ['flare_rise', 'storm', 'sep_like', 'unsettled'],
    'score_gain': 0.025, 'score0': 0.8, 'add_floor': 0.005, 'add_cap': 0.06,
    'input_solar_gain': 0.004, 'input_solar0': 10.0, 'input_solar_cap': 0.04,
}
cands['R5e_early_warn_rad'] = (base_blend, p)

p = r4l2_base()
p['early_warning_rad'] = {
    'enabled': True, 'levels': ['flare_rise', 'storm', 'sep_like'],
    'score_gain': 0.04, 'score0': 0.8, 'add_floor': 0.01, 'add_cap': 0.09,
    'input_solar_gain': 0.006, 'input_solar0': 8.0, 'input_solar_cap': 0.05,
}
cands['R5e2_early_warn_hard'] = (base_blend, p)

# Soft continuous regime mix (precursor → earlier solar/rad)
p = r4l2_base()
p['soft_regime_mix'] = {
    'enabled': True, 'score_lo': 0.6, 'score_hi': 2.4,
    'solar_add_at_hi': 1.2, 'rad_add_at_hi': 0.05,
}
cands['R5s_soft_regime'] = (base_blend, p)

p = r4l2_base()
p['soft_regime_mix'] = {
    'enabled': True, 'score_lo': 0.5, 'score_hi': 2.0,
    'solar_add_at_hi': 2.0, 'rad_add_at_hi': 0.07,
}
p['early_warning_rad'] = {
    'enabled': True, 'levels': ['flare_rise', 'storm', 'sep_like', 'unsettled'],
    'score_gain': 0.02, 'add_cap': 0.05, 'input_solar_gain': 0.003, 'input_solar_cap': 0.03,
}
cands['R5s2_soft_plus_ew'] = (base_blend, p)

# --- Physics-formula hybrid scales (proxy lunar_physics knobs) ---
p = r4l2_base()
p['physics_formula_scale'] = {
    'enabled': True,
    'solar': {'scale': 1.0, 'add': 0.0},
    'radiation': {'scale': 1.05, 'add': 0.0},
}
cands['R5p_rad_formula_105'] = (base_blend, p)

p = r4l2_base()
p['physics_formula_scale'] = {
    'enabled': True,
    'solar': {'scale': 0.98, 'add': 0.0},  # quiet-ish shrink; storm rules still apply after? order: pform last
}
# Actually pform runs last — would shrink storm too. Gate via quiet_solar instead.
# Use storm-safe: only bump rad formula.
p['physics_formula_scale'] = {'enabled': True, 'radiation': {'scale': 1.08, 'add': 0.004}}
cands['R5p2_rad_formula_108'] = (base_blend, p)

# --- Ablation-minded: stronger solar→rad couple (keep coupling story) ---
p = r4l2_base()
p['regime_rules']['flare_rise']['radiation']['couple_from_solar'] = 0.03
p['regime_rules']['storm']['radiation']['couple_from_solar'] = 0.05
p['regime_rules']['sep_like']['radiation']['couple_from_solar'] = 0.06
p['regime_rules']['storm']['radiation']['couple_max_add'] = 0.08
cands['R5a_couple_strong'] = (base_blend, p)

p = r4l2_base()
p['regime_rules']['flare_rise']['radiation']['couple_from_solar'] = 0.02
p['regime_rules']['storm']['radiation']['couple_from_solar'] = 0.045
p['early_warning_rad'] = {
    'enabled': True, 'levels': ['flare_rise', 'storm', 'sep_like'],
    'score_gain': 0.03, 'add_cap': 0.07, 'input_solar_gain': 0.005, 'input_solar_cap': 0.04,
}
cands['R5a2_couple_ew'] = (base_blend, p)

# --- Moonquake lat prior (no tidal) ---
p = r4l2_base()
p['mq_lat_prior'] = {'enabled': True, 'equator_add': 0.6, 'polar_sub': 0.25}
cands['R5m_mq_lat'] = (base_blend, p)

# --- Temp refine on R4l2 (LST scale nudge only — new, not R4 grind of DN) ---
p = r4l2_base()
p['seasonal_temp']['lst_bins']['scale'] = 0.48
cands['R5t_lst_48'] = (base_blend, p)

p = r4l2_base()
p['seasonal_temp']['lst_bins']['scale'] = 0.35
p['seasonal_temp']['diviner_pull'] = 0.03
cands['R5t2_lst35_div03'] = (base_blend, p)

# --- Selective ML share (ablation-safe: keep rad>0; storm still gated in code) ---
cands['R5w_solar45'] = ([0.45, 0.15, 0.02, 0.02, 0.03, 0.01], r4l2_base())
cands['R5w2_rad18'] = ([0.40, 0.18, 0.02, 0.02, 0.03, 0.01], r4l2_base())
cands['R5w3_solar45_rad18'] = ([0.45, 0.18, 0.02, 0.02, 0.03, 0.01], r4l2_base())

# --- Combo wall-shot: EW + soft + couple (mission + windows) ---
p = r4l2_base()
p['early_warning_rad'] = {
    'enabled': True, 'levels': ['flare_rise', 'storm', 'sep_like', 'unsettled'],
    'score_gain': 0.03, 'add_cap': 0.07, 'input_solar_gain': 0.004, 'input_solar_cap': 0.04,
}
p['soft_regime_mix'] = {'enabled': True, 'solar_add_at_hi': 1.0, 'rad_add_at_hi': 0.03}
p['regime_rules']['storm']['radiation']['couple_from_solar'] = 0.04
p['quiet_solar_prior'] = {'enabled': True, 'scale': 0.985, 'add': -0.05}
p['mq_lat_prior'] = {'enabled': True, 'equator_add': 0.4, 'polar_sub': 0.15}
cands['R5x_combo_mission'] = (base_blend, p)

for name, (blend, priors) in cands.items():
    pack(name, blend, priors)
print('built', sorted(cands))
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
  # Stress quiet-ish alternate summer slice (ablation-adjacent window)
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
Path("$STUDIES/R5_INTERIM_latest.json").write_text(json.dumps(payload, indent=2))
print("$tag", json.dumps({k: wins[k].get("wins") for k in wins}, ), "nogo", lead.get("lipas_first_nogo_t_min"))
a = wins.get("A", {}).get("wins"); b = wins.get("B_storm", {}).get("wins")
note = f"nogo={lead.get('lipas_first_nogo_t_min')};caution={lead.get('lipas_first_caution_t_min')}"
open("$LEDGER", "a").write(
    f"| {__import__('datetime').datetime.utcnow().strftime('%Y-%m-%dT%H:%MZ')} | $tag | {a} | {b} | {note} |\n"
)
PY
}

for tag in \
  R5_base_r4l2 \
  R5q_quiet_solar_shrink \
  R5q2_quiet_solar_lift \
  R5e_early_warn_rad \
  R5e2_early_warn_hard \
  R5s_soft_regime \
  R5s2_soft_plus_ew \
  R5p_rad_formula_105 \
  R5p2_rad_formula_108 \
  R5a_couple_strong \
  R5a2_couple_ew \
  R5m_mq_lat \
  R5t_lst_48 \
  R5t2_lst35_div03 \
  R5w_solar45 \
  R5w2_rad18 \
  R5w3_solar45_rad18 \
  R5x_combo_mission
do
  score_pair "$tag"
done

python - <<'PY'
import json
from pathlib import Path
out = Path('logs/overnight_improve/train4/cpu_levers')
studies = Path('studies/drastic_wins')
rows = []
for p in sorted(out.glob('windows_R5*/window_wins.json')):
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
    }

# R4l2 reference targets (from R4_FINAL)
R4 = {'solar_B': 15.8290, 'rad_B': 0.0969, 'temp_A': 19.8333, 'A': 6, 'B': 6}
scored = [key_metrics(r) for r in rows]
# Prefer A6/B6, then better nogo lead (lower t), then better temp/solar/rad
def rank(m):
    if m['A_wins'] is None or m['B_wins'] is None:
        return (-1, 0, 0, 0)
    a6b6 = 1 if (m['A_wins'] >= 6 and m['B_wins'] >= 6) else 0
    nogo = m['nogo'] if m['nogo'] is not None else 999
    goes = m['goes_nogo'] if m['goes_nogo'] is not None else 999
    lead = max(0, goes - nogo) if nogo is not None else 0
    temp = -(m['temp_A'] or 99)
    solar = -(m['solar_B'] or 99)
    rad = -(m['rad_B'] or 99)
    return (a6b6, lead, temp, solar, rad)

scored_sorted = sorted(scored, key=rank, reverse=True)
best = scored_sorted[0] if scored_sorted else None
beat_r4 = False
if best and best['A_wins'] == 6 and best['B_wins'] == 6:
    beat_r4 = (
        (best.get('temp_A') is not None and best['temp_A'] < R4['temp_A'] - 0.15)
        or (best.get('solar_B') is not None and best['solar_B'] < R4['solar_B'] - 0.25)
        or (best.get('rad_B') is not None and best['rad_B'] < R4['rad_B'] - 0.01)
        or (best.get('nogo') is not None and best.get('goes_nogo') is not None
            and (best['goes_nogo'] - best['nogo']) >= 25)
    )

# Wall call: if no cand clearly beats R4l2 on windows OR mission lead → EXHAUSTED
promote = 'READY_R5' if beat_r4 else 'EXHAUSTED_AT_R4l2'
summary = {
    'wave': 'R5',
    'owner': 'bc-4bbf4026',
    'base': 'R4l2_lst_bins_40',
    'promote': promote,
    'beat_r4l2': beat_r4,
    'best': best,
    'ranked': scored_sorted,
    'cands': rows,
    'note': 'Full ablation/mission paper studies later; R5 includes lead proxy + stress C + couple-preserving cands.',
}
(out / 'drastic_R5_summary.json').write_text(json.dumps(summary, indent=2))
(studies / 'R5_FINAL.json').write_text(json.dumps(summary, indent=2))
md = [
    '# Drastic wins R5 — FINAL (Mac)',
    '',
    f"**Promote: {promote}**",
    '',
    f"Best: `{best and best.get('tag')}`",
    '',
    f"- A/B/C wins: {best and best.get('A_wins')}/{best and best.get('B_wins')}/{best and best.get('C_wins')}",
    f"- solar B / rad B / temp A: {best and best.get('solar_B')} / {best and best.get('rad_B')} / {best and best.get('temp_A')}",
    f"- LIPAS caution / NO-GO (min): {best and best.get('caution')} / {best and best.get('nogo')} (GOES NO-GO {best and best.get('goes_nogo')})",
    '',
    '## Wall rule',
    '- READY_R5 only if clear beat of R4l2 on temp/solar/rad **or** ≥25 min NO-GO lead vs GOES with A6/B6 held.',
    '- Else **EXHAUSTED_AT_R4l2** — real wall on new-family R5.',
    '',
    'No paper until user greenlights.',
]
(studies / 'R5_FINAL.md').write_text('\n'.join(md) + '\n')
print('R5 summary', promote, best)
PY

logrow "WAVE R5 DONE | - | - | - | see studies/drastic_wins/R5_FINAL.md |"
echo "R5 complete"
