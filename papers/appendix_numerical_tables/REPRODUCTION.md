# Reproduce each study

Open this file from the paper appendix. Each study is separate. Run commands from the repository root after:

```
git clone https://github.com/Luka-bot-afk/LIPAS.git
cd LIPAS
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Paper tables use blend weights solar 0.4, radiation 0.05, and 0 for temperature, moonquakes, micrometeorites, and dust. The model directory is `saved_model`. That folder is not in this public repository. Keep your local copy unchanged. You can still open every file linked below without it.

## 1. Qualitative comparison (Table 2)

Go to [LIPAS_qualitative_comparison_framework.md](LIPAS_qualitative_comparison_framework.md).

Score DONKI, Diviner, LDEX, Apollo PSE, MEM 3, GOES-18, and LIPAS on the nine criteria. Do not turn the labels into numbers and do not add them up. Compare your scores with Table 2.

## 2. Prototype (April diagnostic, Figures 4 and 5)

This is the daytime run at 0°N, 0°E from 5 to 19 April 2026. It is not the fourteen-day result.

Go to [LIPAS_appendix_numerical_tables_A_B_D_E.pdf](LIPAS_appendix_numerical_tables_A_B_D_E.pdf). If the preview is blank, use Download. April rows start on the second page. There is no separate script for this checkpoint. Do not paste these rows into the Window A or Window B tables.

## 3. Window A (Table 3, Figure 6)

Night-dominant, 5 to 18 July 2026, 42 site-days, at 0°N 0°E, Apollo 11, and Nobile Rim.

Go to [run_14day_flagship_study.py](../../scripts/run_14day_flagship_study.py).

```
python scripts/run_14day_flagship_study.py --start 2026-07-05 --end 2026-07-18 --window-label A --out-dir logs/study_14day_window_A_night --model-dir saved_model --csv data/ingested_extended/extended_training_window_B_ready.csv
```

Open `logs/study_14day_window_A_night/summary.json`. Solar RMSE should be about 4.10 versus 4.66. Radiation should be about 0.119 versus 0.102. The checked numbers are in [reported_window_rmse.md](reported_window_rmse.md).

## 4. Window B (Table 4, Figure 8)

Dayside-dominant, 22 July to 4 August 2026, same sites and the same blend.

```
python scripts/run_14day_flagship_study.py --start 2026-07-22 --end 2026-08-04 --window-label B --out-dir logs/study_14day_window_B_day --model-dir saved_model --csv data/ingested_extended/extended_training_window_B_ready.csv
```

Open `logs/study_14day_window_B_day/summary.json`. Solar RMSE should be about 4.99 versus 5.99. Radiation should be about 0.0188 versus 0.00266.

## 5. Mission simulation (Figure 10)

Go to [run_mission_sim_radiation_eva.py](../../scripts/run_mission_sim_radiation_eva.py).

```
python scripts/run_mission_sim_radiation_eva.py --out-dir logs/study_mission_sim_radiation_eva
```

Compare caution and no-go times with Section 6.4. LIPAS caution is at T+45 and no-go is at T+85. This run is not an RMSE result.

## 6. Ablation (Tables 5 and 6)

Go to [run_hazard_ablation_study.py](../../scripts/run_hazard_ablation_study.py).

```
python scripts/run_hazard_ablation_study.py --out-dir logs/study_ablation_window_A
```

Compare the RMSE changes with Tables 5 and 6. Replacing the live solar input with its Window A mean raises radiation RMSE from 0.1020 to 0.1050. The same replacement lowers solar RMSE from 3.899 to 3.290. Do not retrain.
