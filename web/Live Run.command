#!/bin/bash
# GRIDRUSH — live run: double-click this file. Starts the local server (no network) and opens
# http://127.0.0.1:8767/ in your browser. Close the Terminal window (or Ctrl+C) to stop it.
cd "$(dirname "$0")/.." || exit 1
echo "GRIDRUSH live run: http://127.0.0.1:8767/   (Ctrl+C to stop)"
python3 web/live_server.py
