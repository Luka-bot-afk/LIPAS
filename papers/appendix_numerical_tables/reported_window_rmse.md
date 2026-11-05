# Reported window RMSE (manuscript window tables)

Source: locked train-2 model with serve blend solar 0.4, radiation 0.0, and adaptive gating:

`logs/overnight_improve/final_v3/window_A/summary.json`

`logs/overnight_improve/final_v3/window_B/summary.json`

`logs/overnight_improve/final_v3/window_C/summary.json`

## Window A (17 June to 14 July 2026, predominantly mixed, 84 site-days)

| Hazard | Hybrid | Replica | Outcome |
|--------|-------:|--------:|---------|
| Solar activity | 14.15 | 14.17 | Hybrid lower by about 0.2% |
| Radiation (mSv) | 1.264 | 1.259 | Replica lower |
| Temperature (C) | 39.869 | 39.869 | Tie (shared physics) |
| Moonquakes (day^-1) | 1.320 | 1.320 | Tie (shared physics) |
| Micrometeorite flux (x10^-15) | 0.0 | 0.606 | Circular under blend weight 0 |
| Dust (g cm^-3) | 0.543 | 0.543 | Tie (shared physics) |

## Window B (18 July to 14 August 2026, lunar-day dominant, 84 site-days)

| Hazard | Hybrid | Replica | Outcome |
|--------|-------:|--------:|---------|
| Solar activity | 4.928 | 5.711 | Hybrid lower by about 13.7% |
| Radiation (mSv) | 0.0259 | 0.0040 | Replica lower (dayside window) |
| Temperature (C) | 24.711 | 24.711 | Tie (shared physics) |
| Moonquakes (day^-1) | 0.776 | 0.776 | Tie (shared physics) |
| Micrometeorite flux (x10^-15) | 0.0 | 0.663 | Circular under blend weight 0 |
| Dust (g cm^-3) | 0.167 | 0.167 | Tie (shared physics) |

## Window C (4 to 17 May 2024, disturbed historical interval, 42 site-days)

| Hazard | Hybrid | Replica | Outcome |
|--------|-------:|--------:|---------|
| Solar activity | 18.623 | 18.623 | Tie (adaptive gate to physics) |
| Radiation (mSv) | 0.214 | 0.194 | Replica lower (disturbed interval) |
| Temperature (C) | 44.337 | 44.337 | Tie (shared physics) |
| Moonquakes (day^-1) | 1.287 | 1.287 | Tie (shared physics) |
| Micrometeorite flux (x10^-15) | 0.0 | 0.622 | Circular under blend weight 0 |
| Dust (g cm^-3) | 0.549 | 0.549 | Tie (shared physics) |

## Holdout (train-2 chronological)

Hybrid RMSE about 4.97 versus persistence about 13.66.
