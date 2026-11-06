import re
import urllib.request
import urllib.error
import logging
from typing import Dict, Optional, Tuple

logger = logging.getLogger("bitchord.qobuz.bundle")

# Known fallback credentials commonly used across open-source tools
DEFAULT_APP_ID = "712108740"
DEFAULT_SECRETS = {
    "primary": "25a6979603c467a7187c3ff5c13b6329",
    "secondary": "2a95e79ff729fcfd5870fa4a9ee69a47",
    "web": "be40245e33dcfbc1574fa07d4b29bb8b",
}


class BundleScraper:
    """
    Scrapes or provides Qobuz web player App ID and Secret Keys.
    Adapted from vitiko98/qobuz-dl's Bundle class with fallbacks and caching.
    """

    LOGIN_URL = "https://play.qobuz.com/login"
    BASE_URL = "https://play.qobuz.com"
    USER_AGENT = (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
    )

    BUNDLE_REGEX = re.compile(
        r'<script\s+src="(/resources/[^"]+?/bundle\.js)"></script>', re.IGNORECASE
    )

    APP_ID_PATTERNS = [
        re.compile(r'production:\s*\{\s*api:\s*\{\s*appId:\s*["\'](?P<app_id>\d+)["\']'),
        re.compile(r'appId:\s*["\'](?P<app_id>\d{8,10})["\']'),
        re.compile(r'["\']appId["\']:\s*["\'](?P<app_id>\d{8,10})["\']'),
    ]

    SECRET_PATTERNS = [
        re.compile(r'name:\s*["\'](?P<name>[^"\']+)["\'],\s*secret:\s*["\'](?P<secret>[a-f0-9]{32})["\']'),
        re.compile(r'appSecret:\s*["\'](?P<secret>[a-f0-9]{32})["\']'),
    ]

    def __init__(self, custom_app_id: Optional[str] = None, custom_secret: Optional[str] = None):
        self._custom_app_id = custom_app_id
        self._custom_secret = custom_secret
        self._cached_app_id: Optional[str] = None
        self._cached_secrets: Dict[str, str] = {}

    def get_credentials(self) -> Tuple[str, str]:
        """
        Returns (app_id, primary_secret).
        Prioritizes custom credentials, then cached/scraped, then defaults.
        """
        if self._custom_app_id and self._custom_secret:
            return self._custom_app_id, self._custom_secret

        app_id = self.get_app_id()
        secrets = self.get_secrets()
        primary_secret = next(iter(secrets.values()), DEFAULT_SECRETS["primary"])

        return app_id, primary_secret

    def get_app_id(self) -> str:
        if self._custom_app_id:
            return self._custom_app_id
        if self._cached_app_id:
            return self._cached_app_id

        scraped = self._scrape_bundle()
        if scraped and scraped[0]:
            self._cached_app_id = scraped[0]
            return scraped[0]

        logger.info("Using default Qobuz App ID: %s", DEFAULT_APP_ID)
        return DEFAULT_APP_ID

    def get_secrets(self) -> Dict[str, str]:
        if self._custom_secret:
            return {"custom": self._custom_secret}
        if self._cached_secrets:
            return self._cached_secrets

        scraped = self._scrape_bundle()
        if scraped and scraped[1]:
            self._cached_secrets = scraped[1]
            return scraped[1]

        logger.info("Using default Qobuz secrets")
        return DEFAULT_SECRETS

    def _scrape_bundle(self) -> Optional[Tuple[str, Dict[str, str]]]:
        """Attempt to download and parse the latest bundle from Qobuz web player."""
        try:
            req = urllib.request.Request(
                self.LOGIN_URL,
                headers={"User-Agent": self.USER_AGENT},
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                html = resp.read().decode("utf-8", errors="ignore")

            bundle_match = self.BUNDLE_REGEX.search(html)
            if not bundle_match:
                logger.debug("Bundle script path not found in login page HTML")
                return None

            bundle_path = bundle_match.group(1)
            bundle_url = f"{self.BASE_URL}{bundle_path}"
            logger.info("Found Qobuz bundle URL: %s", bundle_url)

            req_bundle = urllib.request.Request(
                bundle_url,
                headers={"User-Agent": self.USER_AGENT},
            )
            with urllib.request.urlopen(req_bundle, timeout=10) as resp:
                bundle_js = resp.read().decode("utf-8", errors="ignore")

            # Extract app_id
            app_id = None
            for pattern in self.APP_ID_PATTERNS:
                m = pattern.search(bundle_js)
                if m:
                    app_id = m.group("app_id")
                    break

            # Extract secrets
            secrets: Dict[str, str] = {}
            for pattern in self.SECRET_PATTERNS:
                for match in pattern.finditer(bundle_js):
                    d = match.groupdict()
                    name = d.get("name") or f"secret_{len(secrets)}"
                    secret = d.get("secret")
                    if secret and len(secret) == 32:
                        secrets[name] = secret

            if app_id:
                logger.info("Successfully scraped App ID: %s and %d secrets", app_id, len(secrets))
                return app_id, (secrets or DEFAULT_SECRETS)

        except Exception as e:
            logger.debug("Dynamic bundle scraping failed: %s (falling back to defaults)", e)

        return None

