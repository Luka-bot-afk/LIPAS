# Drastic wins R2 — FINAL (Mac)

**Promote: NOT_READY** — user lock: R2m2-class margins still climb territory; ASR wouldn't care yet.

## Abs hybrid RMSE (lower better)

| tag | A/B wins | solar A | solar B | rad A | rad B | notes |
|---|---:|---:|---:|---:|---:|---|
| L20 | 6/5 | 14.1465 | 18.6233 | 1.2550 | 0.1901 | baseline |
| R1c | 6/6 | 14.0185 | 17.3524 | 1.2316 | 0.1153 | R1 best |
| **R2m2_solar115_rad** | **6/6** | **13.9630** | **16.5488** | **1.2218** | **0.0949** | R2 best balanced |
| R2m4_solar118 | 6/5 | 13.9488 | 16.1823 | 1.2174 | 0.0930 | solar climb; mq B loss |
| R2m5_solar_add_hard | 6/5 | 13.8613 | 16.1902 | 1.2032 | 0.0977 | A solar best; mq B loss |
| R2p_persist_merge | 5/5 | 14.3433 | **12.6485** | 1.2029 | 0.2819 | solar B drastic but A/rad die |
| R2p2_persist_storm_only | 5/4 | 14.7963 | **12.1098** | 1.1978 | 0.4868 | worse rad blowup |

## Kill / keep
- KEEP `R2m2` as climb base (A6/B6)
- KILL hard pre-regime persist (`R2p*`) — couple_from_solar sees persist uplift → rad B explosion
- KILL `R2s_sep_heavy` (rad B loss), `R2t` temp mild, unsettled soft (no gain)
- R2m4/m5: solar better but lose mq B — retry with soft mq in R3

## R3 inventions
1. Move `solar_persist_pull` **after** regime rules (so rad couple ignores persist uplift)
2. `couple_max_add` on radiation regime
3. `min_sa_gap` on persist; soft alphas
4. Soft clim-on-m2, night-only temp, temp band clip, solar 1.20 + soft mq

No paper. Climbing.
