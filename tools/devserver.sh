#!/usr/bin/env bash
# Small helper used while developing: start/stop/restart the platform and keep
# the pid in a file so we never have to pattern-match process lists.
set -u
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PIDFILE="${ROOT}/data/devserver.pid"
LOGFILE="${TMPDIR:-/tmp}/blockhaven-dev.log"
cmd="${1:-start}"; shift || true

stop() {
  if [ -f "$PIDFILE" ]; then
    pid="$(cat "$PIDFILE")"
    if kill -0 "$pid" 2>/dev/null; then kill "$pid"; sleep 1; fi
    if kill -0 "$pid" 2>/dev/null; then kill -9 "$pid" 2>/dev/null; fi
    rm -f "$PIDFILE"
    echo "stopped $pid"
  else
    echo "not running"
  fi
}

start() {
  cd "$ROOT"
  nohup python3 main.py "$@" > "$LOGFILE" 2>&1 &
  echo $! > "$PIDFILE"
  sleep 3
  echo "started $(cat "$PIDFILE") -> $LOGFILE"
}

case "$cmd" in
  start) start "$@" ;;
  stop) stop ;;
  restart) stop; start "$@" ;;
  log) tail -n "${1:-40}" "$LOGFILE" ;;
  *) echo "usage: devserver.sh {start|stop|restart|log} [args]"; exit 1 ;;
esac
