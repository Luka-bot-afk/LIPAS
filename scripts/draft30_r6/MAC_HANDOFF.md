# Draft30 R6 — Mac handoff (bc-c3926f51)

**Branch:** `cursor/draft30-r6-reshape-ff97` (from `38bd171` / READY_R6)  
**Package:** `R6c_caution_cap090` (`studies/draft30_r6/R6c_package/`)  
**Cloud:** package lock + figure/study scripts; **no paper latex until `READY_FOR_DRAFT30_R6`**

## Run (Mac)

```bash
cd <LIPAS>
git fetch origin cursor/draft30-r6-reshape-ff97 && git checkout cursor/draft30-r6-reshape-ff97 && git pull
# prefer extended CSV if present; else train7 fallback
bash scripts/draft30_r6/run_draft30_studies.sh
```

Produces:
- `studies/draft30_r6/SELECTED_WINDOWS.json`
- `studies/draft30_r6/READY_FOR_PAPER_R6.{json,md}` — prefer naming **`READY_FOR_DRAFT30_R6`** when promoting
- `studies/draft30_r6/figures/` (prototype off-chart ONE fig; per-hazard A/B lines; blend; mission)
- mission + ablation under `studies/draft30_r6/`

When done: rename/write **`studies/draft30_r6/READY_FOR_DRAFT30_R6.md`** + `.json`, commit, push. Cloud then patches draft30 (NO rewrite).

## Figure rules (user)
- Prototype: **one** chart — temp + other hazards off-chart (not two figs)
- Window A long summer (~3mo / best on data); Window B storm; **3 sites**
- Per-hazard line charts: label / LIPAS / NASA; multi-site only where location matters
- Drop separate LIPAS-vs-GOES fig; mission timeline like draft 22
- Better hybrid mix chart; second system chart only if useful (text must match count)
