#!/usr/bin/env python3
"""
BitChord Qobuz Source Addon Server.
High-Quality Lossless and Hi-Res FLAC Streaming Source for BitChord App.
"""

import os
import sys
import json
import socket
import logging
import argparse
from http.server import ThreadingHTTPServer

from qobuz.client import QobuzClient
from qobuz.models import FormatId
from addon.handler import BitChordAddonHandler, get_local_ip

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("bitchord-addon")


def load_config(config_path: str) -> dict:
    if os.path.exists(config_path):
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.warning("Failed to load config file %s: %s", config_path, e)
    return {}


def main():
    parser = argparse.ArgumentParser(
        description="BitChord Qobuz Source Addon Server - High Quality FLAC Streaming"
    )
    parser.add_argument(
        "--host",
        default=os.environ.get("BITCHORD_HOST", "0.0.0.0"),
        help="Host address to bind (default: 0.0.0.0 for all interfaces)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.environ.get("BITCHORD_PORT", 8080)),
        help="Port to listen on (default: 8080)",
    )
    parser.add_argument(
        "--config",
        default=os.environ.get("BITCHORD_CONFIG", "config.json"),
        help="Path to config file (default: config.json)",
    )
    parser.add_argument(
        "--token",
        default=os.environ.get("QOBUZ_USER_TOKEN"),
        help="Qobuz User Auth Token (optional, can also be configured in Web UI)",
    )
    parser.add_argument(
        "--app-id",
        default=os.environ.get("QOBUZ_APP_ID"),
        help="Qobuz App ID (optional, defaults to web bundle app id)",
    )
    parser.add_argument(
        "--app-secret",
        default=os.environ.get("QOBUZ_APP_SECRET"),
        help="Qobuz App Secret (optional, defaults to bundle secrets)",
    )
    parser.add_argument(
        "--quality",
        type=int,
        default=int(os.environ.get("QOBUZ_QUALITY", FormatId.FLAC_24_192)),
        choices=[FormatId.MP3_320, FormatId.FLAC_16_44, FormatId.FLAC_24_96, FormatId.FLAC_24_192],
        help="Max audio quality: 27 (24b/192k), 7 (24b/96k), 6 (16b/44k), 5 (MP3 320k)",
    )
    parser.add_argument(
        "--direct-redirect",
        action="store_true",
        default=os.environ.get("BITCHORD_DIRECT_REDIRECT", "").lower() in ("true", "1", "yes"),
        help="Redirect client directly to Qobuz CDN instead of proxying FLAC chunks",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable debug logging",
    )

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Load file config if exists
    file_config = load_config(args.config)

    app_id = args.app_id or file_config.get("app_id")
    app_secret = args.app_secret or file_config.get("app_secret")
    user_token = args.token or file_config.get("user_auth_token")
    quality = file_config.get("preferred_format", args.quality)
    direct_redirect = file_config.get("direct_redirect", args.direct_redirect)

    # Initialize Qobuz Client
    client = QobuzClient(
        app_id=app_id,
        app_secret=app_secret,
        user_auth_token=user_token,
        preferred_format=quality,
    )

    # Configure Addon Handler
    current_dir = os.path.dirname(os.path.abspath(__file__))
    static_dir = os.path.join(current_dir, "static")

    BitChordAddonHandler.client = client
    BitChordAddonHandler.static_dir = static_dir
    BitChordAddonHandler.config_file_path = os.path.abspath(args.config)
    BitChordAddonHandler.direct_redirect = direct_redirect

    local_ip = get_local_ip()
    server_address = (args.host, args.port)

    try:
        httpd = ThreadingHTTPServer(server_address, BitChordAddonHandler)
    except OSError as e:
        logger.error("Could not bind to %s:%d: %s", args.host, args.port, e)
        sys.exit(1)

    print("=" * 64)
    print("  🎵 BitChord Qobuz Source Addon (High Quality FLAC Streaming)")
    print("=" * 64)
    print(f"  • Local Dashboard:     http://localhost:{args.port}/setup")
    print(f"  • Network Dashboard:   http://{local_ip}:{args.port}/setup")
    print(f"  • BitChord Source URL: http://{local_ip}:{args.port}/manifest.json")
    print("-" * 64)
    print(f"  • Max Format Quality:  {quality} (27=24/192 FLAC, 7=24/96, 6=16/44)")
    print(f"  • User Auth Token:     {'Configured' if user_token else 'Guest / 30s previews (configure in setup)'}")
    print(f"  • Streaming Mode:      {'Direct CDN Redirect' if direct_redirect else 'Chunked Audio Proxy (Range/Seek enabled)'}")
    print("=" * 64)
    print("  Ready for BitChord! Press Ctrl+C to stop.\n")

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down BitChord Qobuz Addon Server...")
    finally:
        httpd.server_close()


if __name__ == "__main__":
    main()

