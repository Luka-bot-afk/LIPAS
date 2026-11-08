# Drastic wins R2 — FINAL (Mac)

**Promote: NOT_READY**

## Best package: `R2m2_solar115_rad`

| | A | B | solar A | solar B | rad A | rad B | temp A |
|---|---:|---:|---:|---:|---:|---:|---:|
| L20 | 6 | 5 | 14.1465 | 18.6233 | 1.2550 | 0.1901 | 22.2094 |
| R2m2_solar115_rad | 6 | 6 | 13.9630 | 16.5488 | 1.2218 | 0.0949 | 22.2020 |
| Δ vs L20 | | | +0.1834 | +2.0745 | +0.0333 | +0.0952 | +0.0075 |

vs R1c: solar B 16.5488 (R1c 17.3524); rad B 0.0949 (R1c 0.1153).

## Checks
{
  "storm_solar_tie_broken": true,
  "solar_A_3x_L20_flag_margin": true,
  "rad_A_3x": true,
  "rad_B_3x": true,
  "temp_A_improved_vs_L20": false,
  "A6_B6": true,
  "beats_R1c_composite": true
}

## Reason
R2 best clears solar+rad substantial bars and A6/B6, but temp vs L20 still epsilon (not ~3× / ops-useful). Persist family KILL (quiet A solar regress + rad overshoot). Climb R3 on temp/mq-safe solar or declare plateau on temp.

## Kill / keep
- KILL persist R2p_*, sep_heavy rad overshoot, temp_mild, mq-tip merges
- KEEP `R2m2_solar115_rad` as new best; R1c/R1a2 still useful baselines

No paper.
