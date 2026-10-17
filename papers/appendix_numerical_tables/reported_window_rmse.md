# Reported window RMSE (manuscript Tables 3–4)

Values from locked `saved_model` reruns in `logs/study_14day_window_A_night/summary.json` and `logs/study_14day_window_B_day/summary.json`.

## Window A (5–18 July 2026; lunar-night dominant; 42 site-days)

| Hazard | Hybrid | Replica | Outcome |
|--------|-------:|--------:|---------|
| Solar activity | 4.10 | 4.66 | Hybrid lower by ~12% |
| Radiation (mSv) | 0.119 | 0.102 | Replica lower (hybrid higher error) |
| Temperature (°C) | 38.2 | 38.2 | Tie (shared physics) |
| Moonquakes (day⁻¹) | 1.23 | 1.23 | Tie (shared physics) |
| Micrometeorite flux (×10⁻¹⁵) | 0.0 | 0.624 | Descriptive / circular (blend weight 0) |
| Dust (g cm⁻³) | 0.526 | 0.526 | Tie (shared physics) |

## Window B (22 July–4 August 2026; lunar-day dominant; 42 site-days)

| Hazard | Hybrid | Replica | Outcome |
|--------|-------:|--------:|---------|
| Solar activity | 4.99 | 5.99 | Hybrid lower by ~17% |
| Radiation (mSv) | 0.0188 | 0.00266 | Hybrid higher error (quiet-dayside limit) |
| Temperature (°C) | 25.5 | 25.5 | Tie (shared physics) |
| Moonquakes (day⁻¹) | 0.695 | 0.695 | Tie (shared physics) |
| Micrometeorite flux (×10⁻¹⁵) | 0.0 | 0.701 | Descriptive / circular (blend weight 0) |
| Dust (g cm⁻³) | 0.169 | 0.169 | Tie (shared physics) |

## Notes

- Skill charts use `skill = 96 × max(0, 1 − RMSE / scale)` with per-hazard site scale.
- Temperature, moonquakes, and dust ties are intentional (blend weight 0; shared physics path).
- Micrometeorite hybrid RMSE of 0 reflects physics-led scoring against the shower-augmented label, not independent impact validation.
- Chronological holdout (train2): hybrid RMSE ≈ 4.97 vs persistence ≈ 13.66.
