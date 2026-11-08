# Reported Window RMSE — R6c_caution_cap090 (Draft 30 reshape)

Package: `R6c_caution_cap090` on train-2 LSTM. Blend `[0.40, 0.15, 0.02, 0.02, 0.03, 0.01]`.

## Window A — 2026-06-01 → 2026-08-04 (65d, 195 site-days) — **6/6**

| Hazard | LIPAS | NASA replica | Improvement % |
|---|---:|---:|---:|
| solar_activity | 9.532 | 9.889 | 3.60 |
| radiation_mSv | 0.798 | 0.829 | 3.69 |
| temperature_C | 25.90 | 27.35 | 5.32 |
| moonquakes_per_day | 1.166 | 1.167 | 0.08 |
| meteor_flux_1e15 | 0.015 | 0.643 | 97.7 (circular / shower-term) |
| dust_g_cm3 | 0.445 | 0.445 | 0.02 (near-circular) |

Source: `studies/draft30_r6/READY_FOR_DRAFT30_R6.json` / `tables/window_A_rmse.md`

## Window B storm — 2024-04-20 → 2024-05-20 (31d, 93 site-days) — **6/6**

| Hazard | LIPAS | NASA replica | Improvement % |
|---|---:|---:|---:|
| solar_activity | 11.22 | 13.79 | 18.6 |
| radiation_mSv | 0.071 | 0.172 | 58.7 |
| temperature_C | 38.56 | 40.35 | 4.44 |
| moonquakes_per_day | 1.263 | 1.269 | 0.47 |
| meteor_flux_1e15 | 0.012 | 0.564 | 97.9 (circular / shower-term) |
| dust_g_cm3 | 0.147 | 0.163 | 9.90 (near-circular) |

Source: `studies/draft30_r6/tables/window_B_storm_rmse.md`

## Mission (measured)

| System | First caution | First NO-GO |
|---|---|---|
| LIPAS | T+50 | T+55 |
| NASA GOES | T+80 | T+105 |
| NASA combined | T+55 | T+70 |

LIPAS NO-GO leads GOES NO-GO by **50 min**.

## Ablation (2026-06-17 → 2026-06-30, 42 site-days)

Baseline solar RMSE **11.563** / radiation **1.702**. Worst one-away (both): remove solar → solar +10.7%, rad +0.23%.
