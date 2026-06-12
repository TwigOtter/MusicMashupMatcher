"""Match engine — scores every A×B pair by BPM and Camelot key distance."""

from __future__ import annotations

from dataclasses import dataclass

from .keys import camelot_distance
from .models import Match, Track

# Halftime and doubletime are standard mashup techniques, so a 170 BPM
# track is also checked against 85 / 340 BPM partners.
BPM_RATIOS = [1.0, 2.0, 0.5]

RATIO_NOTES = {2.0: "doubletime match", 0.5: "halftime match"}

# When either track lacks key data we can't score harmony; penalize as if
# the keys were moderately apart instead of silently treating it as perfect.
UNKNOWN_KEY_PENALTY = 25


@dataclass
class MatchConfig:
    bpm_tolerance: float = 0.10       # ±10%
    camelot_tolerance: int = 2        # ±2 Camelot steps
    min_score: int = 40


def best_bpm_ratio(bpm_a: float, bpm_b: float) -> tuple[float, float]:
    """Return (ratio, distance_pct) for the ratio that brings the BPMs closest.

    distance_pct is how far bpm_a * ratio lands from bpm_b, relative to bpm_b.
    """
    return min(
        ((r, abs(bpm_a * r - bpm_b) / bpm_b) for r in BPM_RATIOS),
        key=lambda pair: pair[1],
    )


def score_pair(track_a: Track, track_b: Track, config: MatchConfig) -> Match | None:
    """Score one pair; returns None if the pair fails any tolerance gate."""
    if track_a.bpm is None or track_b.bpm is None:
        return None

    ratio, bpm_dist = best_bpm_ratio(track_a.bpm, track_b.bpm)
    if bpm_dist > config.bpm_tolerance:
        return None

    notes: list[str] = []
    if ratio in RATIO_NOTES:
        notes.append(RATIO_NOTES[ratio])

    score = 100.0
    score -= bpm_dist * 100

    cam_dist: int | None = None
    if track_a.camelot and track_b.camelot:
        cam_dist = camelot_distance(track_a.camelot, track_b.camelot)
        if cam_dist > config.camelot_tolerance:
            return None
        score -= cam_dist * 20
        if cam_dist == 0:
            notes.append("same key")
        elif track_a.camelot[:-1] == track_b.camelot[:-1]:
            notes.append("energy shift (relative major/minor)")
    else:
        score -= UNKNOWN_KEY_PENALTY
        notes.append("key unknown")

    final = round(score)
    if final < config.min_score:
        return None

    return Match(
        track_a=track_a,
        track_b=track_b,
        score=final,
        camelot_distance=cam_dist,
        bpm_ratio=ratio,
        bpm_distance_pct=round(bpm_dist * 100, 2),
        notes=notes,
    )


def find_matches(
    tracks_a: list[Track],
    tracks_b: list[Track],
    config: MatchConfig | None = None,
) -> list[Match]:
    """Score every A×B pair, sorted by track A then score descending."""
    config = config or MatchConfig()
    matches = [
        m
        for a in tracks_a
        for b in tracks_b
        if (m := score_pair(a, b, config)) is not None
    ]
    matches.sort(key=lambda m: (m.track_a.name.lower(), m.track_a.id, -m.score))
    return matches
