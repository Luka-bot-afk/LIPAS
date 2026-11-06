# Drastic wins R5 — FINAL (Mac)

**Promote: READY_R5**

## Best package: `R5s2_soft_plus_ew`

R4l2 base + soft_regime_mix + early_warning_rad (ablation-aware couple retained).

| | A | B | C | solar B | rad B | temp A | caution | NO-GO |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| L20 | 6 | 5 | — | 18.6233 | 0.1901 | 22.2094 | 50† | 85† |
| R4l2 | 6 | 6 | — | 15.8290 | 0.0969 | **19.8333** | — | — |
| R5_base echo | 6 | 6 | 5 | 15.8290 | 0.1116 | 19.8462 | 0‡ | 60 |
| **R5s2_soft_plus_ew** | **6** | **6** | 4 | **15.2239** | **0.0940** | 19.8488 | 0‡ | **55** |
| alt R5e_early_warn_rad | 6 | 6 | 5 | 15.8290 | **0.0830** | 19.8469 | 0‡ | 60 |

† L20 mission_sim locked study. ‡ R5 mission proxy caution@0 = false-alarm vs L20; judge NO-GO relative to R5_base.

Δ vs R4l2 (R5s2): solar B **+0.605**; rad B **+0.0029**; temp A −0.016 (flat/slightly worse); NO-GO **5 min earlier** than R5_base.

## Why READY_R5 (honest)
- Clear storm solar climb beyond R4l2 while holding A6/B6 and rad.
- Soft continuous regime + early-warning rad is a **new family** (not LST/solar-scale grind).
- Couple preserved for later ablation story; stress C + mission proxy recorded (cheap).

## Caveats (do not oversell)
- caution=0 false-alarm on proxy — not a primary READY reason vs GOES absolute lead.
- C_stress=4 on best.
- temp held, not improved.

## Families tried (18 cands) — keep / kill
| Family | Cands | Verdict |
|---|---|---|
| control | R5_base_r4l2 | KEEP reference |
| quiet solar | R5q / R5q2 | KILL shrink (later nogo); lift flat |
| early_warning_rad | R5e / R5e2 | **KEEP R5e** (rad B 0.083); KILL hard (B5) |
| soft_regime | R5s / **R5s2** | **KEEP R5s2** (best); KILL soft-only (B5) |
| physics_formula | R5p / R5p2 | KEEP p2 mild; KILL p105 (B5) |
| couple stronger | R5a / R5a2 | KILL (B5) |
| mq_lat | R5m | KILL (A5/B5) |
| LST nudge | R5t / R5t2 | KILL t48 (B5); t2 flat vs R4 |
| ML share | R5w / w2 / w3 | KEEP w2 curiosity (caution=30); KILL w/w3 (B5) |
| combo mission | R5x | KILL (A5/B5/C3) |

## Wall
New-family R5 wave complete (18/18). Further quiet/mq/couple/ML share failed to beat R5s2. **READY_R5** — not EXHAUSTED_AT_R4l2.

No paper until user greenlights.
