# Train4 GO-NIGHT ledger (ART-28)

Win bar: held-out RMSE < train-2 **4.9685** (target ≤~4.0); ≥5/6 hazard wins on chosen summer+storm windows; radiation ML share > 0.

Format: `timestamp | change | retrain? Y/N | heldout_rmse | A_wins 0-6 | B_wins 0-6 | solar_A/B | rad_A/B | decide keep/discard | next`

| timestamp (UTC) | change | retrain? | heldout_rmse | A_wins | B_wins | solar_A/B | rad_A/B | decide | next |
|---|---|---|---|---|---|---|---|---|---|
| 2026-11-05T20:59Z | Baseline verify: appendix locked_saved_model == saved_model_train2_locked; test_rmse=4.9685; serve blend=[0.4,0,0,0,0,0] (rad=0 — must restore) | N | 4.9685 | - | - | - | - | keep baseline | Kaggle auth OK; pack T4a |
| 2026-11-05T20:58Z | Prior art: train6=7.11, train7=6.92 — both miss bar on GPU rematch | N | 6.92–7.11 | - | - | - | - | discard priors | Climb T4a ladder (channel_norm + solar/rad priority) |
| 2026-11-05T21:08Z | BLOCKER: Kaggle GPU unavailable — enable_gpu/machine_shape=NvidiaTeslaT4 accepted but nvidia-smi missing, TF GPUs=[]; T4a v1–v3 + gpu-probe all ERROR. Refused CPU fallback. | N | - | - | - | - | - | STOP | User must restore Kaggle GPU quota/access |
| 2026-11-05T22:39Z | User GO Mac path: worker Lukas-MacBook-Air-2 online (id 2414b5dd…); Kaggle GPU still dead; requested CreateAgent on Mac; runbook added | pending | - | - | - | - | - | waiting Mac agent | cheap→T4a→T4b→T4c |
| 2026-11-05T22:50Z | Mac ART-28 start: cloned PR#5 branch; restored train2_locked blend=[0.4,0,0,0,0,0]; TF 2.16.2 Metal GPU; CSV linked; ALLOW_TRAIN4=1 | N | 4.9685 | - | - | - | - | keep | run cheap then T4a |
| 2026-11-05T22:51Z | Cheap residual ridge: rad skill=0.029 temp=0.058 moonq=0.029 solar=0.012; meteor+dust CIRCULAR corr=1.0; recommend_residual_head=Y | N | 4.9685 proxy | - | - | - | - | keep probes | T4a channel_norm solar/rad priority; later T4b residual for rad |
| 2026-11-05T22:51Z | T4a START Mac Metal (80 ep, channel_norm, solar/rad priority) | Y | pending | - | - | - | - | running | wait held-out |
| 2026-11-05T22:52Z | T4a START Mac Metal (80 ep, channel_norm, solar/rad priority) | Y | pending | - | - | - | - | running | wait held-out |
| 2026-11-05T22:54Z | T4a crash: missing flask (import space_weather_model); installed deps; restarting ladder | Y | - | - | - | - | - | discard crash | restart T4a |
| 2026-11-05T22:54Z | T4a START Mac Metal (80 ep, channel_norm, solar/rad priority) | Y | pending | - | - | - | - | running | wait held-out |
| 2026-11-05T22:56Z | T4a START Mac Metal (80 ep) after deps fix | Y | pending | - | - | - | - | running | wait held-out |
