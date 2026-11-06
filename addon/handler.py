"""
BitChord Addon HTTP Request Handler.
Implements the BitChord Addon Protocol, Audio Streaming, and Web Setup APIs.
"""

import os
import re
import json
import socket
import logging
import urllib.parse
from http.server import BaseHTTPRequestHandler
from typing import Dict, Any, Optional, List

from .manifest import get_addon_manifest
from .stream_proxy import StreamProxy
from qobuz.client import QobuzClient, QobuzAPIError
from qobuz.models import QobuzTrack, FormatId
from qobuz.matcher import TrackMatcher

logger = logging.getLogger("bitchord.addon.handler")


def clean_query(text: str) -> str:
    """Strip YouTube junk like '(Official Video)', '[HD]', etc."""
    junk_patterns = [
        r"\(official\s+video\)",
        r"\(official\s+audio\)",
        r"\(official\s+music\s+video\)",
        r"\[official\s+video\]",
        r"\[official\s+audio\]",
        r"\(lyric\s+video\)",
        r"\(lyrics\)",
        r"\[lyrics\]",
        r"\(audio\)",
        r"\[audio\]",
        r"\(hd\)",
        r"\[hd\]",
        r"\(4k\)",
        r"\[4k\]",
    ]
    cleaned = text
    for pattern in junk_patterns:
        cleaned = re.sub(pattern, "", cleaned, flags=re.IGNORECASE)
    return " ".join(cleaned.split()).strip()


