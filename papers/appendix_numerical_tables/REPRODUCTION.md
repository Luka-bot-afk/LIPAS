# Reproduce each study (Draft 30 / L20)

Open this file from the paper appendix. Each study is separate. Run commands from the repository root after:

```
git clone https://github.com/Luka-bot-afk/LIPAS.git
cd LIPAS
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Paper tables use the L20 serve package on train-2 LSTM weights: blend `[0.40, 0.15, 0.02, 0.02, 0.03, 0.01]` with storm-aware adaptive gating. Canonical lock: `saved_model_L20_promoted/` (also `logs/overnight_improve/train4/promoted_L20_may_dust_l16/`). Train-2 weights alone remain in `papers/appendix_numerical_tables/locked_saved_model/`. Overnight T4a/b/c held-out did **not** beat train-2 (~4.97); do not substitute a new LSTM.

Honesty: micrometeorite labels are shower-augmented physics (circular); dust is physics-dominated / near-circular.

## 1. Qualitative comparison (Table 2)

Go to [LIPAS_qualitative_comparison_framework.md](LIPAS_qualitative_comparison_framework.md).

## 2. Prototype (April diagnostic)

Go to [LIPAS_appendix_numerical_tables_A_B_D_E.pdf](LIPAS_appendix_numerical_tables_A_B_D_E.pdf). April rows start on the second page. Do not paste these rows into the Window A/B tables.

## 3. Window A (summer)

17 June to 14 July 2026, 84 site-days.

```
python scripts/run_14day_flagship_study.py --start 2026-06-17 --end 2026-07-14 --window-label A --out-dir logs/overnight_improve/train4/cpu_levers/windows_L20_may_dust_l16/A --model-dir saved_model_L20_promoted --csv data/ingested_extended/extended_training_window_B_ready.csv
```

Checked numbers: [reported_window_rmse_L20.md](reported_window_rmse_L20.md). Solar ≈14.15 vs 14.17; radiation ≈1.255 vs 1.259 (6/6).

## 4. Window B (storm)

4 to 17 May 2024, 42 site-days.

```
python scripts/run_14day_flagship_study.py --start 2024-05-04 --end 2024-05-17 --window-label C --out-dir logs/overnight_improve/train4/cpu_levers/windows_L20_may_dust_l16/B_storm --model-dir saved_model_L20_promoted --csv data/ingested_extended/extended_training_window_B_ready.csv
```

Solar exact tie ≈18.62 (counted miss); radiation ≈0.190 vs 0.194 (5/6).

## 5. Mission simulation

Measured package artifacts:

`logs/overnight_improve/train4/studies_L20_locked/mission_sim/`

LIPAS caution T+50 / no-go T+85; GOES caution T+80 / no-go T+105.

## 6. Ablation

Quiet 5--18 July 2026. Artifacts:

`logs/overnight_improve/train4/studies_L20_locked/ablation/`

Baseline solar RMSE ≈5.149; radiation ≈0.105. Worst one-away radiation: remove solar (+1.04%). Worst one-away solar: remove temperature (+0.66%).
