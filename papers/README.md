# Papers and study materials

Openable manuscript package for the LIPAS unified lunar forecasting work.

## Folders

| Path | What it is |
|------|------------|
| `elsevier/` | **Main editable LaTeX** (Elsevier `elsarticle`, Advances in Space Research style). Open `elsevier/main.tex` on Overleaf. |
| `elsevier/figures/` | Locked skill charts, prototype bars, architecture diagrams, mission timeline |
| `appendix_numerical_tables/` | RMSE tables, qualitative + quantitative frameworks, reported window numbers |
| `LIPAS_unified_lunar_forecasting_manuscript.pdf` | Older compiled full PDF (overlay-edited). Prefer the `elsevier/` LaTeX for new edits. |

## Study code (separate from paper prose)

Runners live in `../studies/` at the repo root (symlinks into `../scripts/`). Start at `../studies/README.md`.

## Compile the LaTeX

1. Upload or open `papers/elsevier/`
2. Set main file to `main.tex`
3. pdfLaTeX → BibTeX → pdfLaTeX → pdfLaTeX

Locked numbers that must match GitHub tables are listed again in `elsevier/README.md`.
