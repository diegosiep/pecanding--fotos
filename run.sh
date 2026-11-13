#!/bin/sh
# Pecanding · fotos comestibles — launcher Linux/macOS
cd "$(dirname "$0")"
if [ -d .venv ]; then . .venv/bin/activate; fi
exec python3 -m app serve "$@"
