# READY_FOR_DRAFT30_R6

**Status:** READY_FOR_PAPER (measured artifacts only — no LaTeX rewrite)

## Package
- **R6c_caution_cap090** (R5s2 + caution_cap090 / false_alarm_guard quiet_rad_cap=0.090)
- Model dir: `saved_model_R6c_caution_cap090`
- Branch: `cursor/draft30-r6-reshape-ff97`

## Windows (ASR-best under R6c)
| Window | Dates | Days | Wins | Note |
|---|---|---:|---:|---|
| **A summer** | 2026-06-01 → 2026-08-04 | 65 | **6/6** | Longest 6/6; ≥90d grid were 5/6 (dust miss) |
| **B storm** | 2024-04-20 → 2024-05-20 | 31 | **6/6** | Best among storm cands (wins, length, solar+rad margin) |

Sites: 0°N 0°E, Apollo 11, Nobile Rim.

## Mission sim (measured)
- LIPAS caution **T+50** / NO-GO **T+55**
- NASA GOES caution T+80 / NO-GO T+105
- NASA combined caution T+55 / NO-GO T+70
- LIPAS NO-GO leads GOES NO-GO by **50 min**

## Ablation (quiet fortnight 2026-06-17→06-30 inside A)
- Baseline solar RMSE **11.563** / rad **1.702**
- Worst one-away (both channels): remove solar → solar +10.7%, rad +0.23%

## Figures
`studies/draft30_r6/figures/` — see `FIGURE_MANIFEST.json`
- ONE prototype: `fig_prototype_offchart.png` (temp + off-chart hazards)
- Per-hazard Window A/B line charts (label / LIPAS / NASA)
- `fig_architecture_blend.png`, `fig_mission_timeline.png` (draft-22 style)
- Drop old six-hazard prototype + separate LIPAS-vs-GOES skill bars (paper should use table for mission)

## Paths
- SELECTED: `studies/draft30_r6/SELECTED_WINDOWS.json`
- READY: `studies/draft30_r6/READY_FOR_DRAFT30_R6.json`
- Mission: `studies/draft30_r6/mission_sim/`
- Ablation: `studies/draft30_r6/ablation/`
- Window raw: `logs/overnight_improve/train4/studies_R6c_draft30/{A,B_storm}/`
