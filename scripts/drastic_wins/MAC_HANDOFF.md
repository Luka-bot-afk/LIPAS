# Drastic wins — Mac handoff

**Branch:** `cursor/drastic-wins-regime-ff97`  
**R5 owner (ONLY):** `bc-4bbf4026-216b-5188-a1db-7401a698f86f` on worker `2414b5dd`  
**Stand down:** `bc-9b4346a4` — do **not** run a second R5 tmux if `bc-4bbf4026` is sweeping. One R5 session only (`lipas-r5-sweep`).  
**Cloud:** `bc-a48cf0e9` — hooks/scripts; no invent; no paper.

## Current lock

- READY baseline to beat: **`R4l2_lst_bins_40`** (A6/B6; solar B 15.83; rad B 0.097; temp A 19.83)
- User lock: climb R5 **new families** until clear beat **or** honest **EXHAUSTED_AT_R4l2**
- Full mission/ablation studies package = later (user). R5 still scores **cheap mission lead proxy** + stress window C + keeps solar↔rad couple (ablation-aware).

## R5 hooks (hybrid-only)

In `apply_archive_priors_to_hybrid`:
- `quiet_solar_prior` — quiet level only
- `early_warning_rad` — score/input-solar rad add for earlier caution/NO-GO
- `soft_regime_mix` — continuous score→solar/rad add
- `mq_lat_prior` — lat band (no tidal; R1f tidal was KILL)
- `physics_formula_scale` — hybrid proxy for physics knobs
- Plus R4l2 base (regime solar/rad couple + LST bins 0.40)

## Run (owner only)

```bash
cd /Users/lukatakki/Documents/GitHub/LIPAS
git fetch origin cursor/drastic-wins-regime-ff97
git checkout cursor/drastic-wins-regime-ff97
git pull --ff-only origin cursor/drastic-wins-regime-ff97
source .venv/bin/activate
export ALLOW_TRAIN4=1 TF_CPP_MIN_LOG_LEVEL=2 PYTHONUNBUFFERED=1
# If sibling session exists, kill it first — one R5 only:
# tmux kill-session -t lipas-r5-sweep 2>/dev/null || true
bash scripts/drastic_wins/run_wave_R5.sh
```

Push interim `studies/drastic_wins/R5_INTERIM_latest.json` / ledger often; end with `R5_FINAL.md` + `R5_FINAL.json`.

## Wall / promote

- **READY_R5** only if beat R4l2 on temp/solar/rad **or** ≥25 min NO-GO lead vs GOES with A6/B6 held
- Else **EXHAUSTED_AT_R4l2**
- **No paper** until user greenlights
