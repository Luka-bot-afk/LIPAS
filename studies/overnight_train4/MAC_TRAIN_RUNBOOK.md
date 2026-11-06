# Mac GO-NIGHT runbook (ART-28)

User authorized Mac after Kaggle GPU failed (CUDA never attached). Quality OK — train-2 best was Mac.

## Mission (locked)
**Beat the NASA/replica baselines we evaluate against** on as many hazards as possible (bar ≥5/6, 1 miss OK). Radiation ML share **> 0**. Held-out clearly better than train-2 **4.9685** when locking a new LSTM; serve/physics wins must be real and honest (no circular labels).

**Not train-only.** LSTM retrain is one lever. Also invent/adapt:
- Physics knobs (Diviner blend, MEM shower amplitude, CRaTER/GCR scale, KP/Bz gains)
- Calendar / archive priors (e.g. seasonal temp rise, Perseids/meteor showers, known storm climatology) so the hybrid *knows* expected structure without needing ML to rediscover it
- Blend / adaptive gates (all channels `w>0`; storm-aware, not radiation→0 “fix”)
- Residual / calibration heads on physics (temp vs Diviner especially)
- Feature emphasis from archives already on disk (Diviner climatology, MEM3, OMNI)

Work **credit-smart**: cheap serve/physics probes before another full retrain; don’t burn epochs if a physics+calendar fix wins the window scores.

## Win bar
- Held-out RMSE **< 4.9685** (target ≤ ~4.0) for any **promoted LSTM**
- ≥5/6 hazards beat NASA/replica on chosen summer Window A + storm Window B (1 miss OK)
- Radiation ML blend **> 0** always
- Temp may beat Diviner via **physics residual / archive climatology**, not only a better LSTM
- No paper rewrite; draft30 only after real results + mission sim + ablation redo

## Timing decision (credit-smart — locked)
**Start physics / archive / serve levers NOW in parallel with ongoing T4c** (or whatever Metal train is running):
- GPU/Metal stays on the retrain
- CPU path runs blend grids, Diviner/MEM/CRaTER knobs, calendar/archive priors on **frozen train2_locked** (and any finished T4* checkpoints) without waiting
- After current train finishes: score that checkpoint + apply best serve package; only then spend another full retrain if still needed

Do **not** idle until the whole ladder ends — T4a/T4b already missed hard; wall-clock is better spent overlapping serve science with T4c/T4d.

## Credit-smart order
1. Locate repo → checkout `cursor/go-night-train4-e2f9`
2. CSV: prefer fair locked-Y train7 / train2 pin (avoid label-drift CSV as Y)
3. Restore baseline: `locked_saved_model` → `saved_model_train2_locked/` + `saved_model/`
4. **Cheap checks** (no full retrain): residual ridge, blend grid, physics knobs, calendar priors
5. Ladder: **T4a → T4b → T4c** (and further arms like T4d train2-CSV if coded) — do not quit after one miss
6. **In parallel with step 5:** serve+physics+archive fine-tune on frozen weights (train2 + finished T4*); keep rad `w>0`
7. When a train finishes: merge best serve package onto it; window-score; only then next heavy retrain if needed
8. If a package beats windows ≥5/6 **and** (held-out win **or** documented hybrid refinement with no fake circular wins): promote candidate
9. **After promote (required before paper):** mission sim + ablation + final Window A/B
10. Paper draft 30 only after those numbers exist
11. Log every row in `logs/overnight_improve/train4/ledger.md`

## Honesty
Do not claim NASA wins via circular labels (meteor/dust corr≈1). Prefer independent physics/calendar contrast or residual-on-honest-proxy.
Do not stop after one failed retrain.

## Commands (repo root)
```bash
export ALLOW_TRAIN4=1
export TF_CPP_MIN_LOG_LEVEL=2
# Prefer companion scripts if present:
#   logs/overnight_improve/train4/run_mac_overnight_full.sh
#   logs/overnight_improve/train4/run_mac_climb_continue.sh
python scripts/train4_kaggle.py --stage cheap
python scripts/train4_kaggle.py --stage t4a   # then t4b / t4c as needed
```
