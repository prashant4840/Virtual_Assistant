#!/usr/bin/env bash
set -euo pipefail

PY_BIN="${PY_BIN:-python3}"
VENV_DIR="${VENV_DIR:-.venv}"
RUN_AFTER_SETUP="${RUN_AFTER_SETUP:-1}"

echo ">> Using Python: ${PY_BIN}"
echo ">> Creating virtual environment at: ${VENV_DIR}"
"${PY_BIN}" -m venv "${VENV_DIR}"

if [[ ! -f "${VENV_DIR}/bin/activate" ]]; then
  echo "Virtual environment activation script not found."
  exit 1
fi

# shellcheck disable=SC1090
source "${VENV_DIR}/bin/activate"

echo ">> Upgrading pip/setuptools/wheel"
python -m pip install --upgrade pip setuptools wheel

echo ">> Installing pinned dependencies"
pip install -r requirements.txt

echo ">> Setup complete."
echo ">> To activate later: source ${VENV_DIR}/bin/activate"

if [[ "${RUN_AFTER_SETUP}" == "1" ]]; then
  echo ">> Launching app..."
  python main.py
else
  echo ">> Skipping run (RUN_AFTER_SETUP=${RUN_AFTER_SETUP})"
fi
