#!/usr/bin/env bash
# Convenience launcher: python3 main.py with any extra arguments passed through.
cd "$(dirname "$0")" || exit 1
exec python3 main.py "$@"
