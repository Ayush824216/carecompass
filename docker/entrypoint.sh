#!/bin/sh
# First run on a fresh clone: build processed public data (if the raw files are mounted) and train Model A.
set -e
cd /app
if [ -d data/public ] && [ ! -f data/processed/public_train.jsonl ]; then
  echo "[entrypoint] preparing public data"; python scripts/prepare_public_data.py || echo "[entrypoint] public data prep skipped"
fi
if [ ! -f models/model_a.joblib ]; then
  echo "[entrypoint] training Model A"; python scripts/train.py
fi
if [ ! -f models/input_type.joblib ]; then
  echo "[entrypoint] training the input-type classifier"; python scripts/train_input_type.py || echo "[entrypoint] input-type training skipped (rules still work)"
fi
exec uvicorn app.main:app --app-dir backend --host 0.0.0.0 --port 8000 --workers ${WORKERS:-2}
