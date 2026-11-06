"""
Qobuz API client and helper modules for BitChord Source Addon.
Adapted and enhanced from vitiko98/qobuz-dl.
"""

from .client import QobuzClient
from .signature import generate_file_url_signature
from .bundle import BundleScraper
from .models import QobuzTrack, AudioQuality

__all__ = [
    "QobuzClient",
    "generate_file_url_signature",
    "BundleScraper",
    "QobuzTrack",
    "AudioQuality",
]
