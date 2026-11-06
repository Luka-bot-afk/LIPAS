# L20 measured window RMSE (locked serve package)

Source summaries under `logs/overnight_improve/train4/cpu_levers/windows_L20_may_dust_l16/`.

**Honesty:** meteor labels are physics-constructed (circular risk); dust is physics-dominated.


## Window_A_2026-06-17_to_2026-07-14

| Hazard | Hybrid RMSE | Flagship RMSE | Hybrid beats? |
|--------|------------:|--------------:|:-------------:|
| solar_activity | 14.1465 | 14.1748 | True |
| radiation_mSv | 1.2550 | 1.2590 | True |
| temperature_C | 22.2094 | 22.3185 | True |
| moonquakes_per_day | 1.3135 | 1.3203 | True |
| meteor_flux_1e15 | 0.0131 | 0.6060 | True |
| dust_g_cm3 | 0.5428 | 0.5428 | True |

## Storm_B_2024-05-04_to_2024-05-17

| Hazard | Hybrid RMSE | Flagship RMSE | Hybrid beats? |
|--------|------------:|--------------:|:-------------:|
| solar_activity | 18.6233 | 18.6233 | False |
| radiation_mSv | 0.1901 | 0.1935 | True |
| temperature_C | 26.9938 | 27.1897 | True |
| moonquakes_per_day | 1.2870 | 1.2871 | True |
| meteor_flux_1e15 | 0.0124 | 0.6223 | True |
| dust_g_cm3 | 0.5443 | 0.5488 | True |
