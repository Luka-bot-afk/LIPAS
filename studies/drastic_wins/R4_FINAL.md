# Drastic wins R4 — FINAL (Mac)

**Promote: READY**

## Best package: `R4l2_lst_bins_40`

| | A | B | solar A | solar B | rad A | rad B | temp A | temp B |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| L20 | 6 | 5 | 14.1465 | 18.6233 | 1.2550 | 0.1901 | 22.2094 | 26.9938 |
| R3b | 6 | 6 | 13.9386 | 15.8290 | 1.2132 | 0.0969 | 22.2034 | 27.0091 |
| **R4l2_lst_bins_40** | **6** | **6** | **13.9347** | **15.8290** | **1.2132** | **0.0969** | **19.8333** | **25.3210** |

Δ vs L20 (R4l2_lst_bins_40): solar B +2.7943; rad B +0.0932; temp A +2.3762; temp B +1.6727.

## Why this call
- R3t kill was wrong-sign night_add; corrected day+/night− and LST bins move temp for real.
- Best holds R3b solar/rad exactly while cutting temp A RMSE by 2.38°C.
- ASR-interesting=True (temp A substantial ≥1.5 and B not badly regressed).

## Keep / kill
- KEEP: R4l2_lst_bins_40, R4l3_lst30_div04, R4l_lst_bins_25, R4t2_dn_correct_med, R4t3_dn_correct_optA
- KILL: heavy diviner (R4d3), weak seasonal-only, physics_pull alone (flat)

## Checks
```json
{
  "A6_B6": true,
  "holds_R3b_solar_B": true,
  "holds_R3b_rad_B": true,
  "temp_A_delta_vs_L20": 2.376157143149779,
  "temp_B_delta_vs_L20": 1.6727308910276832,
  "temp_A_ops_useful_ge_0.5": true,
  "temp_A_substantial_ge_1.5": true,
  "temp_B_not_regressed": true,
  "solar_B_delta_vs_L20": 2.7942836472276227,
  "rad_B_delta_vs_L20": 0.09324123245411296,
  "beats_R3b_temp_A": true,
  "ASR_interesting": true,
  "promote": "READY"
}
```

No paper until user says so (even if READY).
