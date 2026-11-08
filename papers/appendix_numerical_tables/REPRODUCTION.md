# Reproduce each study (Draft 30 / R6c_caution_cap090)

Open this file from the paper appendix. Each study is separate. Run commands from the repository root after:

```
git clone https://github.com/Luka-bot-afk/LIPAS.git
cd LIPAS
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Paper tables use the R6c_caution_cap090 serve package on train-2 LSTM weights: blend `[0.40, 0.15, 0.02, 0.02, 0.03, 0.01]` with storm-aware adaptive gating. Canonical lock: `saved_model_R6c_caution_cap090/` (also `studies/draft30_r6/`). Train-2 weights alone remain in `papers/appendix_numerical_tables/locked_saved_model/`. Overnight T4a/b/c held-out did **not** beat train-2 (~4.97); do not substitute a new LSTM.

Honesty: micrometeorite labels are shower-augmented physics (circular); dust is physics-dominated / near-circular.

## 1. Qualitative comparison (Table 2)

Go to [LIPAS_qualitative_comparison_framework.md](LIPAS_qualitative_comparison_framework.md).

## 2. Prototype (April diagnostic)

Go to [LIPAS_appendix_numerical_tables_A_B_D_E.pdf](LIPAS_appendix_numerical_tables_A_B_D_E.pdf). April rows start on the second page. Paper figure: `fig_prototype_offchart.png` (temperature + off-chart hazards). Do not paste these rows into the Window A/B tables.

## 3. Window A (summer)

1 June to 4 August 2026, 195 site-days.

```
python scripts/run_14day_flagship_study.py --start 2026-06-01 --end 2026-08-04 --window-label A --out-dir logs/overnight_improve/train4/studies_R6c_draft30/A --model-dir saved_model_R6c_caution_cap090 --csv data/ingested_extended/extended_training_window_B_ready.csv
```

Checked numbers: [reported_window_rmse_R6.md](reported_window_rmse_R6.md). Solar ≈9.532 vs 9.889; radiation ≈0.798 vs 0.829 (6/6).

## 4. Window B (storm)

20 April to 20 May 2024, 93 site-days.

```
python scripts/run_14day_flagship_study.py --start 2024-04-20 --end 2024-05-20 --window-label B --out-dir logs/overnight_improve/train4/studies_R6c_draft30/B_storm --model-dir saved_model_R6c_caution_cap090 --csv data/ingested_extended/extended_training_window_B_ready.csv
```

Checked numbers: [reported_window_rmse_R6.md](reported_window_rmse_R6.md). Solar ≈11.22 vs 13.79; radiation ≈0.071 vs 0.172 (6/6).

## 5. Mission simulation

See `studies/draft30_r6/mission_sim/`. LIPAS caution T+50 / NO-GO T+55; GOES T+80 / T+105; combined T+55 / T+70.

## 6. Ablation

Quiet fortnight 17–30 June 2026 inside Window A. Baseline solar RMSE ≈11.563 / rad ≈1.702. Worst one-away (both channels): remove solar (solar +10.7%, rad +0.23%). See `studies/draft30_r6/ablation/`.

## Canonical READY package

- `studies/draft30_r6/READY_FOR_DRAFT30_R6.json`
- `studies/draft30_r6/READY_FOR_DRAFT30_R6.md`
- `studies/draft30_r6/SELECTED_WINDOWS.json`
