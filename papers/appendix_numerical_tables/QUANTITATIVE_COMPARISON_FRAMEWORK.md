# Quantitative comparison framework (Appendix C)

This note explains how the locked Window A and Window B numbers were produced.

## What is compared

For each hazard and each site-day:

- **Hybrid** = locked LIPAS train-2 hybrid prediction (`saved_model`)
- **Replica / Flagship** = independent public-method reconstruction used as the study baseline
- **Truth / label** = study evaluation target (measurement, physics path, catalog proxy, or engineering export)

Blend weights used for the reported studies:

`[0.4, 0.05, 0.0, 0.0, 0.0, 0.0]`

Order: solar, radiation, temperature, moonquakes, micrometeorites, dust.

Temperature, moonquakes, micrometeorites, and dust therefore stay on the physics path inside the hybrid. That is why those channels can tie the replica when the replica shares the same physics path.

## Main metric

Root-mean-square error (RMSE) of hybrid and replica against the study labels, aggregated over 42 site-days per window (3 sites × 14 days).

Skill charts use:

`skill = 96 * max(0, 1 - RMSE / scale)`

`scale` is the maximum of hybrid and replica RMSE across the three sites for that hazard only. Skill is not height-normalized across hazards.

A skill of 96 means zero RMSE on that site for that hazard. It is not percent accuracy.

## Windows

| Window | Dates | Regime |
|--------|-------|--------|
| A | 5 Jul 2026 to 18 Jul 2026 | lunar-night dominant |
| B | 22 Jul 2026 to 4 Aug 2026 | lunar-day dominant, quiet radiation |

## How to read the radiation result

Window A hybrid radiation RMSE is 0.119 versus replica 0.102.

Window B hybrid radiation RMSE is 0.0188 versus replica 0.00266.

Window B absolute doses are much smaller. The same small radiation blend weight (0.05) then creates a larger relative gap when there is little storm signal.

## How to read micrometeorites

Hybrid micrometeorite RMSE is 0.0 in both windows because blend weight 0 makes hybrid follow the shower-augmented label used for scoring. That is circular. Report it as a shower-timing illustration, not as an independent forecast win.

## Output files after a successful rerun

`logs/study_14day_window_A_night/summary.json`

`logs/study_14day_window_A_night/daily_predictions.csv`

`logs/study_14day_window_B_day/summary.json`

`logs/study_14day_window_B_day/daily_predictions.csv`

Aggregate RMSE in `summary.json` must match `reported_window_rmse.md`.

## Prototype study note (not locked)

The April client-V1 prototype used a different model path and thinner replicas. Mean skill across the six hazards was about 73.3 (LIPAS) versus 69.5 (flagship-replica aggregate). That two-bar summary is only historical context. Do not overwrite locked Window A/B tables with prototype outputs. The early Diviner-class temperature plot shows the client overshooting peak daytime temperature, which is why locked temperature stays on the physics path (blend weight 0).
