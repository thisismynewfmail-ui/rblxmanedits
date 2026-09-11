#!/usr/bin/env bash
# BLOCKHAVEN launcher.
#
# Starts the platform with the live terminal read-out: a status block every
# few seconds showing traffic, accounts, worlds and host processes instead of
# a single banner that goes quiet.  Extra arguments are passed straight
# through to main.py, so the usual flags still work:
#
#   ./run.sh                     normal start
#   ./run.sh --port 9000         somewhere else
#   ./run.sh --no-games          website only
#   ./run.sh --reset             wipe the database and re-seed
#   ./run.sh --status-interval 3 refresh the read-out faster (0 = off)
#
# Environment:
#   BLOCKHAVEN_STATUS_INTERVAL   default refresh in seconds (default 10)
#   NO_COLOR                     set to anything to drop the ANSI colours
set -uo pipefail

cd "$(dirname "$0")" || exit 1

PYTHON="${PYTHON:-python3}"
if ! command -v "$PYTHON" >/dev/null 2>&1; then
  echo "run.sh: $PYTHON is not on PATH -- BLOCKHAVEN needs Python 3.9 or newer." >&2
  exit 1
fi

VERSION="$("$PYTHON" -c 'import sys; print("%d.%d" % sys.version_info[:2])' 2>/dev/null || echo "?")"
if ! "$PYTHON" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 9) else 1)'; then
  echo "run.sh: Python $VERSION found, but 3.9 or newer is required." >&2
  exit 1
fi

INTERVAL="${BLOCKHAVEN_STATUS_INTERVAL:-10}"

# Only supply the default interval when the caller has not chosen one.
HAS_INTERVAL=0
for arg in "$@"; do
  case "$arg" in
    --status-interval|--status-interval=*) HAS_INTERVAL=1 ;;
  esac
done

# A quick summary of what is about to happen, before the seeding output
# scrolls past.
COLS="$(tput cols 2>/dev/null || echo 80)"
printf '%*s\n' "$COLS" '' | tr ' ' '='
echo "  BLOCKHAVEN launcher"
echo "  python      $PYTHON ($VERSION)"
echo "  workdir     $(pwd)"
if [ -f data/blockhaven.sqlite3 ]; then
  SIZE="$(du -h data/blockhaven.sqlite3 2>/dev/null | cut -f1)"
  echo "  database    data/blockhaven.sqlite3 (${SIZE:-?})"
else
  echo "  database    will be created and seeded on this run"
fi
if [ "$HAS_INTERVAL" -eq 0 ]; then
  echo "  status      refreshing every ${INTERVAL}s"
fi
echo "  arguments   ${*:-(none)}"
printf '%*s\n' "$COLS" '' | tr ' ' '='
echo

if [ "$HAS_INTERVAL" -eq 0 ]; then
  exec "$PYTHON" main.py --status-interval "$INTERVAL" "$@"
fi
exec "$PYTHON" main.py "$@"
