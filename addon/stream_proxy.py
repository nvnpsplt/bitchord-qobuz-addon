"""
Audio streaming proxy for BitChord ExoPlayer.
Handles HTTP Range requests (206 Partial Content), HEAD pre-probes, and chunked streaming.
"""

import urllib.request
import urllib.error
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger("bitchord.addon.proxy")
CHUNK_SIZE = 64 * 1024  # 64 KB chunks for low-latency FLAC streaming


class StreamProxy:
    """
    Proxies media streams from Qobuz CDN directly to BitChord.
    Ensures seamless seeking, range requests, and correct audio headers.
    """

    USER_AGENT = "BitChord/1.0 (Linux; Android; ExoPlayerLib/2.19.1)"

    @classmethod
    def proxy_stream(
        cls,
        remote_url: str,
        request_headers: Dict[str, str],
        client_handler: Any,
        is_head_request: bool = False,
    ):
        """
        Proxies an upstream audio URL to the client handler (BaseHTTPRequestHandler).
        """
        upstream_headers = {
            "User-Agent": cls.USER_AGENT,
        }

        # Forward Range header if present
        range_header = request_headers.get("Range") or request_headers.get("range")
        if range_header:
            upstream_headers["Range"] = range_header
            logger.debug("Forwarding Range header to Qobuz: %s", range_header)

        req = urllib.request.Request(
            remote_url,
            headers=upstream_headers,
            method="HEAD" if is_head_request else "GET",
        )

        try:
            with urllib.request.urlopen(req, timeout=15) as upstream_resp:
                status_code = upstream_resp.status

                # Determine content headers
                content_type = upstream_resp.headers.get("Content-Type", "audio/flac")
                content_length = upstream_resp.headers.get("Content-Length")
                content_range = upstream_resp.headers.get("Content-Range")
                accept_ranges = upstream_resp.headers.get("Accept-Ranges", "bytes")

                # Send response status
                client_handler.send_response(status_code)
                client_handler.send_header("Content-Type", content_type)
                client_handler.send_header("Accept-Ranges", accept_ranges)
                client_handler.send_header("Access-Control-Allow-Origin", "*")
                client_handler.send_header("Cache-Control", "no-cache, no-store")

                if content_length:
                    client_handler.send_header("Content-Length", content_length)
                if content_range:
                    client_handler.send_header("Content-Range", content_range)

                client_handler.end_headers()

                # If this was only a HEAD probe, don't write body
                if is_head_request:
                    return

                # Stream audio chunks to client
                bytes_sent = 0
                while True:
                    chunk = upstream_resp.read(CHUNK_SIZE)
                    if not chunk:
                        break
                    client_handler.wfile.write(chunk)
                    bytes_sent += len(chunk)

                logger.debug("Successfully streamed %d bytes", bytes_sent)

        except (BrokenPipeError, ConnectionResetError):
            logger.debug("Client closed audio stream prematurely (track skipped/stopped)")
        except urllib.error.HTTPError as e:
            logger.error("Upstream CDN HTTP error %d: %s", e.code, e.reason)
            try:
                client_handler.send_response(e.code)
                client_handler.send_header("Content-Type", "application/json")
                client_handler.end_headers()
                client_handler.wfile.write(
                    f'{{"error": "Upstream error {e.code}"}}'.encode("utf-8")
                )
            except Exception:
                pass
        except Exception as e:
            logger.error("Error proxying audio stream: %s", e)
            try:
                client_handler.send_response(502)
                client_handler.send_header("Content-Type", "application/json")
                client_handler.end_headers()
                client_handler.wfile.write(
                    f'{{"error": "Proxy error: {str(e)}"}}'.encode("utf-8")
                )
            except Exception:
                pass
