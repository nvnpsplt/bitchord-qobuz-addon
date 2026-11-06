"""
Unit tests for BitChord Qobuz Source Addon.
Tests manifest structure, signature hashing, track model serialization, and query cleaning.
"""

import unittest
from qobuz.signature import generate_file_url_signature, generate_legacy_signature
from qobuz.models import QobuzTrack, AudioQuality, FormatId, StreamInfo
from addon.manifest import get_addon_manifest
from addon.handler import clean_query


class TestAddonManifest(unittest.TestCase):
    def test_manifest_structure(self):
        manifest = get_addon_manifest("http://192.168.1.100:8080")
        self.assertEqual(manifest["id"], "org.bitchord.addon.qobuz")
        self.assertEqual(manifest["name"], "Qobuz FLAC")
        self.assertIn("search", manifest["resources"])
        self.assertIn("stream", manifest["resources"])
        self.assertIn("flac", manifest["formats"])
        self.assertIn("HI_RES", manifest["qualities"])
        self.assertTrue(manifest["icon"].startswith("http://192.168.1.100:8080"))


class TestSignature(unittest.TestCase):
    def test_generate_file_url_signature(self):
        sig = generate_file_url_signature(
            track_id=1234567,
            format_id=27,
            request_ts=1700000000,
            app_secret="test_secret_32_chars_long_12345",
            intent="stream",
        )
        self.assertEqual(len(sig), 32)
        self.assertTrue(all(c in "0123456789abcdef" for c in sig))

    def test_legacy_signature(self):
        sig = generate_legacy_signature(
            track_id=1234567,
            format_id=6,
            request_ts=1700000000,
            app_secret="test_secret_32_chars_long_12345",
        )
        self.assertEqual(len(sig), 32)


class TestTrackModel(unittest.TestCase):
    def test_from_api_item(self):
        raw_api_item = {
            "id": 18491294,
            "title": "Get Lucky",
            "version": "Radio Edit",
            "duration": 248,
            "maximum_bit_depth": 24,
            "maximum_sampling_rate": 88.2,
            "hires": True,
            "performer": {"name": "Daft Punk feat. Pharrell Williams"},
            "album": {
                "title": "Random Access Memories",
                "image": {"large": "https://static.qobuz.com/cover.jpg"},
            },
        }

        track = QobuzTrack.from_api_item(raw_api_item)
        self.assertEqual(track.id, "18491294")
        self.assertEqual(track.title, "Get Lucky (Radio Edit)")
        self.assertEqual(track.artist, "Daft Punk feat. Pharrell Williams")
        self.assertEqual(track.album, "Random Access Memories")
        self.assertEqual(track.bit_depth, 24)
        self.assertTrue(track.hires)

        bitchord_dict = track.to_bitchord_dict("http://192.168.1.50:8080")
        self.assertEqual(bitchord_dict["id"], "18491294")
        self.assertEqual(bitchord_dict["audioQuality"], "HI_RES")
        self.assertEqual(bitchord_dict["format"], "flac")
        self.assertEqual(bitchord_dict["bitDepth"], 24)
        self.assertEqual(bitchord_dict["sampleRate"], 88200)
        self.assertEqual(bitchord_dict["streamURL"], "http://192.168.1.50:8080/stream/18491294")

    def test_stream_info(self):
        info = StreamInfo(
            url="https://streaming.qobuz.com/sample.flac",
            format="flac",
            audio_quality="HI_RES",
            bit_depth=24,
            sample_rate=96000,
            bitrate=4608,
        )
        d = info.to_bitchord_dict()
        self.assertEqual(d["format"], "flac")
        self.assertEqual(d["audioQuality"], "HI_RES")
        self.assertEqual(d["bitDepth"], 24)
        self.assertEqual(d["sampleRate"], 96000)


class TestCleanQuery(unittest.TestCase):
    def test_clean_junk(self):
        self.assertEqual(
            clean_query("The Weeknd - Blinding Lights (Official Video)"),
            "The Weeknd - Blinding Lights",
        )
        self.assertEqual(
            clean_query("Daft Punk - Get Lucky [Official Audio] [HD]"),
            "Daft Punk - Get Lucky",
        )
        self.assertEqual(
            clean_query("Coldplay - Yellow (Lyric Video)"),
            "Coldplay - Yellow",
        )


if __name__ == "__main__":
    unittest.main()
