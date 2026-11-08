#!/bin/zsh
set -euo pipefail
cd /Users/lukatakki/Documents/GitHub/LIPAS
source .venv/bin/activate
export ALLOW_TRAIN4=1
export TF_CPP_MIN_LOG_LEVEL=2
export PYTHONUNBUFFERED=1
export SETUPTOOLS_USE_DISTUTILS=local
LEDGER=logs/overnight_improve/train4/ledger.md
logrow() { printf '| %s | %s\n' "$(date -u +%Y-%m-%dT%H:%MZ)" "$1" >> "$LEDGER"; }

# Deps first, then pin setuptools LAST (TF 2.16 needs distutils)
pip install -q flask flask-cors python-dotenv reportlab beautifulsoup4 lxml
pip install -q --force-reinstall 'setuptools==69.5.1'
python -c "import distutils, tensorflow as tf; print('preflight TF', tf.__version__, tf.config.list_physical_devices('GPU'))"

logrow "T4a START Mac Metal (80 ep) after deps fix | Y | pending | - | - | - | - | running | wait held-out |"
python scripts/train4_kaggle.py --stage t4a 2>&1 | tee logs/overnight_improve/train4/t4a_run.log
RMSE=$(python -c "import json; print(json.load(open('saved_model_train4a/train4_gate.json')).get('test_rmse','?'))" 2>/dev/null || echo '?')
BEAT=$(python -c "import json; print(json.load(open('saved_model_train4a/train4_gate.json')).get('beats_train2',False))" 2>/dev/null || echo False)
logrow "T4a DONE test_rmse=${RMSE} beats_train2=${BEAT} | Y | ${RMSE} | - | - | - | - | $([[ "$BEAT" == "True" ]] && echo keep || echo discard) | $([[ "$BEAT" == "True" ]] && echo window+blend || echo T4b residual) |"

if [[ "$BEAT" != "True" ]]; then
  logrow "T4b START residual solar+rad | Y | pending | - | - | - | - | running | |"
  python scripts/train4_kaggle.py --stage t4b 2>&1 | tee logs/overnight_improve/train4/t4b_run.log
  RMSE=$(python -c "import json; print(json.load(open('saved_model_train4b/train4_gate.json')).get('test_rmse','?'))" 2>/dev/null || echo '?')
  BEAT=$(python -c "import json; print(json.load(open('saved_model_train4b/train4_gate.json')).get('beats_train2',False))" 2>/dev/null || echo False)
  logrow "T4b DONE test_rmse=${RMSE} beats_train2=${BEAT} | Y | ${RMSE} | - | - | - | - | $([[ "$BEAT" == "True" ]] && echo keep || echo discard) | $([[ "$BEAT" == "True" ]] && echo window+blend || echo T4c capacity) |"
fi

if [[ "$BEAT" != "True" ]]; then
  logrow "T4c START capacity | Y | pending | - | - | - | - | running | |"
  python scripts/train4_kaggle.py --stage t4c 2>&1 | tee logs/overnight_improve/train4/t4c_run.log
  RMSE=$(python -c "import json; print(json.load(open('saved_model_train4c/train4_gate.json')).get('test_rmse','?'))" 2>/dev/null || echo '?')
  BEAT=$(python -c "import json; print(json.load(open('saved_model_train4c/train4_gate.json')).get('beats_train2',False))" 2>/dev/null || echo False)
  logrow "T4c DONE test_rmse=${RMSE} beats_train2=${BEAT} | Y | ${RMSE} | - | - | - | - | $([[ "$BEAT" == "True" ]] && echo keep || echo discard) | autopsy if miss |"
fi

echo LADDER_COMPLETE beat=$BEAT rmse=$RMSE | tee logs/overnight_improve/train4/ladder_done.txt
