"""
BitChord Addon Manifest Generator.
Defines the addon metadata, supported resources, and format capabilities.
"""

from typing import Dict, Any


def get_addon_manifest(base_url: str = "") -> Dict[str, Any]:
    """
    Returns the BitChord Addon Manifest specification.
    According to BitChord Addon Developer Guide:
    - id (str): reverse domain identifier
    - name (str): user-facing name
    - version (str): semver
    - description (str): description of the source
    - resources (list): ["search", "stream"]
    - formats (list): supported audio codecs, e.g. ["flac"]
    - qualities (list): supported quality tags
    """
    base = base_url.rstrip("/") if base_url else ""
    icon_url = f"{base}/static/icon.svg" if base else "/static/icon.svg"

    return {
        "id": "org.bitchord.addon.qobuz",
        "name": "Qobuz FLAC",
        "version": "1.0.0",
        "description": "High Quality Lossless & Hi-Res FLAC Streaming Source for BitChord powered by Qobuz",
        "icon": icon_url,
        "resources": [
            "search",
            "stream",
        ],
        "types": [
            "music",
        ],
        "formats": [
            "flac",
        ],
        "qualities": [
            "HI_RES",
            "LOSSLESS",
            "24B_192K",
            "24B_96K",
            "16B_44K",
        ],
        "author": "BitChord Community",
        "homepage": "https://github.com/vitiko98/qobuz-dl",
        "settings": {
            "directSourceStreaming": True,
            "maxQuality": "24B_192K",
            "audioProxy": True,
        },
    }

