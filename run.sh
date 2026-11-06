#!/usr/bin/env bash
# Startup script for BitChord Qobuz Addon Server

set -e

PORT="${PORT:-8080}"
HOST="${HOST:-0.0.0.0}"

echo "Starting BitChord Qobuz Source Addon..."
exec python3 server.py --host "$HOST" --port "$PORT" "$@"
