from dataclasses import dataclass, field
from enum import IntEnum
from typing import Optional, Dict, Any


class FormatId(IntEnum):
    """Qobuz Audio Quality Format IDs."""
    MP3_320 = 5       # MP3 320 kbps CBR
    FLAC_16_44 = 6    # FLAC 16-bit / 44.1 kHz (CD Lossless)
    FLAC_24_96 = 7    # FLAC 24-bit / up to 96 kHz (Hi-Res)
    FLAC_24_192 = 27  # FLAC 24-bit / up to 192 kHz (Highest Hi-Res)


class AudioQuality:
    HI_RES = "HI_RES"
    LOSSLESS = "LOSSLESS"
    HIGH = "HIGH"

    @classmethod
    def from_track(cls, bit_depth: int = 16, sample_rate: float = 44.1) -> str:
        if bit_depth > 16 or sample_rate > 48.0:
            return cls.HI_RES
        return cls.LOSSLESS


@dataclass
class QobuzTrack:
    id: str
    title: str
    artist: str
    album: str
    duration: int  # in seconds
    artwork_url: str = ""
    hires: bool = False
    bit_depth: int = 16
    sample_rate: float = 44.1  # in kHz, e.g. 96.0, 192.0
    isrc: Optional[str] = None
    streamable: bool = True
    maximum_format_id: int = FormatId.FLAC_16_44
    raw_data: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_api_item(cls, item: Dict[str, Any]) -> "QobuzTrack":
        """Parse track from Qobuz API JSON track item."""
        track_id = str(item.get("id", ""))
        title = item.get("title", "Unknown Title")
        version = item.get("version")
        if version and version.strip():
            title = f"{title} ({version.strip()})"

        # Extract artist/performer
        performer = item.get("performer") or {}
        artist_obj = item.get("artist") or {}
        artist = performer.get("name") or artist_obj.get("name") or "Unknown Artist"

        # Extract album & artwork
        album_obj = item.get("album") or {}
        album = album_obj.get("title", "")
        images = album_obj.get("image") or {}
        artwork_url = (
            images.get("large")
            or images.get("extralarge")
            or images.get("mega")
            or images.get("thumbnail")
            or images.get("small")
            or ""
        )

        duration = int(item.get("duration", 0))
        bit_depth = int(item.get("maximum_bit_depth", 16) or 16)
        sample_rate = float(item.get("maximum_sampling_rate", 44.1) or 44.1)
        hires = bool(item.get("hires") or item.get("hires_streamable") or bit_depth > 16)
        streamable = bool(item.get("streamable", True))

        # Determine maximum available format ID
        if bit_depth >= 24 and sample_rate > 96.0:
            max_fmt = FormatId.FLAC_24_192
        elif bit_depth >= 24:
            max_fmt = FormatId.FLAC_24_96
        else:
            max_fmt = FormatId.FLAC_16_44

        return cls(
            id=track_id,
            title=title,
            artist=artist,
            album=album,
            duration=duration,
            artwork_url=artwork_url,
            hires=hires,
            bit_depth=bit_depth,
            sample_rate=sample_rate,
            isrc=item.get("isrc"),
            streamable=streamable,
            maximum_format_id=max_fmt,
            raw_data=item,
        )

    def to_bitchord_dict(self, base_url: str = "") -> Dict[str, Any]:
        """
        Format track object for BitChord Addon Protocol response.
        Matches BitChord schema specifications:
        - id (str): unique identifier
        - title (str): track title
        - artist (str): artist name
        - album (str): album name
        - duration (int): duration in seconds
        - artworkURL (str): album artwork image url
        - format (str): 'flac'
        - audioQuality (str): 'HI_RES' or 'LOSSLESS'
        - bitDepth (int): 16 or 24
        - sampleRate (int): sample rate in Hz (e.g. 44100, 96000, 192000)
        - streamURL (str): stream link to this addon
        """
        sample_rate_khz = self.sample_rate if self.sample_rate < 1000 else self.sample_rate / 1000.0
        sample_rate_display = f"{sample_rate_khz:g}"
        audio_quality_str = f"{self.bit_depth}-bit / {sample_rate_display} kHz"
        sample_rate_hz = int(self.sample_rate * 1000) if self.sample_rate < 1000 else int(self.sample_rate)

        return {
            "id": str(self.id),
            "title": self.title,
            "artist": self.artist,
            "album": self.album,
            "duration": self.duration,
            "artworkURL": self.artwork_url,
            "format": "",
            "audioQuality": audio_quality_str,
            "sampleRate": sample_rate_hz,
            "bitDepth": self.bit_depth,
        }


@dataclass
class StreamInfo:
    url: str
    format: str = "flac"
    audio_quality: str = AudioQuality.LOSSLESS
    bit_depth: int = 16
    sample_rate: int = 44100  # in Hz
    bitrate: int = 1411  # in kbps
    mime_type: str = "audio/flac"
    duration: int = 0

    def to_bitchord_dict(self) -> Dict[str, Any]:
        """Format stream descriptor for BitChord GET /stream/{id} response."""
        return {
            "url": self.url,
            "format": self.format,
            "audioQuality": self.audio_quality,
            "bitDepth": self.bit_depth,
            "sampleRate": self.sample_rate,
            "bitrate": self.bitrate,
            "mimeType": self.mime_type,
            "duration": self.duration,
        }

