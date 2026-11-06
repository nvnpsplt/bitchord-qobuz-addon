"""
BitChord Addon package for High Quality Qobuz FLAC Streaming.
"""

from .manifest import get_addon_manifest
from .handler import BitChordAddonHandler
from .stream_proxy import StreamProxy

__all__ = [
    "get_addon_manifest",
    "BitChordAddonHandler",
    "StreamProxy",
]

