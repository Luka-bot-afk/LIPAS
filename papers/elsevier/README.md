# LIPAS Elsevier / ASR preprint (elsarticle)

Editable **Advances in Space Research** preprint using Elsevier’s `elsarticle` class (`preprint,12pt,authoryear`).

## Compile (Overleaf recommended)

1. Upload this `elsevier/` folder to Overleaf (or clone the repo and open `papers/elsevier`).
2. Set the main document to `main.tex`.
3. Ensure the Overleaf TeX Live image includes `elsarticle` (default).
4. Compile: **pdfLaTeX → BibTeX → pdfLaTeX → pdfLaTeX**.

Locally (if TeX is installed):

```bash
cd papers/elsevier
pdflatex main.tex && bibtex main && pdflatex main.tex && pdflatex main.tex
```

## Locked-model numbers (must match GitHub tables)

| Window | Solar H/F | Radiation H/F |
|--------|-----------|---------------|
| A (night-dominant) | 4.10 / 4.66 | **0.119 / 0.102** (replica better) |
| B (quiet dayside) | 4.99 / 5.99 | **0.0188 / 0.00266** (replica better) |

Skill charts in `figures/fig_windowA_skill.png` and `fig_windowB_skill.png` are regenerated from `logs/study_14day_window_*/summary.json`. Location key is below the axes (does not overlap bars). Skill is scaled **within** each hazard only.

## Notes for ASR submission

- Replace affiliation placeholder in `main.tex` before submission.
- Expand methods/system sections from the full manuscript PDF if the journal requests more detail; this package prioritizes corrected Results / Discussion / Conclusion aligned with locked-model outputs.
- Full PDF with appendices: `papers/LIPAS_unified_lunar_forecasting_manuscript.pdf` on GitHub.