def get_local_ip() -> str:
    """Find local network IP address for LAN access."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
    except Exception:
        ip = "127.0.0.1"
    finally:
        s.close()
    return ip


class BitChordAddonHandler(BaseHTTPRequestHandler):
    """
    HTTP Request Handler serving BitChord Addon endpoints and Web Setup UI.
    """

    client: QobuzClient = None  # Injected by server
    static_dir: str = ""
    config_file_path: str = ""
    direct_redirect: bool = False

    def get_base_url(self) -> str:
        """Determines server base URL from Host header."""
        host = self.headers.get("Host") or f"{get_local_ip()}:8080"
        proto = "https" if self.headers.get("X-Forwarded-Proto") == "https" else "http"
        return f"{proto}://{host}"

    def send_json(self, data: Any, status: int = 200):
        """Helper to send JSON response with CORS headers."""
        payload = json.dumps(data, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS, HEAD")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Range, Authorization")
        self.end_headers()
        self.wfile.write(payload)

    def do_OPTIONS(self):
        """Handle CORS pre-flight requests."""
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS, HEAD")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Range, Authorization")
        self.end_headers()

    def do_HEAD(self):
        """Handle HEAD requests (used by ExoPlayer to probe audio length)."""
        parsed_url = urllib.parse.urlparse(self.path)
        path = parsed_url.path

        # Check for /audio/{id}.flac or /stream/{id}
        audio_match = re.match(r"^/audio/([^/]+?)(?:\.flac)?$", path)
        stream_match = re.match(r"^/stream/([^/]+)$", path)

        track_id = None
        if audio_match:
            track_id = audio_match.group(1)
        elif stream_match:
            track_id = stream_match.group(1)

        if track_id:
            try:
                stream_info = self.client.get_file_url(track_id)
                StreamProxy.proxy_stream(
                    remote_url=stream_info.url,
                    request_headers=dict(self.headers),
                    client_handler=self,
                    is_head_request=True,
                )
                return
            except Exception as e:
                logger.error("HEAD request failed for %s: %s", track_id, e)
                self.send_response(404)
                self.end_headers()
                return

        self.send_response(404)
        self.end_headers()

    def do_GET(self):
        """Handle GET requests."""
        parsed_url = urllib.parse.urlparse(self.path)
        path = parsed_url.path
        query = urllib.parse.parse_qs(parsed_url.query)

        # 1. Manifest
        if path in ("/manifest.json", "/manifest"):
            manifest = get_addon_manifest(self.get_base_url())
            self.send_json(manifest)
            return

        # 2. Health check
        if path in ("/health", "/healthz", "/status"):
            self.send_json({
                "status": "ok",
                "service": "bitchord-qobuz-addon",
                "version": "1.0.0",
                "app_id": self.client.app_id,
                "has_user_token": bool(self.client.user_auth_token),
                "preferred_format": self.client.preferred_format,
            })
            return

        # 3. BitChord Catalogue Search (/search?q=...)
        if path == "/search":
            self.handle_search(query)
            return

        # 4. Stream Resolution (/stream/{id})
        stream_match = re.match(r"^/stream/([^/]+)$", path)
        if stream_match:
            track_id = stream_match.group(1)
            self.handle_stream(track_id, query)
            return

        # 5. Audio Media Delivery (/audio/{id}.flac or /audio/{id})
        audio_match = re.match(r"^/audio/([^/]+?)(?:\.flac)?$", path)
        if audio_match:
            track_id = audio_match.group(1)
            self.handle_audio(track_id)
            return

        # 6. Web UI Status & Test APIs
        if path == "/api/status":
            self.handle_api_status()
            return

        if path == "/api/test-search":
            q_val = query.get("q", [""])[0]
            tracks = self.client.search(q_val, limit=10)
            base_url = self.get_base_url()
            self.send_json({
                "query": q_val,
                "count": len(tracks),
                "tracks": [t.to_bitchord_dict(base_url) for t in tracks],
            })
            return

        # 7. Static Assets & Root Setup UI
        if path in ("/", "/setup", "/index.html"):
            self.serve_static_file("index.html", "text/html")
            return

        if path.startswith("/static/"):
            filename = path.replace("/static/", "").strip("/")
            self.serve_static_asset(filename)
            return

        # 404 Not Found
        self.send_json({"error": "Endpoint not found", "path": path}, status=404)

    def do_POST(self):
        """Handle POST requests for Web UI configuration."""
        parsed_url = urllib.parse.urlparse(self.path)
        path = parsed_url.path

        if path == "/api/config":
            self.handle_api_config_save()
            return

        if path == "/api/test-login":
            self.handle_api_test_login()
            return

        self.send_json({"error": "Endpoint not found"}, status=404)

    # -------------------------------------------------------------
    # BitChord Search & Stream Logic
    # -------------------------------------------------------------

    def handle_search(self, query: Dict[str, List[str]]):
        """Handle BitChord GET /search?q=..."""
        raw_q = query.get("q", [""])[0]
        title_param = query.get("title", [""])[0]
        artist_param = query.get("artist", [""])[0]
        duration_param = query.get("duration", ["0"])[0]

        target_duration = int(duration_param) if duration_param.isdigit() else 0

        # Build effective query
        if title_param and artist_param:
            search_query = f"{title_param} {artist_param}"
        elif raw_q:
            search_query = clean_query(raw_q)
        else:
            search_query = ""

        if not search_query:
            self.send_json({"tracks": []})
            return

        logger.info("BitChord search query: '%s' (duration=%d)", search_query, target_duration)

        try:
            tracks = self.client.search(search_query, limit=10)
        except Exception as e:
            logger.error("Search failed for '%s': %s", search_query, e)
            self.send_json({"tracks": []})
            return

        # Score & rank tracks using intelligent fuzzy matching and duration tolerance
        tracks = TrackMatcher.match_and_rank(
            tracks,
            raw_query=search_query,
            query_title=title_param,
            query_artist=artist_param,
            expected_duration=target_duration,
        )

        base_url = self.get_base_url()
        bitchord_tracks = [t.to_bitchord_dict(base_url) for t in tracks]

        self.send_json({"tracks": bitchord_tracks})

    def handle_stream(self, track_id: str, query: Dict[str, List[str]]):
        """
        Handle BitChord GET /stream/{id}.
        If client asks for audio directly or has Range header, stream directly!
        Otherwise, return BitChord stream JSON descriptor.
        """
        accept_header = self.headers.get("Accept", "").lower()
        has_range = bool(self.headers.get("Range"))
        is_media_req = "audio/" in accept_header or query.get("media", ["false"])[0] == "true"

        # If direct audio stream requested
        if is_media_req or has_range:
            self.handle_audio(track_id)
            return

        try:
            stream_info = self.client.get_file_url(track_id)
        except QobuzAPIError as e:
            logger.error("Stream resolution failed for track %s: %s", track_id, e)
            self.send_json({"error": f"Track not found: {e}"}, status=404)
            return
        except Exception as e:
            logger.error("Unexpected error resolving stream for track %s: %s", track_id, e)
            self.send_json({"error": str(e)}, status=500)
            return

        base_url = self.get_base_url()

        # If direct_redirect mode is enabled, supply the direct Qobuz CDN URL
        if self.direct_redirect and stream_info.url:
            resolved_url = stream_info.url
        else:
            resolved_url = f"{base_url}/audio/{track_id}.flac"

        response_payload = {
            "url": resolved_url,
            "format": stream_info.format,
            "audioQuality": stream_info.audio_quality,
            "bitDepth": stream_info.bit_depth,
            "sampleRate": stream_info.sample_rate,
            "bitrate": stream_info.bitrate,
            "duration": stream_info.duration,
        }

        self.send_json(response_payload)

    def handle_audio(self, track_id: str):
        """Proxy direct audio stream with HTTP 206 Range support."""
        try:
            stream_info = self.client.get_file_url(track_id)
        except QobuzAPIError as e:
            logger.error("Audio fetch failed for track %s: %s", track_id, e)
            self.send_json({"error": f"Track stream unavailable: {e}"}, status=404)
            return
        except Exception as e:
            logger.error("Audio error for track %s: %s", track_id, e)
            self.send_json({"error": str(e)}, status=500)
            return

        if self.direct_redirect and stream_info.url:
            self.send_response(302)
            self.send_header("Location", stream_info.url)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            return

        StreamProxy.proxy_stream(
            remote_url=stream_info.url,
            request_headers=dict(self.headers),
            client_handler=self,
            is_head_request=False,
        )

    # -------------------------------------------------------------
    # Web Setup & Management UI Handlers
    # -------------------------------------------------------------

    def handle_api_status(self):
        """Return system status and network endpoints for Web UI."""
        local_ip = get_local_ip()
        base_url = self.get_base_url()
        lan_url = f"http://{local_ip}:8080"

        auth_status = self.client.verify_auth()

        masked_token = None
        if self.client.user_auth_token:
            t = self.client.user_auth_token
            masked_token = f"{t[:4]}...{t[-4:]}" if len(t) > 8 else "***"

        self.send_json({
            "service": "BitChord Qobuz Source Addon",
            "version": "1.0.0",
            "app_id": self.client.app_id,
            "user_token_configured": bool(self.client.user_auth_token),
            "masked_token": masked_token,
            "auth": auth_status,
            "preferred_format": self.client.preferred_format,
            "direct_redirect": self.direct_redirect,
            "network": {
                "current_url": base_url,
                "lan_manifest_url": f"{lan_url}/manifest.json",
                "lan_root_url": lan_url,
                "local_ip": local_ip,
            },
        })

    def handle_api_config_save(self):
        """Save updated credentials from Web UI."""
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length).decode("utf-8")
        try:
            data = json.loads(body)
        except Exception:
            self.send_json({"error": "Invalid JSON"}, status=400)
            return

        app_id = data.get("app_id")
        app_secret = data.get("app_secret")
        user_auth_token = data.get("user_auth_token")
        preferred_format = data.get("preferred_format")
        direct_redirect = data.get("direct_redirect")

        if preferred_format is not None:
            try:
                preferred_format = int(preferred_format)
            except ValueError:
                preferred_format = None

        if direct_redirect is not None:
            self.direct_redirect = bool(direct_redirect)

        self.client.update_credentials(
            app_id=app_id if app_id else None,
            app_secret=app_secret if app_secret else None,
            user_auth_token=user_auth_token,
            preferred_format=preferred_format,
        )

        # Save to config file if path configured
        if self.config_file_path:
            try:
                config_data = {
                    "app_id": self.client._app_id,
                    "app_secret": self.client._app_secret,
                    "user_auth_token": self.client.user_auth_token,
                    "preferred_format": self.client.preferred_format,
                    "direct_redirect": self.direct_redirect,
                }
                with open(self.config_file_path, "w", encoding="utf-8") as f:
                    json.dump(config_data, f, indent=2)
                logger.info("Saved configuration to %s", self.config_file_path)
            except Exception as e:
                logger.warning("Failed to persist config file: %s", e)

        auth_res = self.client.verify_auth()
        self.send_json({
            "status": "success",
            "message": "Configuration updated successfully",
            "auth": auth_res,
        })

    def handle_api_test_login(self):
        """Attempt login with email & password and return token."""
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length).decode("utf-8")
        try:
            data = json.loads(body)
        except Exception:
            self.send_json({"error": "Invalid JSON"}, status=400)
            return

        email = data.get("email")
        password = data.get("password")

        if not email or not password:
            self.send_json({"error": "Email and password are required"}, status=400)
            return

        try:
            res = self.client.login(username=email, password=password)
            self.send_json({
                "status": "success",
                "message": "Login successful",
                "user_auth_token": self.client.user_auth_token,
                "user": res.get("user"),
            })
        except Exception as e:
            logger.error("Login failed: %s", e)
            self.send_json({"error": str(e)}, status=401)

    # -------------------------------------------------------------
    # Static Files Serving
    # -------------------------------------------------------------

    def serve_static_file(self, filename: str, content_type: str):
        filepath = os.path.join(self.static_dir, filename)
        if not os.path.exists(filepath):
            self.send_json({"error": "File not found"}, status=404)
            return

        with open(filepath, "rb") as f:
            content = f.read()

        self.send_response(200)
        self.send_header("Content-Type", f"{content_type}; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(content)

    def serve_static_asset(self, filename: str):
        # Disallow directory traversal
        clean_name = os.path.basename(filename)
        filepath = os.path.join(self.static_dir, clean_name)
        if not os.path.exists(filepath):
            self.send_json({"error": "Asset not found"}, status=404)
            return

        mime_types = {
            ".css": "text/css",
            ".js": "application/javascript",
            ".svg": "image/svg+xml",
            ".png": "image/png",
            ".ico": "image/x-icon",
            ".html": "text/html",
        }
        ext = os.path.splitext(clean_name)[1].lower()
        ctype = mime_types.get(ext, "application/octet-stream")

        with open(filepath, "rb") as f:
            content = f.read()

        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "public, max-age=3600")
        self.end_headers()
        self.wfile.write(content)

