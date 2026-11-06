import json
import time
import urllib.parse
import urllib.request
import urllib.error
import logging
from typing import Optional, List, Dict, Any, Tuple

from .bundle import BundleScraper
from .models import QobuzTrack, StreamInfo, FormatId, AudioQuality
from .signature import generate_file_url_signature, generate_legacy_signature

logger = logging.getLogger("bitchord.qobuz.client")


class QobuzAPIError(Exception):
    """Exception raised when Qobuz API returns an error."""
    def __init__(self, message: str, status_code: int = 500, error_code: Optional[str] = None):
        super().__init__(message)
        self.status_code = status_code
        self.error_code = error_code


class QobuzClient:
    """
    Qobuz REST API client adapted and optimized for BitChord streaming.
    Supports catalog searching, metadata retrieval, user auth, and signed track streaming.
    """

    BASE_URL = "https://www.qobuz.com/api.json/0.2"

    def __init__(
        self,
        app_id: Optional[str] = None,
        app_secret: Optional[str] = None,
        user_auth_token: Optional[str] = None,
        email: Optional[str] = None,
        password: Optional[str] = None,
        preferred_format: int = FormatId.FLAC_24_192,
    ):
        self.scraper = BundleScraper(custom_app_id=app_id, custom_secret=app_secret)
        self._app_id = app_id
        self._app_secret = app_secret
        self.user_auth_token = user_auth_token
        self.email = email
        self.password = password
        self.preferred_format = preferred_format
        self.user_info: Optional[Dict[str, Any]] = None

        # Track metadata cache
        self._track_cache: Dict[str, QobuzTrack] = {}

    @property
    def app_id(self) -> str:
        if not self._app_id:
            self._app_id, _ = self.scraper.get_credentials()
        return self._app_id

    @property
    def app_secret(self) -> str:
        if not self._app_secret:
            _, self._app_secret = self.scraper.get_credentials()
        return self._app_secret

    def update_credentials(
        self,
        app_id: Optional[str] = None,
        app_secret: Optional[str] = None,
        user_auth_token: Optional[str] = None,
        preferred_format: Optional[int] = None,
    ):
        """Update runtime credentials and reset caches."""
        if app_id:
            self._app_id = app_id
            self.scraper._custom_app_id = app_id
        if app_secret:
            self._app_secret = app_secret
            self.scraper._custom_secret = app_secret
        if user_auth_token is not None:
            self.user_auth_token = user_auth_token.strip() if user_auth_token else None
        if preferred_format is not None:
            self.preferred_format = preferred_format
        self._track_cache.clear()

    def api_call(
        self,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        method: str = "GET",
    ) -> Dict[str, Any]:
        """
        Executes an HTTP request to Qobuz API v0.2.
        """
        params = dict(params or {})
        params["app_id"] = self.app_id

        if self.user_auth_token and "user_auth_token" not in params:
            params["user_auth_token"] = self.user_auth_token

        query_string = urllib.parse.urlencode(params)
        url = f"{self.BASE_URL}/{endpoint.lstrip('/')}"
        if method == "GET" and query_string:
            url = f"{url}?{query_string}"
            data = None
        else:
            data = query_string.encode("utf-8") if query_string else None

        headers = {
            "User-Agent": "BitChord-Qobuz-Addon/1.0",
            "X-App-Id": self.app_id,
            "Accept": "application/json",
        }
        if self.user_auth_token:
            headers["X-User-Auth-Token"] = self.user_auth_token

        req = urllib.request.Request(url, data=data, headers=headers, method=method)

        try:
            with urllib.request.urlopen(req, timeout=12) as response:
                content = response.read().decode("utf-8")
                return json.loads(content)
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="ignore")
            error_code = None
            message = f"Qobuz HTTP {e.code}: {e.reason}"
            try:
                err_json = json.loads(body)
                if "message" in err_json:
                    message = err_json["message"]
                if "error_code" in err_json:
                    error_code = err_json["error_code"]
            except Exception:
                pass
            logger.error("API error for %s: %s (Status: %s)", endpoint, message, e.code)
            raise QobuzAPIError(message, status_code=e.code, error_code=error_code) from e
        except Exception as e:
            logger.error("Network error on %s: %s", endpoint, e)
            raise QobuzAPIError(f"Network error connecting to Qobuz: {e}", status_code=502) from e

    def login(self, username: Optional[str] = None, password: Optional[str] = None) -> Dict[str, Any]:
        """Authenticate using username and password."""
        user = username or self.email
        pwd = password or self.password
        if not user or not pwd:
            raise ValueError("Email and password are required for login")

        res = self.api_call(
            "user/login",
            {"username": user, "password": pwd},
            method="GET",
        )
        self.user_auth_token = res.get("user_auth_token")
        self.user_info = res.get("user")
        logger.info("Successfully logged in to Qobuz as %s", user)
        return res

    def verify_auth(self) -> Dict[str, Any]:
        """Verify the current user_auth_token and retrieve user subscription info."""
        if not self.user_auth_token:
            return {"authenticated": False, "status": "No token provided"}

        try:
            res = self.api_call("user/get")
            self.user_info = res
            return {
                "authenticated": True,
                "user": res,
                "display_name": res.get("display_name") or res.get("email"),
                "subscription": res.get("credential", {}).get("description", "Active"),
            }
        except QobuzAPIError as e:
            return {"authenticated": False, "error": str(e), "status_code": e.status_code}

    def search(self, query: str, limit: int = 15, offset: int = 0) -> List[QobuzTrack]:
        """
        Search Qobuz catalog for tracks matching the query.
        """
        if not query or not query.strip():
            return []

        clean_query = query.strip()
        logger.debug("Searching Qobuz for: %s", clean_query)

        data = self.api_call(
            "catalog/search",
            {
                "query": clean_query,
                "type": "tracks",
                "limit": limit,
                "offset": offset,
            },
        )

        tracks_data = data.get("tracks", {}).get("items", [])
        results: List[QobuzTrack] = []

        for item in tracks_data:
            try:
                track = QobuzTrack.from_api_item(item)
                if track.id:
                    self._track_cache[track.id] = track
                    results.append(track)
            except Exception as e:
                logger.warning("Error parsing track item: %s", e)

        return results

    def get_track(self, track_id: str) -> Optional[QobuzTrack]:
        """Fetch metadata for a single track by ID."""
        if track_id in self._track_cache:
            return self._track_cache[track_id]

        try:
            data = self.api_call("track/get", {"track_id": track_id})
            track = QobuzTrack.from_api_item(data)
            self._track_cache[track_id] = track
            return track
        except Exception as e:
            logger.error("Failed to fetch track %s: %s", track_id, e)
            return None

    def get_file_url(
        self,
        track_id: str,
        preferred_format: Optional[int] = None,
        intent: str = "stream",
    ) -> StreamInfo:
        """
        Request stream URL for track_id from track/getFileUrl with request signature.
        Gracefully falls back across formats (27 -> 7 -> 6 -> 5) until a valid stream is found.
        """
        target_format = preferred_format or self.preferred_format

        # Format fallback hierarchy (Highest Hi-Res to MP3)
        fallback_order = [
            FormatId.FLAC_24_192,
            FormatId.FLAC_24_96,
            FormatId.FLAC_16_44,
            FormatId.MP3_320,
        ]

        # Prioritize the requested format first
        if target_format in fallback_order:
            fallback_order.remove(target_format)
            formats_to_try = [target_format] + fallback_order
        else:
            formats_to_try = fallback_order

        last_error = None

        for fmt in formats_to_try:
            try:
                stream_info = self._request_stream_url(track_id, fmt, intent=intent)
                if stream_info and stream_info.url:
                    logger.info("Obtained stream for track %s at format %s", track_id, fmt)
                    return stream_info
            except QobuzAPIError as e:
                last_error = e
                logger.debug("Format %s not available for track %s: %s", fmt, track_id, e)
                continue
            except Exception as e:
                last_error = e
                logger.debug("Unexpected error trying format %s for track %s: %s", fmt, track_id, e)
                continue

        # If everything failed, raise descriptive error
        raise QobuzAPIError(
            f"Unable to retrieve stream for track {track_id}. Last error: {last_error}",
            status_code=404,
        )

    def _request_stream_url(self, track_id: str, format_id: int, intent: str = "stream") -> StreamInfo:
        """Performs signed API call to track/getFileUrl."""
        request_ts = str(int(time.time()))

        # Generate request signature
        request_sig = generate_file_url_signature(
            track_id=track_id,
            format_id=format_id,
            request_ts=request_ts,
            app_secret=self.app_secret,
            intent=intent,
        )

        params = {
            "track_id": track_id,
            "format_id": format_id,
            "intent": intent,
            "request_ts": request_ts,
            "request_sig": request_sig,
        }

        try:
            res = self.api_call("track/getFileUrl", params=params)
        except QobuzAPIError as e:
            # Try legacy signature fallback if primary signature produced 400
            if e.status_code == 400:
                logger.debug("Trying legacy signature format for track %s...", track_id)
                legacy_sig = generate_legacy_signature(
                    track_id=track_id,
                    format_id=format_id,
                    request_ts=request_ts,
                    app_secret=self.app_secret,
                )
                params["request_sig"] = legacy_sig
                res = self.api_call("track/getFileUrl", params=params)
            else:
                raise

        media_url = res.get("url")
        if not media_url:
            raise QobuzAPIError(f"No media URL returned for track {track_id}", status_code=404)

        mime_type = res.get("mime_type", "audio/flac" if format_id != FormatId.MP3_320 else "audio/mpeg")
        bit_depth = int(res.get("bit_depth") or (24 if format_id in (FormatId.FLAC_24_192, FormatId.FLAC_24_96) else 16))
        raw_sr = res.get("sampling_rate", 44.1)
        sample_rate_hz = int(float(raw_sr) * 1000) if float(raw_sr) < 1000 else int(float(raw_sr))

        audio_quality = AudioQuality.from_track(bit_depth, sample_rate_hz / 1000.0)
        fmt_name = "mp3" if format_id == FormatId.MP3_320 else "flac"

        # Calculate estimated bitrate
        if fmt_name == "mp3":
            bitrate = 320
        elif bit_depth == 24 and sample_rate_hz >= 192000:
            bitrate = 9216
        elif bit_depth == 24 and sample_rate_hz >= 96000:
            bitrate = 4608
        else:
            bitrate = 1411

        return StreamInfo(
            url=media_url,
            format=fmt_name,
            audio_quality=audio_quality,
            bit_depth=bit_depth,
            sample_rate=sample_rate_hz,
            bitrate=bitrate,
            mime_type=mime_type,
            duration=int(res.get("duration", 0)),
        )
