# Drastic wins — Mac handoff

**Branch tip (R6):** `cursor/lastshot-r6-wall-1d4f`  
**R6 owner (ONLY):** `bc-43fb58ef-bd5f-56f6-a18c-264e182b1d4f`  
**Stood down:** `bc-4bbf4026` (R5 complete), `bc-9b4346a4`  
**Cloud:** `bc-a48cf0e9` — hooks optional; Mac authored last-shot when cloud absent. No paper.

## Locks

- **READY_R5:** `R5s2_soft_plus_ew` @ `e7e31c1` — solar B 15.22; nogo 55; caution@0 false-alarm caveat
- **READY_R6:** `R6c_caution_cap090` — same windows + **caution 50** / nogo 55; C5; solar/rad/temp held
- Residual Metal: **ABORT** (T4b). Residual serve bias: **KILL** (B5). lunar knobs: no RMSE climb.

## Run (historical)

```bash
bash scripts/drastic_wins/run_wave_R6_lastshot.sh   # one tmux: lipas-r6-lastshot
```

## Artifacts

- `studies/drastic_wins/R6_FINAL.md` / `R6_FINAL.json`
- `studies/drastic_wins/r6_residual_gate/residual_gate.json`
