"""Tier 1 — GetSongBPM API (https://getsongbpm.com).

Free API; requires an API key and a backlink credit in any public UI
(the HTML report includes one).
"""

from __future__ import annotations

import difflib
import logging
import re

import requests

from ..keys import parse_key_string

log = logging.getLogger(__name__)

SEARCH_URL = "https://api.getsong.co/search/"

# Strip remix/edit/feat. qualifiers that hurt search matching.
_NOISE_RE = re.compile(
    r"\s*[\(\[][^)\]]*[\)\]]|\s*-\s*(remaster(ed)?|radio edit|original mix).*$",
    re.IGNORECASE,
)


def _normalize(text: str) -> str:
    return _NOISE_RE.sub("", text).strip().lower()


def _similarity(a: str, b: str) -> float:
    return difflib.SequenceMatcher(None, _normalize(a), _normalize(b)).ratio()


def getsongbpm_lookup(
    name: str,
    artist: str,
    api_key: str,
    *,
    session: requests.Session | None = None,
    timeout: float = 15.0,
) -> dict | None:
    """Look up BPM/key for a track. Returns {"bpm", "key", "mode"} or None.

    "key" and "mode" may be None when the API has tempo but no key data.
    """
    http = session or requests
    primary_artist = artist.split(",")[0].strip()
    try:
        resp = http.get(
            SEARCH_URL,
            params={
                "api_key": api_key,
                "type": "both",
                "lookup": f"song:{_normalize(name)} artist:{_normalize(primary_artist)}",
            },
            # Their CDN sometimes rejects the default python-requests UA.
            headers={"User-Agent": "MashupMatcher/1.0 (+https://github.com/twigotter/musicmashupmatcher)"},
            timeout=timeout,
        )
        resp.raise_for_status()
        payload = resp.json()
    except (requests.RequestException, ValueError) as exc:
        log.warning("GetSongBPM request failed for %s — %s: %s", artist, name, exc)
        return None

    results = payload.get("search")
    # The API signals "no result" — and also bad/missing API keys — with a
    # dict instead of a list. Surface anything that isn't a plain miss, or
    # an invalid key looks identical to 100% cache misses.
    if not isinstance(results, list):
        error = None
        if isinstance(results, dict):
            error = results.get("error")
        error = error or payload.get("error")
        if error and "no result" not in str(error).lower():
            log.warning("GetSongBPM error for %s — %s: %s", artist, name, error)
        else:
            log.debug("GetSongBPM: no result for %s — %s", artist, name)
        return None

    best, best_score = None, 0.0
    for candidate in results:
        title = candidate.get("song_title") or candidate.get("title") or ""
        cand_artist = (candidate.get("artist") or {}).get("name") or ""
        score = _similarity(name, title) + _similarity(primary_artist, cand_artist)
        if score > best_score:
            best, best_score = candidate, score

    # Require a reasonably confident match — a wrong track's BPM is worse
    # than no data, since Tier 2/3 would never get the chance to correct it.
    if best is None or best_score < 1.2:
        log.debug(
            "GetSongBPM: best candidate too weak for %s — %s (score %.2f: %r)",
            artist, name, best_score,
            (best or {}).get("song_title"),
        )
        return None

    try:
        bpm = float(best.get("tempo"))
    except (TypeError, ValueError):
        return None

    parsed = parse_key_string(best.get("key_of"))
    key, mode = parsed if parsed else (None, None)
    return {"bpm": bpm, "key": key, "mode": mode}
