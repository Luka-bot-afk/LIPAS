#!/usr/bin/env bash
# Pack a flat Kaggle dataset for LIPAS Train4 GO-NIGHT.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="${1:-/tmp/kaggle_pack_train4}"
CSV_SRC="${CSV_SRC:-$ROOT/data/ingested_extended/train7_training_locked_y_ext_drivers.csv}"
if [[ ! -f "$CSV_SRC" ]]; then
  echo "Missing CSV: $CSV_SRC" >&2
  exit 1
fi
rm -rf "$OUT"
mkdir -p "$OUT"

copy() { cp -a "$1" "$OUT/$2"; }

copy "$ROOT/training_pipeline.py" training_pipeline.py
copy "$ROOT/space_weather_model.py" space_weather_model.py
copy "$ROOT/data_ingestion.py" data_ingestion.py
copy "$ROOT/lunar_physics.py" lunar_physics.py
copy "$ROOT/lunar_sites.py" lunar_sites.py
copy "$ROOT/models.py" models.py
copy "$ROOT/gap_fill.py" gap_fill.py
copy "$ROOT/scripts/fit_blend_and_calibration.py" fit_blend_and_calibration.py
copy "$ROOT/scripts/evaluate.py" evaluate.py
copy "$ROOT/scripts/train4_kaggle.py" train4_kaggle.py
copy "$ROOT/configs/train4a.json" train4a.json
copy "$ROOT/configs/train4b.json" train4b.json
copy "$ROOT/configs/train4c.json" train4c.json
copy "$ROOT/configs/hybrid_blend_policy.json" hybrid_blend_policy.json
copy "$ROOT/requirements.txt" requirements.txt
copy "$CSV_SRC" train7_training_locked_y_ext_drivers.csv

# Locked train2 baseline for cheap checks / comparison meta
mkdir -p "$OUT/locked_saved_model"
cp -a "$ROOT/papers/appendix_numerical_tables/locked_saved_model/." "$OUT/locked_saved_model/"

cat > "$OUT/README_KAGGLE.txt" <<'EOF'
LIPAS Train4 GO-NIGHT flat pack.
CSV: train7_training_locked_y_ext_drivers.csv (locked train2 Y + external drivers)
Configs: train4a/b/c.json
Entrypoint: train4_kaggle.py
Gate: test_rmse < 4.9685; radiation ML blend > 0; no CPU fallback.
EOF

cat > "$OUT/dataset-metadata.json" <<EOF
{
  "title": "LIPAS Train4",
  "id": "lukatakki/lipas-train4",
  "licenses": [{"name": "CC0-1.0"}]
}
EOF

echo "Packed -> $OUT"
du -sh "$OUT"
ls -la "$OUT" | head -40
