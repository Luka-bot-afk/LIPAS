# Train4 GO-NIGHT ledger (ART-28)

Win bar: held-out RMSE < train-2 **4.9685** (target ≤~4.0); ≥5/6 hazard wins on chosen summer+storm windows; radiation ML share > 0.

Format: `timestamp | change | retrain? Y/N | heldout_rmse | A_wins 0-6 | B_wins 0-6 | solar_A/B | rad_A/B | decide keep/discard | next`

| timestamp (UTC) | change | retrain? | heldout_rmse | A_wins | B_wins | solar_A/B | rad_A/B | decide | next |
|---|---|---|---|---|---|---|---|---|---|
| 2026-11-05T20:59Z | Baseline verify: appendix locked_saved_model == saved_model_train2_locked; test_rmse=4.9685; serve blend=[0.4,0,0,0,0,0] (rad=0 — must restore) | N | 4.9685 | - | - | - | - | keep baseline | Kaggle auth OK; pack T4a |
| 2026-11-05T20:58Z | Prior art: train6=7.11, train7=6.92 — both miss bar on GPU rematch | N | 6.92–7.11 | - | - | - | - | discard priors | Climb T4a ladder (channel_norm + solar/rad priority) |
| 2026-11-05T21:08Z | BLOCKER: Kaggle GPU unavailable — enable_gpu/machine_shape=NvidiaTeslaT4 accepted but nvidia-smi missing, TF GPUs=[]; T4a v1–v3 + gpu-probe all ERROR. Refused CPU fallback. | N | - | - | - | - | - | STOP | User must restore Kaggle GPU quota/access |
