# LIPAS conference poster (A0 portrait, LaTeX)

Portrait A0, exactly two columns. Sources live in this folder; compiled PDF is `main.pdf`.

## Build

```bash
cd poster
tectonic -X compile main.tex
```

Requires `fontspec` (XeTeX via Tectonic) and Liberation Sans.

## Assets

- `assets/` moon background, teal wave band, flowchart, and UI screenshots extracted from the prior poster art
- `figures/` locked draft30 R6c Window A/B charts, mission timeline, and hybrid mix chart

## Rules encoded in the source

- Abstract and Introduction match the prior poster PDF wording
- CubeSat callout removed
- New Methods / Results / Discussion prose avoids dashes (hyphenated compounds rephrased); URLs and preserved Abstract/Introduction text keep source spelling
