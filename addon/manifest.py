"""
BitChord Addon Manifest Generator.
Defines the addon metadata, supported resources, and format capabilities.
"""

from typing import Dict, Any


def get_addon_manifest(base_url: str = "") -> Dict[str, Any]:
    """
    Returns the BitChord Addon Manifest specification matching the Unified Addon standard.
    """
    base = base_url.rstrip("/") if base_url else ""
    icon_url = f"{base}/static/icon.svg" if base else "/static/icon.svg"

    return {
        "id": "dev.bitperfect.qobuz.de.personal",
        "name": "Qobuz [FLAC Hi-Res]",
        "version": "1.0.0-de",
        "resources": [
            "search",
            "stream"
        ],
        "allowDownloads": 1,
        "checkValidLossless": 1,
        "settings": [
            {
                "key": "quality",
                "default": "LOSSLESS",
                "options": [
                    {"value": "LOSSLESS"},
                    {"value": "HI_RES"},
                    {"value": "HIGH"},
                    {"value": "LOW"}
                ]
            }
        ]
    }

