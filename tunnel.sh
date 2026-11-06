#!/usr/bin/env bash
# Starts the BitChord Qobuz Addon and exposes it via a free Cloudflare HTTPS Tunnel

set -e

PORT="${PORT:-8080}"

echo "================================================================"
echo "  🎵 BitChord Qobuz Addon + Cloudflare HTTPS Tunnel"
echo "================================================================"

# Check if cloudflared is installed
if ! command -v cloudflared &> /dev/null; then
    echo "❌ Error: 'cloudflared' is not installed."
    echo "Install it via: brew install cloudflared"
    exit 1
fi

# Start python addon server in background
python3 server.py --port "$PORT" &
SERVER_PID=$!

# Ensure server stops when script exits
trap "kill $SERVER_PID 2>/dev/null || true; exit" SIGINT SIGTERM EXIT

sleep 1

echo ""
echo "🚀 Starting Cloudflare Tunnel..."
echo "Watch for your public HTTPS URL ending in .trycloudflare.com below:"
echo "Append /manifest.json to that URL and paste into BitChord!"
echo "----------------------------------------------------------------"

cloudflared tunnel --url "http://localhost:${PORT}"

