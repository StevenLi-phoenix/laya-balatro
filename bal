#!/usr/bin/env bash
# Balatro CLI wrapper: cd + utf-8 handled. Usage: ./bal show | play 0 1 | do 2 "Buy X" | new deck=b_red stake=1 model=haiku effort=high | report [model]
cd "$(dirname "$0")" && PYTHONIOENCODING=utf-8 exec .venv/Scripts/python.exe -m laya_player.claude_cli "$@"
