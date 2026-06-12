"""Core data models for Mashup Matcher."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Track:
    id: str           # Spotify ID
    name: str
    artist: str
    duration_ms: int = 0
    bpm: float | None = None
    key: int | None = None        # 0-11, pitch class notation
    mode: int | None = None       # 0 = minor, 1 = major
    camelot: str | None = None    # e.g. "8A", "5B"
    source: str | None = None     # which tier provided the metadata

    @property
    def resolved(self) -> bool:
        """True if we have enough metadata to attempt matching."""
        return self.bpm is not None

    @property
    def has_key(self) -> bool:
        return self.key is not None and self.mode is not None


@dataclass
class Match:
    track_a: Track
    track_b: Track
    score: int
    camelot_distance: int | None   # None when either track lacks key data
    bpm_ratio: float               # 1.0 = same tempo, 2.0 = doubletime, etc.
    bpm_distance_pct: float
    notes: list[str] = field(default_factory=list)
