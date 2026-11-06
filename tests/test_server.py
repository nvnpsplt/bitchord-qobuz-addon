"""
Unit tests for BitChordAddonHandler using in-memory streams.
Tests handler routes and responses without opening network sockets.
"""

import io
import json
import unittest
from unittest.mock import MagicMock

from addon.handler import BitChordAddonHandler
from qobuz.client import QobuzClient
from qobuz.models import QobuzTrack, StreamInfo


class MockClient(QobuzClient):
    def __init__(self):
        super().__init__(app_id="test_app_id", app_secret="test_secret_32_chars_123456789")

    def search(self, query: str, limit: int = 10, offset: int = 0):
        return [
            QobuzTrack(
                id="123456",
                title="Starboy",
                artist="The Weeknd",
                album="Starboy",
                duration=230,
                artwork_url="https://static.qobuz.com/starboy.jpg",
                hires=True,
                bit_depth=24,
                sample_rate=96.0,
            )
        ]

    def get_file_url(self, track_id: str, preferred_format: int = None, intent: str = "stream"):
        return StreamInfo(
            url="https://streaming.qobuz.com/sample.flac",
            format="flac",
            audio_quality="HI_RES",
            bit_depth=24,
            sample_rate=96000,
            bitrate=4608,
            duration=230,
        )


def execute_request(method: str, path: str, headers: dict = None, body: bytes = b"") -> tuple[int, dict, bytes]:
    """Execute a request against BitChordAddonHandler using in-memory byte streams."""
    BitChordAddonHandler.client = MockClient()
    BitChordAddonHandler.static_dir = "static"
    BitChordAddonHandler.config_file_path = ""
    BitChordAddonHandler.direct_redirect = False

    raw_headers = headers or {}
    if "Host" not in raw_headers:
        raw_headers["Host"] = "127.0.0.1:8080"

    header_lines = "".join(f"{k}: {v}\r\n" for k, v in raw_headers.items())
    request_data = f"{method} {path} HTTP/1.1\r\n{header_lines}\r\n".encode("utf-8") + body

    wfile = io.BytesIO()
    rfile = io.BytesIO(request_data)

    handler = BitChordAddonHandler.__new__(BitChordAddonHandler)
    handler.rfile = rfile
    handler.wfile = wfile
    handler.connection = MagicMock()
    handler.client_address = ("127.0.0.1", 54321)
    handler.server = MagicMock()
    handler.close_connection = True

    # Parse request
    handler.raw_requestline = rfile.readline()
    handler.parse_request()

    # Dispatch method
    if method == "GET":
        handler.do_GET()
    elif method == "POST":
        handler.do_POST()
    elif method == "OPTIONS":
        handler.do_OPTIONS()
    elif method == "HEAD":
        handler.do_HEAD()

    wfile.seek(0)
    raw_response = wfile.read()

    # Parse HTTP response
    resp_lines = raw_response.split(b"\r\n\r\n", 1)
    header_part = resp_lines[0].decode("utf-8", errors="ignore")
    body_part = resp_lines[1] if len(resp_lines) > 1 else b""

    status_line = header_part.splitlines()[0]
    status_code = int(status_line.split()[1])

    resp_headers = {}
    for line in header_part.splitlines()[1:]:
        if ":" in line:
            k, v = line.split(":", 1)
            resp_headers[k.strip().lower()] = v.strip()

    return status_code, resp_headers, body_part


class TestHandlerRoutes(unittest.TestCase):
    def test_manifest_endpoint(self):
        code, headers, body = execute_request("GET", "/manifest.json")
        self.assertEqual(code, 200)
        self.assertIn("application/json", headers.get("content-type", ""))
        data = json.loads(body.decode("utf-8"))
        self.assertEqual(data["id"], "org.bitchord.addon.qobuz")
        self.assertEqual(data["name"], "Qobuz FLAC")
        self.assertIn("search", data["resources"])
        self.assertIn("stream", data["resources"])
        self.assertIn("flac", data["formats"])

    def test_health_endpoint(self):
        code, headers, body = execute_request("GET", "/health")
        self.assertEqual(code, 200)
        data = json.loads(body.decode("utf-8"))
        self.assertEqual(data["status"], "ok")
        self.assertEqual(data["service"], "bitchord-qobuz-addon")

    def test_search_endpoint(self):
        code, headers, body = execute_request("GET", "/search?q=Starboy+The+Weeknd")
        self.assertEqual(code, 200)
        data = json.loads(body.decode("utf-8"))
        self.assertIn("tracks", data)
        self.assertEqual(len(data["tracks"]), 1)
        track = data["tracks"][0]
        self.assertEqual(track["id"], "123456")
        self.assertEqual(track["title"], "Starboy")
        self.assertEqual(track["audioQuality"], "HI_RES")
        self.assertEqual(track["format"], "flac")
        self.assertEqual(track["bitDepth"], 24)
        self.assertEqual(track["sampleRate"], 96000)

    def test_stream_json_descriptor(self):
        code, headers, body = execute_request("GET", "/stream/123456")
        self.assertEqual(code, 200)
        data = json.loads(body.decode("utf-8"))
        self.assertEqual(data["format"], "flac")
        self.assertEqual(data["audioQuality"], "HI_RES")
        self.assertEqual(data["bitDepth"], 24)
        self.assertEqual(data["sampleRate"], 96000)
        self.assertTrue(data["url"].endswith("/audio/123456.flac"))

    def test_cors_options(self):
        code, headers, _ = execute_request("OPTIONS", "/manifest.json")
        self.assertEqual(code, 204)
        self.assertEqual(headers.get("access-control-allow-origin"), "*")

    def test_404_endpoint(self):
        code, headers, body = execute_request("GET", "/non_existent_route")
        self.assertEqual(code, 404)


if __name__ == "__main__":
    unittest.main()
