# Reported window RMSE (draft 27)

Locked blend `[0.4, 0.0, 0, 0, 0, 0]` with storm-aware adaptive gating. Train-2 weights unchanged.

## Summer Window S — 17 Jun – 4 Aug 2026 (138 site-days)

Combined former Windows A (17 Jun–14 Jul) and B (18 Jul–4 Aug). Excludes 15–17 Jul gap. Source: `logs/overnight_improve/final_v3/window_AB/summary.json`.

| Hazard | Hybrid | Replica | Outcome |
|---|---:|---:|---|
| Solar activity | 11.46 | 11.62 | Hybrid lower ≈1.4% |
| Radiation (mSv) | 0.987 | 0.982 | Replica lower |
| Temperature (°C) | 34.73 | 34.73 | Tie (physics) |
| Moonquakes / day | 1.139 | 1.139 | Tie (physics) |
| Micrometeorites | 0.0 | 0.629 | Not independent (shower term) |
| Dust (g cm⁻³) | 0.436 | 0.436 | Tie (physics) |

## Storm Window C — 1–28 May 2024 (84 site-days)

One-month disturbed historical interval. Source: `logs/overnight_improve/final_v3/window_C28/summary.json`.

| Hazard | Hybrid | Replica | Outcome |
|---|---:|---:|---|
| Solar activity | 14.65 | 14.65 | Tie (adaptive gate → physics) |
| Radiation (mSv) | 0.199 | 0.182 | Replica lower |
| Temperature (°C) | 40.72 | 40.72 | Tie (physics) |
| Moonquakes / day | 1.309 | 1.309 | Tie (physics) |
| Micrometeorites | 0.0 | 0.604 | Not independent (shower term) |
| Dust (g cm⁻³) | 0.546 | 0.546 | Tie (physics) |
