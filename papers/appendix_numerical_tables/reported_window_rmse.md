# Reported window RMSE (manuscript Tables 3 and 4)

Source: locked `saved_model` reruns in

`logs/study_14day_window_A_night/summary.json`

`logs/study_14day_window_B_day/summary.json`

## Window A (5 to 18 July 2026, lunar-night dominant, 42 site-days)

| Hazard | Hybrid | Replica | Outcome |
|--------|-------:|--------:|---------|
| Solar activity | 4.10 | 4.66 | Hybrid lower by about 12% |
| Radiation (mSv) | 0.119 | 0.102 | Replica lower |
| Temperature (C) | 38.2 | 38.2 | Tie (shared physics) |
| Moonquakes (day^-1) | 1.23 | 1.23 | Tie (shared physics) |
| Micrometeorite flux (x10^-15) | 0.0 | 0.624 | Circular under blend weight 0 |
| Dust (g cm^-3) | 0.526 | 0.526 | Tie (shared physics) |

## Window B (22 July to 4 August 2026, lunar-day dominant, 42 site-days)

| Hazard | Hybrid | Replica | Outcome |
|--------|-------:|--------:|---------|
| Solar activity | 4.99 | 5.99 | Hybrid lower by about 17% |
| Radiation (mSv) | 0.0188 | 0.00266 | Replica lower (quiet dayside) |
| Temperature (C) | 25.5 | 25.5 | Tie (shared physics) |
| Moonquakes (day^-1) | 0.695 | 0.695 | Tie (shared physics) |
| Micrometeorite flux (x10^-15) | 0.0 | 0.701 | Circular under blend weight 0 |
| Dust (g cm^-3) | 0.169 | 0.169 | Tie (shared physics) |

## Holdout (train-2 chronological)

Hybrid RMSE about 4.97 versus persistence about 13.66.
