# Study reproduction runners

Open [REPRODUCTION.md](../papers/appendix_numerical_tables/REPRODUCTION.md) for one section per study.

Qualitative scores and the nine criteria: [LIPAS_qualitative_comparison_framework.md](../papers/appendix_numerical_tables/LIPAS_qualitative_comparison_framework.md).

The April prototype is the daytime diagnostic at 0°N, 0°E from 5 to 19 April 2026. Daily rows are in the numerical PDF in that same folder. There is no separate runner, and those rows are not the fourteen-day result.

These scripts rebuild the locked-model study outputs used in the paper. The `saved_model` folder is not in this public repository.

Use Python 3.10+ from the repo root with dependencies from `requirements.txt`.

Model directory for paper numbers: `saved_model`

Blend weights expected: `[0.4, 0.05, 0.0, 0.0, 0.0, 0.0]`

Driver CSV used by the 14-day studies:

`data/ingested_extended/extended_training_window_B_ready.csv`

## Window A (Table 3, Figure Window A skill)

```
python scripts/run_14day_flagship_study.py --start 2026-07-05 --end 2026-07-18 --window-label A --out-dir logs/study_14day_window_A_night --model-dir saved_model --csv data/ingested_extended/extended_training_window_B_ready.csv
```

Check:

`logs/study_14day_window_A_night/summary.json`

Solar hybrid about 4.10, replica about 4.66

Radiation hybrid about 0.119, replica about 0.102

## Window B (Table 4, Figure Window B skill)

```
python scripts/run_14day_flagship_study.py --start 2026-07-22 --end 2026-08-04 --window-label B --out-dir logs/study_14day_window_B_day --model-dir saved_model --csv data/ingested_extended/extended_training_window_B_ready.csv
```

Check:

`logs/study_14day_window_B_day/summary.json`

Solar hybrid about 4.99, replica about 5.99

Radiation hybrid about 0.0188, replica about 0.00266

## Ablation (Tables 5 and 6)

```
python scripts/run_hazard_ablation_study.py --out-dir logs/study_ablation_window_A
```

Check the printed RMSE table against manuscript Tables 5 and 6. Small floating differences are fine if the ranking and relative changes stay the same.

## Mission simulation (Figure mission timeline)

```
python scripts/run_mission_sim_radiation_eva.py --out-dir logs/study_mission_sim_radiation_eva
```

Check caution and no-go times against the paper timeline (LIPAS caution near T+45, no-go near T+85).

## Holdout capability check

```
python scripts/verify_train2_capability.py
```

Expect hybrid holdout RMSE near 4.97 versus persistence near 13.66.

## Notes

Do not point `--model-dir` at `saved_model_train2_locked` for the Window A/B paper tables. That folder has different blend weights.

Micrometeorite hybrid RMSE of 0.0 is expected under blend weight 0. It is circular against the shower-augmented label.
