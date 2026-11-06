#!/usr/bin/env bash
# Draft30 R6 study reruns — Mac owner bc-c3926f51.
# Package: R6c_caution_cap090. NO paper edits here (cloud owns latex).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"
if [[ -f .venv/bin/activate ]]; then
  # shellcheck disable=SC1091
  source .venv/bin/activate
fi
export TF_CPP_MIN_LOG_LEVEL=2 PYTHONUNBUFFERED=1 ALLOW_TRAIN4=1
export SETUPTOOLS_USE_DISTUTILS=local

MODEL=saved_model_R6c_caution_cap090
OUT=logs/overnight_improve/train4/studies_R6c_draft30
STUDIES=studies/draft30_r6
CSV_PREF=data/ingested_extended/extended_training_window_B_ready.csv
CSV_FALLBACK=data/ingested_extended/train7_training_locked_y_ext_drivers.csv
if [[ -f "$CSV_PREF" ]]; then CSV="$CSV_PREF"; else CSV="$CSV_FALLBACK"; fi
echo "CSV=$CSV MODEL=$MODEL OUT=$OUT"

bash scripts/draft30_r6/pack_R6c_model_dir.sh \
  papers/appendix_numerical_tables/locked_saved_model "$MODEL"

mkdir -p "$OUT" "$STUDIES/window_grid" "$STUDIES/figures" "$STUDIES/mission_sim" "$STUDIES/ablation"

echo "=== Window A summer grid (pick best ≥~90d where data allows) ==="
python scripts/draft30_r6/select_windows_and_run.py \
  --csv "$CSV" --model-dir "$MODEL" --out-root "$OUT" \
  --studies-dir "$STUDIES"

echo "=== Mission sim ==="
python scripts/run_mission_sim_radiation_eva.py \
  --model-dir "$MODEL" \
  --out-dir "$OUT/mission_sim" \
  2>&1 | tee "$OUT/mission_sim_run.log"
cp -R "$OUT/mission_sim/." "$STUDIES/mission_sim/" 2>/dev/null || true

echo "=== Ablation (use chosen Window A span from selection json) ==="
A_START=$(python -c "import json;print(json.load(open('$STUDIES/SELECTED_WINDOWS.json'))['A']['start'])")
A_END=$(python -c "import json;print(json.load(open('$STUDIES/SELECTED_WINDOWS.json'))['A']['end'])")
# Ablation uses a quieter mid-window fortnight if A is long
python scripts/run_hazard_ablation_study.py \
  --csv "$CSV" --model-dir "$MODEL" \
  --start "${ABLATION_START:-2026-06-17}" --end "${ABLATION_END:-2026-06-30}" \
  --out-dir "$OUT/ablation" \
  2>&1 | tee "$OUT/ablation_run.log" || true
cp -R "$OUT/ablation/." "$STUDIES/ablation/" 2>/dev/null || true

echo "=== Build draft30 figures ==="
python scripts/draft30_r6/build_draft30_figures.py \
  --studies-dir "$STUDIES" --out-dir "$STUDIES/figures" \
  --model-dir "$MODEL" --csv "$CSV"

echo "=== READY_FOR_PAPER summary ==="
python - <<PY
import json
from pathlib import Path
s = Path('$STUDIES')
sel = json.loads((s/'SELECTED_WINDOWS.json').read_text())
payload = {
  'status': 'READY_FOR_DRAFT30_R6',
  'package': 'R6c_caution_cap090',
  'selected': sel,
  'paths': {
    'A': sel['A'].get('out_dir'),
    'B': sel['B'].get('out_dir'),
    'figures': str(s/'figures'),
    'mission': str(s/'mission_sim'),
    'ablation': str(s/'ablation'),
  },
}
(s/'READY_FOR_DRAFT30_R6.json').write_text(json.dumps(payload, indent=2))
(s/'READY_FOR_DRAFT30_R6.md').write_text(
  '# READY_FOR_DRAFT30_R6\n\n'
  f"- Package: R6c_caution_cap090\n"
  f"- Window A: {sel['A']['start']} → {sel['A']['end']} wins={sel['A'].get('wins')}\n"
  f"- Window B: {sel['B']['start']} → {sel['B']['end']} wins={sel['B'].get('wins')}\n"
  f"- Figures: studies/draft30_r6/figures/\n"
  f"- Mission/ablation under studies/draft30_r6/\n"
  f"- NO rewrite; cloud patches draft30 latex from these artifacts.\n"
)
print(json.dumps(payload, indent=2))
PY

echo "DONE — push studies/draft30_r6 READY_FOR_DRAFT30_R6* + figures + summaries"
