#!/bin/sh
set -eu
cd "$(dirname "$0")"
python_bin=${PYTHON:-python3}
"$python_bin" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)' || {
  echo 'Use Python 3.11 or newer. For example, run PYTHON=python3.11 sh install.sh.' >&2
  exit 1
}
"$python_bin" -m venv .venv
if [ -s requirements.txt ]; then
  .venv/bin/python -m pip install -r requirements.txt
fi
