# Mission Simulation — Radiation-Driven EVA Abort
**Site:** Apollo 11 (Mare Tranquillitatis)
**Duration:** 457 min (Apollo 17 EVA-3 length)
**Model:** train2 / second-train hybrid
**Base day drivers:** 2026-07-12
**Step:** every 5 minutes
Radiation is the scripted abort driver because EVA abort decisions are often radiation-led and the 14-day study found hybrid radiation skill vs NASA replicas. This scenario does **not** claim LIPAS is best on every hazard.
| Time | Event |
|---|---|
| T+0 | EVA start (quiet) |
| T+40 | Solar/CME precursor rises (DONKI-like) |
| T+55 | Kp / IMF storm coupling rises |
| T+70 | GOES proton flux surge |
| T+120 | Storm peak region |
| T+457 | Scheduled EVA end |
| System | First CAUTION | First NO-GO |
|---|---|---|
| LIPAS hybrid | T+50 min (0h 50m) | T+85 min (1h 25m) |
| NASA GOES proton product | T+80 min (1h 20m) | T+105 min (1h 45m) |
| NASA combined (physics rad + GOES) | T+55 min (0h 55m) | T+70 min (1h 10m) |
- Storm precursor onset: T+40
- GOES proton surge: T+70
- LIPAS caution relative to precursor: 10 min
- LIPAS caution relative to GOES surge: -20 min
- NASA GOES caution relative to proton surge: 10 min
- Minutes LIPAS NO-GO leads NASA GOES NO-GO: 20
- `eva_timeline.csv`
- `events.json`
