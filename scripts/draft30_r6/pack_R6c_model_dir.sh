#!/usr/bin/env bash
# Pack READY_R6 R6c_caution_cap090 into a local model dir (keras from train-2 lock).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"
SRC="${1:-papers/appendix_numerical_tables/locked_saved_model}"
DST="${2:-saved_model_R6c_caution_cap090}"
PKG=studies/draft30_r6/R6c_package
mkdir -p "$DST"
for f in model.keras best.keras scaler.npz meta.json calibration.npz capability.json; do
  if [[ -f "$SRC/$f" ]]; then cp -f "$SRC/$f" "$DST/$f"; fi
done
cp -f "$PKG/archive_priors.json" "$DST/archive_priors.json"
cp -f "$PKG/serve_config_locked.json" "$DST/serve_config_locked.json"
python - <<PY
import json, numpy as np
from pathlib import Path
pkg = Path("$PKG")
dst = Path("$DST")
serve = json.loads((pkg / "serve_config_locked.json").read_text())
blend = serve["blend_weights"]["values"]
np.save(dst / "blend_weights.npy", np.asarray(blend, float))
print("blend", blend)
PY
echo "Packed $DST from $SRC + $PKG"
