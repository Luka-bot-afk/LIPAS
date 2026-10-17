# LIPAS Elsevier / ASR preprint (elsarticle)

Editable Advances in Space Research preprint using Elsevier `elsarticle` (`preprint,12pt,authoryear`).

## Compile (Overleaf recommended)

1. Open this `elsevier/` folder (or the parent `papers/` tree) on Overleaf.
2. Set the main document to `main.tex`.
3. Compile: pdfLaTeX → BibTeX → pdfLaTeX → pdfLaTeX.

Locally (if TeX is installed):

```bash
cd papers/elsevier
pdflatex main.tex && bibtex main && pdflatex main.tex && pdflatex main.tex
```

## Locked-model numbers (must match appendix tables)

| Window | Solar H / replica | Radiation H / replica |
|--------|-------------------|------------------------|
| A (night-dominant) | 4.10 / 4.66 | 0.119 / 0.102 (replica better) |
| B (quiet dayside) | 4.99 / 5.99 | 0.0188 / 0.00266 (replica better) |

Blend: `[0.4, 0.05, 0, 0, 0, 0]` in order solar, radiation, temperature, moonquakes, micrometeorites, dust.

Skill charts: `figures/fig_windowA_skill.png`, `figures/fig_windowB_skill.png`. Location key sits below the axes. Skill is scaled within each hazard only. No “skill scaled …” footer text inside the PNGs.

## Figure checklist

| File | Role |
|------|------|
| `fig_architecture_data_path.png` | 18-feature data path |
| `fig_architecture_blend.png` | Locked blend |
| `fig_prototype_lipas_vs_flagship.png` | Prototype two-bar mean skill |
| `fig_lipas_vs_diviner.png` | Prototype temperature vs Diviner-class |
| `fig_windowA_skill.png` / `fig_windowB_skill.png` | Locked windows |
| `fig_mission_timeline.png` | Mission sim (red legend) |

## Related folders

- Numeric / qualitative appendix markdown: `../appendix_numerical_tables/`
- Study runners: `../../studies/`
