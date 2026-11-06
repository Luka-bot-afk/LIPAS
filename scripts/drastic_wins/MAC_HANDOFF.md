# Drastic wins — Mac handoff (`bc-d6c08fcb`)

**Branch:** `cursor/drastic-wins-regime-ff97`  
**Cloud owner:** `bc-a48cf0e9` (implements hooks / cloud probes)  
**Mac owner:** you — Metal/CPU window sweeps  
**Hard rules:** no paper edits; no mission/ablation studies package yet. Window A + storm B RMSE probes only. Keep rad ML share > 0. LSTM stays train-2 locked weights.

## Sync note (cloud `bc-a48cf0e9`)

Pulled `origin/cursor/drastic-wins-regime-ff97` — was go-night tip `fc4dde6` (no Mac lever commit yet). Cloud is pushing hooks + R1 solar-first cands on this branch. **Mac: `git pull --ff-only` then run wave R1.** Prefer starting with `R1s_*` solar climatology cands (your first lever).

## What landed in code

`space_weather_model.apply_archive_priors_to_hybrid` now supports hybrid-only:

- **`solar_storm_climatology`** — pull hybrid solar toward storm-day target with per-level blend (flare_rise/storm/sep_like); optional DOY amp
- `regime_rules.enabled` + per-level (`quiet` / `unsettled` / `flare_rise` / `storm` / `sep_like`) channel `{scale, add}` for solar/radiation/temperature/moonquakes/(dust/micrometeorites)
- radiation `couple_from_solar` (uses hybrid solar − physics solar)
- `moonquake_prior` (scale/add + terminator bump + tidal sinusoid)
- `seasonal_temp.day_add_C` / `night_add_C`
- `physics_band_clip` (pull hybrid toward physics±band)

L20 baseline priors still work. Regime rules are **additive** JSON — Mac can sweep without further code if hooks are pulled.

## How to sweep

```bash
cd /Users/lukatakki/Documents/GitHub/LIPAS   # or your LIPAS checkout
git fetch origin cursor/drastic-wins-regime-ff97
git checkout cursor/drastic-wins-regime-ff97
git pull --ff-only origin cursor/drastic-wins-regime-ff97
source .venv/bin/activate
export ALLOW_TRAIN4=1 TF_CPP_MIN_LOG_LEVEL=2 PYTHONUNBUFFERED=1
bash scripts/drastic_wins/run_wave_R1.sh
```

Script builds `R1_*` cands under `logs/overnight_improve/train4/cpu_levers/cands/`, scores Window A + B_storm, appends `logs/overnight_improve/train4/drastic_wins_ledger.md`, writes `cpu_levers/drastic_R1_summary.json`.

## Priority chase order

1. Break **storm B solar tie** (hybrid-only solar storm/flare_rise scale/add)
2. Grow **radiation** A+B margins (GCR v2 + storm couple) without quiet false-alarm blowups
3. **Temp** via day/night add or diviner_pull — never raise ML
4. **Moonquakes** via tidal/terminator prior — never raise ML
5. Selective `w_solar` / `w_rad` only after rules move the needle

## Coordination

- Push cand results + ledger rows to this branch often
- If you invent a new prior key the code lacks, note it in ledger and ping via git commit message `NEED HOOK: ...` — cloud will implement
- Do not promote / paper until cloud+Mac agree margins are drastic vs L20

## Mac fix (2026-11-06)

`run_wave_R1.sh` ROOT was `../../..` (landed outside LIPAS). Fixed to `../..`. First Mac attempt null-scored; re-run after fix.
