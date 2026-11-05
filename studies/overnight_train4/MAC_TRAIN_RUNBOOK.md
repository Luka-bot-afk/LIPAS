# Mac GO-NIGHT runbook (ART-28)

User authorized Mac after Kaggle GPU failed (CUDA never attached). Quality OK — train-2 best was Mac.

## Win bar
- Held-out RMSE **< 4.9685** (target ≤ ~4.0)
- ≥5/6 hazards beat NASA/replica on chosen summer Window A + storm Window B (1 miss OK)
- Radiation ML blend **> 0** always (never zero as a “fix”)
- No paper rewrite; result patches only after promote

## Credit-smart order
1. Locate repo → checkout `cursor/go-night-train4-e2f9`
2. Ensure CSV: `data/ingested_extended/train7_training_locked_y_ext_drivers.csv` (download from Kaggle dataset `lukatakki/lipas-train4` if missing)
3. Restore baseline: copy `papers/appendix_numerical_tables/locked_saved_model/` → `saved_model_train2_locked/` + `saved_model/`
4. **Cheap checks first** (no full retrain): `ALLOW_TRAIN4=1 python scripts/train4_kaggle.py --stage cheap`
5. **T4a** retrain: `ALLOW_TRAIN4=1 python scripts/train4_kaggle.py --stage t4a`
6. If held-out misses → **T4b** residual (solar+rad) → **T4c** capacity
7. On beat: blend sweep all `w>0`, Window A summer grid, Window B storm grid, promote
8. **After promote (required before paper):** re-run mission sim + ablation + final Window A/B studies; push artifacts/ledger
9. Paper draft 30 only **after** those new numbers exist (cloud/paper agent) — never from old draft25 numbers alone
10. Log every row in `logs/overnight_improve/train4/ledger.md`

## Honesty
Do not claim NASA wins via circular labels (label ≈ physics). Fix residual/features first.
Do not stop after one failed retrain.

## Commands (repo root)
```bash
export ALLOW_TRAIN4=1
export TF_CPP_MIN_LOG_LEVEL=2
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
# + tensorflow-macos / tensorflow-metal if Apple Silicon and not already present
python scripts/train4_kaggle.py --stage cheap
python scripts/train4_kaggle.py --stage t4a
```
