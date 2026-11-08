# Drastic wins R6 LAST-SHOT — FINAL (Mac)

**Promote: READY_R6**

## Best package: `R6c_caution_cap090`

R5s2 base + `false_alarm_guard` quiet_rad_cap=0.090 (fixes caution@0 mission false-alarm).

| | A | B | C | solar B | rad B | temp A | caution | NO-GO |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| R5s2 (base) | 6 | 6 | 4 | 15.2239 | 0.0940 | 19.8488 | 0‡ | 55 |
| **R6c_caution_cap090** | **6** | **6** | **5** | **15.2239** | **0.0939** | **19.8384** | **50** | **55** |
| L20 | 6 | 5 | — | 18.6233 | 0.1901 | 22.2094 | 50† | 85† |

† L20 mission_sim locked. ‡ R5 caution@0 false-alarm.

Δ vs R5s2: caution **0→50** (matches L20-class timing); solar/rad/temp held (temp A −0.010); C_stress 4→5; NO-GO unchanged at 55.

## Why READY_R6 (honest)
- Cheap caution@0 mission false-alarm **fixed** without regressing A6/B6 or storm solar/rad.
- Stress C improved vs R5s2.
- Residual Metal retrain **aborted** (T4b gate); residual bias serve **killed** (B5).
- lunar_physics knobs: mild keep curiosity (A6/B6) but nogo 60 (no climb vs R5s2); storm-kp flat on RMSE.

## Families (9 cands) — keep / kill
| Family | Cands | Verdict |
|---|---|---|
| control | R6_base_r5s2 | KEEP reference (still caution=0) |
| caution FA guard | **R6c_caution_cap090** / c2 / c3 | **KEEP c**; KILL c2 (B5 solar cap); c3 nogo regress |
| lunar_physics knobs | R6p / p2 | KEEP p curiosity (A6/B6); KILL p2 (B5) |
| residual bias | R6r / R6x_resid | **KILL** (B5; gate abort Metal) |
| combo | R6x_caution_lunar | KEEP curiosity; nogo 60 no beat |

## Residual gate
- abort_metal_retrain: **True** (T4b RMSE 44 vs train2 4.97)
- allow_residual_correct: solar=False, radiation=True, temperature=True — serve bias still window-killed

## Wall note
RMSE NASA-wow climb beyond R5s2 **not** found on residual/lunar last-shots. READY_R6 is the **mission caution integrity** win on top of R5s2, not a further solar Δ climb. Further untried families for RMSE = exhausted → treat as soft wall on RMSE; do not grind R1–R5 kills.

No paper.
