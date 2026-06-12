"""Tier 2 — AcousticBrainz (via MusicBrainz recording search).

AcousticBrainz stopped collecting data in 2022, so coverage is patchy;
this tier is a cheap second chance before falling back to local analysis.
"""

from __future__ import annotations

import logging
import time

import requests

from ..keys import NOTE_TO_PITCH

log = logging.getLogger(__name__)

MUSICBRAINZ_SEARCH_URL = "https://musicbrainz.org/ws/2/recording"
ACOUSTICBRAINZ_URL = "https://acousticbrainz.org/api/v1/{mbid}/low-level"
USER_AGENT = "MashupMatcher/1.0 (https://github.com/twigotter/musicmashupmatcher)"

# MusicBrainz asks for at most 1 request/second.
_MB_MIN_INTERVAL = 1.1
_last_mb_request = 0.0


def _mb_rate_limit() -> None:
    global _last_mb_request
    wait = _MB_MIN_INTERVAL - (time.monotonic() - _last_mb_request)
    if wait > 0:
        time.sleep(wait)
    _last_mb_request = time.monotonic()


def _resolve_mbid(name: str, artist: str, http, timeout: float) -> str | None:
    _mb_rate_limit()
    primary_artist = artist.split(",")[0].strip()
    resp = http.get(
        MUSICBRAINZ_SEARCH_URL,
        params={
            "query": f'recording:"{name}" AND artist:"{primary_artist}"',
            "fmt": "json",
            "limit": 5,
        },
        headers={"User-Agent": USER_AGENT},
        timeout=timeout,
    )
    resp.raise_for_status()
    recordings = resp.json().get("recordings", [])
    for rec in recordings:
        if rec.get("score", 0) >= 90:
            return rec["id"]
    return None


def acousticbrainz_lookup(
    name: str,
    artist: str,
    *,
    session: requests.Session | None = None,
    timeout: float = 15.0,
) -> dict | None:
    """Look up BPM/key via MusicBrainz -> AcousticBrainz. Returns
    {"bpm", "key", "mode"} or None."""
    http = session or requests
    try:
        mbid = _resolve_mbid(name, artist, http, timeout)
        if mbid is None:
            return None
        resp = http.get(
            ACOUSTICBRAINZ_URL.format(mbid=mbid),
            headers={"User-Agent": USER_AGENT},
            timeout=timeout,
        )
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        data = resp.json()
    except (requests.RequestException, ValueError) as exc:
        log.warning("AcousticBrainz lookup failed for %s — %s: %s", artist, name, exc)
        return None

    bpm = data.get("rhythm", {}).get("bpm")
    if not bpm:
        return None

    tonal = data.get("tonal", {})
    key = NOTE_TO_PITCH.get(tonal.get("key_key"))
    scale = tonal.get("key_scale")
    mode = {"minor": 0, "major": 1}.get(scale) if key is not None else None
    if mode is None:
        key = None
    return {"bpm": float(bpm), "key": key, "mode": mode}
