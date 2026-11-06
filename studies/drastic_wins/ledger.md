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
| 2026-11-06T16:58Z | WAVE R3 START | - | - | - | post-regime persist + solar climb; NOT_READY lock |
| 2026-11-06T16:59Z | R3a_m2_soft_persist | 6 | 5 | solarB=True |
| 2026-11-06T17:01Z | R3a2_m2_persist_med | 5 | 5 | solarB=True |
| 2026-11-06T17:02Z | R3a3_persist_storm_cmax | 6 | 5 | solarB=True |
| 2026-11-06T17:03Z | R3b_solar120_m2rad | 6 | 6 | solarB=True |
| 2026-11-06T17:04Z | R3b2_solar120_mq_soft | 5 | 5 | solarB=True |
| 2026-11-06T17:06Z | R3c_add_hard_cmax | 6 | 5 | solarB=True |
| 2026-11-06T17:07Z | R3d_m2_soft_clim | 6 | 6 | solarB=True |
| 2026-11-06T17:08Z | R3e_m2_persist_clim | 6 | 5 | solarB=True |
| 2026-11-06T17:09Z | R3t_night_temp_025 | 6 | 5 | solarB=True |
| 2026-11-06T17:10Z | R3f_temp_band_clip | 6 | 6 | solarB=True |
| 2026-11-06T17:12Z | R3g_rad_climb_cmax | 6 | 6 | solarB=True |
| 2026-11-06T17:13Z | R3h_persist_storm_hard | 6 | 5 | solarB=True |
| 2026-11-06T17:13Z | WAVE R3 DONE | - | - | - | see cpu_levers/drastic_R3_summary.json |
| 2026-11-06T17:19Z | WAVE R4 START | - | - | - | TEMP on R3b base; correct day+/night- ; NOT_READY lock |
| 2026-11-06T17:20Z | R4t_dn_correct_mild | 6 | 5 | tempA=21.798294884152114 |
| 2026-11-06T17:21Z | R4t2_dn_correct_med | 6 | 6 | tempA=21.52899763523056 |
| 2026-11-06T17:23Z | R4t3_dn_correct_optA | 6 | 6 | tempA=21.35244469676122 |
| 2026-11-06T17:24Z | R4t4_dn_dawn_window | 6 | 5 | tempA=21.740595483062226 |
| 2026-11-06T17:25Z | R4d_diviner_03 | 6 | 5 | tempA=22.1185496873858 |
| 2026-11-06T17:26Z | R4d2_diviner_08 | 6 | 5 | tempA=22.22030211739392 |
| 2026-11-06T17:28Z | R4d3_diviner_15 | 5 | 5 | tempA=22.820115014014352 |
| 2026-11-06T17:29Z | R4d4_diviner_dn_mild | 6 | 5 | tempA=21.811908102519656 |
| 2026-11-06T17:30Z | R4s_seasonal_05 | 6 | 6 | tempA=22.200271361093236 |
| 2026-11-06T17:32Z | R4s2_seasonal_10 | 6 | 5 | tempA=22.178310802902477 |
| 2026-11-06T17:33Z | R4s3_seasonal_div_dn | 6 | 5 | tempA=21.872884915202103 |
| 2026-11-06T17:34Z | R4l_lst_bins_25 | 6 | 6 | tempA=20.62575272084577 |
| 2026-11-06T17:36Z | R4l2_lst_bins_40 | 6 | 6 | tempA=19.833285363277913 |
| 2026-11-06T17:37Z | R4l3_lst30_div04 | 6 | 6 | tempA=20.275754979394993 |
| 2026-11-06T17:38Z | R4p_physics_pull_35 | 6 | 6 | tempA=22.213756808009993 |
| 2026-11-06T17:40Z | R4p2_phys_dn_mild | 6 | 6 | tempA=21.906262501589907 |
| 2026-11-06T17:41Z | R4r_regime_temp_dn | 6 | 6 | tempA=21.81489725552661 |
| 2026-11-06T17:41Z | WAVE R4 DONE | - | - | - | see cpu_levers/drastic_R4_summary.json |
| 2026-11-06T18:25Z | WAVE R5 START | - | - | - | R4l2 base; NEW families; mission lead proxy; wall climb; owner bc-4bbf4026 |
| 2026-11-06T18:28Z | R5_base_r4l2 | 6 | 6 | nogo=60;caution=0 |
| 2026-11-06T18:30Z | R5q_quiet_solar_shrink | 6 | 6 | nogo=65;caution=0 |
| 2026-11-06T18:33Z | R5q2_quiet_solar_lift | 6 | 6 | nogo=60;caution=0 |
| 2026-11-06T18:35Z | R5e_early_warn_rad | 6 | 6 | nogo=60;caution=0 |
| 2026-11-06T18:38Z | R5e2_early_warn_hard | 6 | 5 | nogo=60;caution=0 |
| 2026-11-06T18:41Z | R5s_soft_regime | 6 | 5 | nogo=60;caution=0 |
| 2026-11-06T18:43Z | R5s2_soft_plus_ew | 6 | 6 | nogo=55;caution=0 |
| 2026-11-06T18:46Z | R5p_rad_formula_105 | 6 | 5 | nogo=60;caution=0 |
| 2026-11-06T18:48Z | R5p2_rad_formula_108 | 6 | 6 | nogo=60;caution=0 |
| 2026-11-06T18:51Z | R5a_couple_strong | 6 | 5 | nogo=60;caution=0 |
| 2026-11-06T18:53Z | R5a2_couple_ew | 6 | 5 | nogo=60;caution=0 |
| 2026-11-06T18:56Z | R5m_mq_lat | 5 | 5 | nogo=60;caution=0 |
| 2026-11-06T18:58Z | R5t_lst_48 | 6 | 5 | nogo=65;caution=0 |
