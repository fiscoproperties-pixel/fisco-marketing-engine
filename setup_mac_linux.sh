#!/usr/bin/env bash
set -e
python3 -m pip install -r requirements.txt
python3 -m playwright install chromium
echo "Setup complete."
