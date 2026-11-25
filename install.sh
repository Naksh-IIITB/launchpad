#!/bin/sh
set -eu
cd "$(dirname "$0")"
python3 -m venv .venv
if [ -s requirements.txt ]; then
  .venv/bin/python -m pip install -r requirements.txt
fi
