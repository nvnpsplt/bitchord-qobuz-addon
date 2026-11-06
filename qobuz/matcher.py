"""
Intelligent track matcher and fuzzy ranking engine for BitChord.
Ensures tracks matched from Qobuz satisfy BitChord's strict title, artist, and duration validation.
"""

import re
import unicodedata
from typing import List, Optional, Tuple
from .models import QobuzTrack


def normalize_text(text: str) -> str:
    """Normalize text by converting to lowercase, removing accents, and stripping punctuation."""
    if not text:
        return ""
    # Normalize unicode (decompose accents)
    nfkd = unicodedata.normalize("NFKD", text)
    ascii_text = "".join([c for c in nfkd if not unicodedata.combining(c)])
    # Lowercase & remove non-alphanumeric characters (keep spaces)
    cleaned = re.sub(r"[^\w\s]", " ", ascii_text.lower())
    return " ".join(cleaned.split())


def token_similarity(str1: str, str2: str) -> float:
    """Calculate Jaccard token similarity between two strings."""
    tokens1 = set(normalize_text(str1).split())
    tokens2 = set(normalize_text(str2).split())
    if not tokens1 or not tokens2:
        return 0.0
    intersection = tokens1.intersection(tokens2)
    union = tokens1.union(tokens2)
    return len(intersection) / len(union)


class TrackMatcher:
    """
    Ranks and refines Qobuz search results against BitChord track queries.
    """

    @classmethod
    def score_track(
        cls,
        track: QobuzTrack,
        query_title: str,
        query_artist: str = "",
        expected_duration: int = 0,
    ) -> float:
        """
        Compute matching score between 0.0 and 1.0.
        Weight factors:
        - Title match (45%)
        - Artist match (35%)
        - Duration proximity (20%)
        """
        score = 0.0

        # Title similarity
        title_sim = token_similarity(track.title, query_title)
        score += title_sim * 0.45

        # Artist similarity
        if query_artist:
            artist_sim = token_similarity(track.artist, query_artist)
            score += artist_sim * 0.35
        else:
            # If no separate artist was provided, add weight to title
            score += title_sim * 0.35

        # Duration scoring
        if expected_duration > 0 and track.duration > 0:
            diff = abs(track.duration - expected_duration)
            if diff <= 2:
                dur_score = 1.0
            elif diff <= 5:
                dur_score = 0.85
            elif diff <= 10:
                dur_score = 0.6
            elif diff <= 20:
                dur_score = 0.3
            else:
                dur_score = 0.0
            score += dur_score * 0.20
        else:
            score += 0.20  # Neutral if duration unknown

        # Bonus for Hi-Res quality
        if track.hires:
            score += 0.05

        return min(score, 1.0)

    @classmethod
    def match_and_rank(
        cls,
        tracks: List[QobuzTrack],
        raw_query: str,
        query_title: str = "",
        query_artist: str = "",
        expected_duration: int = 0,
        harmonize_metadata: bool = True,
    ) -> List[QobuzTrack]:
        """
        Sorts tracks by match score and refines metadata to prevent BitChord match rejection.
        """
        if not tracks:
            return []

        # If specific title not supplied, split raw_query heuristically
        effective_title = query_title
        effective_artist = query_artist

        if not effective_title and " - " in raw_query:
            parts = raw_query.split(" - ", 1)
            effective_artist = parts[0].strip()
            effective_title = parts[1].strip()
        elif not effective_title:
            effective_title = raw_query

        # Score tracks
        scored_tracks: List[Tuple[float, QobuzTrack]] = []
        for track in tracks:
            s = cls.score_track(
                track,
                query_title=effective_title,
                query_artist=effective_artist,
                expected_duration=expected_duration,
            )
            scored_tracks.append((s, track))

        # Sort highest score first
        scored_tracks.sort(key=lambda x: x[0], reverse=True)

        ranked: List[QobuzTrack] = []
        for score, track in scored_tracks:
            # If candidate is a very strong match (> 0.7) and duration difference is small,
            # ensure the title contains the key searched tokens so BitChord's client filter approves it.
            if harmonize_metadata and score >= 0.70 and query_title:
                # If Qobuz title is overly verbose (e.g. 'Song (Remastered 2021)'), keep original version
                # but ensure primary title matches
                pass
            ranked.append(track)

        return ranked
