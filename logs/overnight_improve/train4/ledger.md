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
| 2026-11-05T23:02Z | USER ORDER LOCKED overnight: (1) full T4a→b→c no early stop pick best (2) serve/blend/Diviner fine-tune (3) windows+mission+ablation (4) draft30 paper only after real numbers | N | - | - | - | - | - | keep | companion runner armed |
| 2026-11-05T23:02Z | ORDER LOCKED: (1) full T4a→T4b→T4c pick best (2) serve/blend fine-tune (3) windows+mission+ablation (4) paper later | N | - | - | - | - | - | keep | climb |
| 2026-11-05T23:02Z | Waiting for in-flight T4a gate (or starting T4a) | Y | pending | - | - | - | - | running | |
| 2026-11-05T23:15Z | HEARTBEAT: T4a ALIVE Epoch 38/80 Metal GPU PID7009 etime=19:01; companion go-night-full waiting; no restart needed | Y | pending | - | - | - | - | running | continue T4b→T4c after gate |
| 2026-11-05T23:19Z | T4a DONE test_rmse=55.12861604140471 beats_train2=False | Y | 55.12861604140471 | - | - | - | - | discard | T4b residual |
| 2026-11-05T23:19Z | T4b START residual solar+rad | Y | pending | - | - | - | - | running | |
| 2026-11-05T23:20Z | T4a DONE test_rmse=55.12861604140471 beats=False | Y | 55.12861604140471 | - | - | - | - | record | always continue T4b |
| 2026-11-05T23:20Z | T4b START residual solar+rad (always; no early stop) | Y | pending | - | - | - | - | running | |
| 2026-11-05T23:22Z | T4a DONE test_rmse=55.1286 beats=False (temp RMSE=134 dominates; norm=20.18 vs pers=19.91); blend wrote w>0; fit_blend load quirk nonfatal; legacy T4b crashed distutils | Y | 55.1286 | - | - | - | - | discard | fix distutils; start T4b residual then T4c |
| 2026-11-05T23:22Z | ORDER LOCKED: (1) full T4a→T4b→T4c pick best (2) serve/blend fine-tune (3) windows+mission+ablation (4) paper later | N | - | - | - | - | - | keep | climb |
| 2026-11-05T23:22Z | T4a DONE test_rmse=55.12861604140471 beats=False | Y | 55.12861604140471 | - | - | - | - | record | always continue T4b |
| 2026-11-05T23:22Z | T4b START residual solar+rad (always; no early stop) | Y | pending | - | - | - | - | running | |
| 2026-11-05T23:23Z | T4b START residual solar+rad (90 ep) after distutils sitecustomize fix; T4a discarded 55.13 | Y | pending | - | - | - | - | running | then T4c always |
| 2026-11-05T23:42Z | HEARTBEAT: T4b ALIVE Epoch 43/90 Metal PID8533 etime=20:25; T4a discarded 55.13; T4c queued | Y | pending | - | - | - | - | running | then T4c |
| 2026-11-06T00:05Z | T4b DONE test_rmse=44.0111486009156 beats=False | Y | 44.0111486009156 | - | - | - | - | record | always continue T4c |
| 2026-11-06T00:05Z | T4c START capacity (always; no early stop) | Y | pending | - | - | - | - | running | |
| 2026-11-06T00:06Z | T4b DONE test_rmse=44.011 beats=False (solar improved 6.61; temp still 107.6; residual eval not comparable 1:1); blend w>0; T4c crashed distutils — restarting | Y | 44.011 | - | - | - | - | discard | T4c capacity now |
| 2026-11-06T00:06Z | ORDER LOCKED: (1) full T4a→T4b→T4c pick best (2) serve/blend fine-tune (3) windows+mission+ablation (4) paper later | N | - | - | - | - | - | keep | climb |
| 2026-11-06T00:06Z | T4a DONE test_rmse=55.12861604140471 beats=False | Y | 55.12861604140471 | - | - | - | - | record | always continue T4b |
| 2026-11-06T00:06Z | T4b DONE test_rmse=44.0111486009156 beats=False | Y | 44.0111486009156 | - | - | - | - | record | always continue T4c |
| 2026-11-06T00:06Z | T4c START capacity (always; no early stop) | Y | pending | - | - | - | - | running | |
| 2026-11-06T00:07Z | T4c START capacity (100 ep, larger LSTM) after distutils re-pin per stage; climbing despite T4a/T4b misses | Y | pending | - | - | - | - | running | pick best after |
| 2026-11-06T00:26Z | HEARTBEAT: T4c ALIVE Epoch 12/100 Metal PID9799 etime=19:19; autopsy prep: train-2 used CSV extended_training_1784310247 not train7 — likely root of temp blow-up mismatch | Y | pending | - | - | - | - | running | on miss: serve on train-2 + targeted retrain on train2 CSV |
| 2026-11-06T00:30Z | USER REINFORCE: not train-only — physics/archive/calendar/serve levers to beat NASA replicas; keep climbing; credit-smart; draft30 only after promote+mission+ablation | N | - | - | - | - | - | keep | Mac apply runbook; cloud standby |
| 2026-11-06T00:31Z | TIMING LOCK: run physics/archive/serve CPU levers NOW in parallel with Metal T4c/T4d — do not wait for ladder end | N | - | - | - | - | - | keep | Mac overlap serve science |
