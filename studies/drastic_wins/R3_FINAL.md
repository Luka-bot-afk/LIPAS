# Drastic wins R3 — FINAL (Mac)

**Promote: NOT_READY** — temp still epsilon; ASR would not care yet.

## Best package: `R3b_solar120_m2rad`

| | A | B | solar A | solar B | rad A | rad B | temp A |
|---|---:|---:|---:|---:|---:|---:|---:|
| L20 | 6 | 5 | 14.1465 | 18.6233 | 1.2550 | 0.1901 | 22.2094 |
| R2m2 | 6 | 6 | 13.9630 | 16.5488 | 1.2218 | 0.0949 | 22.2020 |
| **R3b_solar120_m2rad** | **6** | **6** | **13.9386** | **15.8290** | **1.2132** | **0.0969** | **22.2034** |

Δ vs L20 (R3b): solar B +2.7943; rad B +0.0932; temp A +0.0061 (epsilon).

## Other A6/B6
R3b_solar120_m2rad, R3d_m2_soft_clim, R3f_temp_band_clip, R3g_rad_climb_cmax

## Temp family
- `R3t_night_temp_025`: **KILL** — temp A/B worse; lost B mq
- `R3f_temp_band_clip`: A6/B6 but temp slightly worse than L20; no gain

## Kill / keep
- KILL soft/hard persist (mq B or quiet solar), mq terminator soft, night temp +0.25, add_hard
- KEEP `R3b` (new solar best) + `R2m2` baseline; clim/rad A6B6 secondary

## Checks
- storm solar tie broken: yes
- beats R2m2 solar B: yes (15.83 vs 16.55)
- temp ops-useful: **no** (still ~0.006°C RMSE vs L20)
- ASR-interesting: **no** → NOT_READY

No paper. Temp remains open gap for R4.
