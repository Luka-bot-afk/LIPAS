| utc | tag | A_wins | B_wins | notes |
|---|---|---:|---:|---|
| 2026-11-06T15:09Z | WAVE R1 START | - | - | - | regime solar/rad/mq/temp + GCR variants |
| 2026-11-06T15:11Z | R1s_solar_clim_pull15 | 6 | 4 | solarB=False |
| 2026-11-06T15:12Z | R1s2_solar_clim_pull25 | 6 | 4 | solarB=False |
| 2026-11-06T15:14Z | R1s3_solar_clim_low_target | 6 | 4 | solarB=False |
| 2026-11-06T15:15Z | R1a_storm_solar_108 | 6 | 6 | solarB=True |
| 2026-11-06T15:17Z | R1a2_storm_solar_112 | 6 | 6 | solarB=True |
| 2026-11-06T15:18Z | R1a3_storm_solar_add_only | 6 | 6 | solarB=True |
| 2026-11-06T15:19Z | R1c_storm_couple | 6 | 6 | solarB=True |
| 2026-11-06T15:21Z | R1d_gcr_120 | 6 | 5 | solarB=False |
| 2026-11-06T15:22Z | R1e_temp_daynight | 6 | 5 | solarB=False |
| 2026-11-06T15:23Z | R1f_mq_tidal | 5 | 4 | solarB=False |
| 2026-11-06T15:25Z | R1g_combo | 5 | 5 | solarB=True |
| 2026-11-06T15:26Z | R2a_wsolar_50 | 5 | 5 | solarB=False |
| 2026-11-06T15:27Z | R2b_wrad_20 | 6 | 4 | solarB=False |
| 2026-11-06T15:27Z | WAVE R1 DONE | - | - | - | see cpu_levers/drastic_R1_summary.json |
| 2026-11-06T16:00Z | WAVE R2 START | - | - | - | merge R1a2 solar + R1c rad; no mq tidal |
| 2026-11-06T16:01Z | R2m_a2_c | 6 | 5 | solarB=True |
| 2026-11-06T16:02Z | R2m2_solar115_rad | 6 | 6 | solarB=True |
| 2026-11-06T16:03Z | R2m3_rad_hard | 6 | 5 | solarB=True |
| 2026-11-06T16:05Z | R2m4_solar118 | 6 | 5 | solarB=True |
| 2026-11-06T16:06Z | R2m5_solar_add_hard | 6 | 5 | solarB=True |
| 2026-11-06T16:07Z | R2t_merge_temp_mild | 5 | 5 | solarB=True |
| 2026-11-06T16:47Z | R2u_unsettled_soft | 6 | 5 | solarB=True |
| 2026-11-06T16:48Z | R2s_sep_heavy | 6 | 5 | solarB=True |
| 2026-11-06T16:49Z | R2p_persist_merge | 5 | 5 | solarB=True |
| 2026-11-06T16:50Z | R2p2_persist_storm_only | 5 | 4 | solarB=True |
| 2026-11-06T16:50Z | WAVE R2 DONE | - | - | - | see cpu_levers/drastic_R2_summary.json |
| 2026-11-06T16:54Z | WAVE R3 START | - | - | - | post-regime persist + solar climb; NOT_READY lock |
