#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
if [[ ! -x .venv/bin/python ]]; then
  python3 -m venv .venv
fi
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
export ADC_BACKEND_DB="${ADC_BACKEND_DB:-$(pwd)/adc_backend.sqlite3}"
exec python -m uvicorn main:app --host 127.0.0.1 --port 8000
