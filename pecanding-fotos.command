#!/bin/sh
# Doble clic en macOS: abre la app local en http://127.0.0.1:8765
cd "$(dirname "$0")"
if [ -d .venv ]; then . .venv/bin/activate; fi
python3 -m app serve &
sleep 1
open "http://127.0.0.1:8765" 2>/dev/null || xdg-open "http://127.0.0.1:8765"
