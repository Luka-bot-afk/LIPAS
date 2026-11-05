# Reproduce each study

Open this file from the paper appendix. Each study is separate. Run commands from the repository root after:

```
git clone https://github.com/Luka-bot-afk/LIPAS.git
cd LIPAS
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Paper tables use blend weights solar 0.4, radiation 0.0, and 0 for temperature, moonquakes, micrometeorites, and dust, with the same storm-aware adaptive gating as Section 3.2 (zero solar/radiation ML under storm-like regimes or when live radiation input is at or above 0.20 mSv). The locked train-2 weights ship in `papers/appendix_numerical_tables/locked_saved_model/`. Before running the study scripts, either copy that folder to `saved_model` at the repository root or pass `--model-dir papers/appendix_numerical_tables/locked_saved_model`. Leave the blend weights unchanged.

## 1. Qualitative comparison (Table 2)

Go to [LIPAS_qualitative_comparison_framework.md](LIPAS_qualitative_comparison_framework.md).

Score DONKI, Diviner, LDEX, Apollo PSE, MEM 3, GOES-18, and LIPAS on the nine criteria. Do not turn the labels into numbers and do not add them up. Compare your scores with Table 2.

## 2. Prototype (April diagnostic, Figures 4 and 5)

This is the daytime run at 0°N, 0°E from 5 to 19 April 2026. It is not the locked window evaluation.

Go to [LIPAS_appendix_numerical_tables_A_B_D_E.pdf](LIPAS_appendix_numerical_tables_A_B_D_E.pdf). If the preview is blank, use Download. April rows start on the second page. There is no separate script for this checkpoint. Do not paste these rows into the Window A, B, or C tables.

## 3. Window A (Table 3, Figure 6)

Predominantly mixed, 17 June to 14 July 2026, 84 site-days, at 0°N 0°E, Apollo 11, and Nobile Rim.

Go to [run_14day_flagship_study.py](../../scripts/run_14day_flagship_study.py).

```
python scripts/run_14day_flagship_study.py --start 2026-06-17 --end 2026-07-14 --window-label A --out-dir logs/overnight_improve/final_v3/window_A --model-dir papers/appendix_numerical_tables/locked_saved_model --csv data/ingested_extended/extended_training_window_B_ready.csv
```

Open `logs/overnight_improve/final_v3/window_A/summary.json`. Solar RMSE should be about 14.15 versus 14.17. Radiation should be about 1.26 versus 1.26. The checked numbers are in [reported_window_rmse.md](reported_window_rmse.md).

## 4. Window B (Table 4, Figure 8)

Dayside-dominant, 18 July to 14 August 2026, 84 site-days, same sites and the same blend.

```
python scripts/run_14day_flagship_study.py --start 2026-07-18 --end 2026-08-14 --window-label B --out-dir logs/overnight_improve/final_v3/window_B --model-dir papers/appendix_numerical_tables/locked_saved_model --csv data/ingested_extended/extended_training_window_B_ready.csv
```

Open `logs/overnight_improve/final_v3/window_B/summary.json`. Solar RMSE should be about 4.93 versus 5.71. Radiation should be about 0.0259 versus 0.0040.

## 5. Window C (storm historical interval)

Disturbed interval, 4 to 17 May 2024, 42 site-days, same sites.

```
python scripts/run_14day_flagship_study.py --start 2024-05-04 --end 2024-05-17 --window-label C --out-dir logs/overnight_improve/final_v3/window_C --model-dir papers/appendix_numerical_tables/locked_saved_model --csv data/ingested_extended/extended_training_window_B_ready.csv
```

Open `logs/overnight_improve/final_v3/window_C/summary.json`. Solar RMSE should tie at about 18.62. Radiation should be about 0.214 versus 0.194.

## 6. Mission simulation (Figure 10)

Go to [run_mission_sim_radiation_eva.py](../../scripts/run_mission_sim_radiation_eva.py).

```
python scripts/run_mission_sim_radiation_eva.py --out-dir logs/study_mission_sim_radiation_eva
```

Compare caution and no-go times with Section 6.4. LIPAS caution is at T+45 and no-go is at T+85. This run is not an RMSE result.

## 7. Ablation (Tables 5 and 6)

Quiet subset 5--18 July 2026 (42 site-days within Window A). Go to [run_hazard_ablation_study.py](../../scripts/run_hazard_ablation_study.py).

```
python scripts/run_hazard_ablation_study.py --start 2026-07-05 --end 2026-07-18 --out-dir logs/overnight_improve/ablation_A_quiet
```

Compare the RMSE changes with Tables 5 and 6. Replacing the live solar input with its subset mean raises radiation RMSE from 0.1173 to 0.1196 and lowers solar RMSE from 5.142 to 3.171. Do not retrain.
