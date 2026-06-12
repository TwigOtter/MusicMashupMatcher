"""Tiered metadata resolver: cache -> GetSongBPM -> AcousticBrainz -> local."""

from __future__ import annotations

import logging

from .cache import MetadataCache
from .keys import to_camelot
from .models import Track
from .resolvers import acousticbrainz_lookup, getsongbpm_lookup, local_analyze

log = logging.getLogger(__name__)


def apply_metadata(track: Track, result: dict, source: str) -> Track:
    track.bpm = result["bpm"]
    track.key = result.get("key")
    track.mode = result.get("mode")
    if track.has_key:
        track.camelot = to_camelot(track.key, track.mode)
    track.source = source
    return track


class MetadataResolver:
    def __init__(
        self,
        cache: MetadataCache,
        getsongbpm_api_key: str | None,
        *,
        use_cache: bool = True,
        api_only: bool = False,
    ):
        self.cache = cache
        self.api_key = getsongbpm_api_key
        self.use_cache = use_cache
        self.api_only = api_only

    def resolve(self, track: Track) -> Track:
        if self.use_cache and (cached := self.cache.get(track.id)):
            cached.duration_ms = track.duration_ms
            return cached

        result, source = None, None
        if self.api_key:
            result = getsongbpm_lookup(track.name, track.artist, self.api_key)
            source = "getsongbpm"
        if result is None:
            result = acousticbrainz_lookup(track.name, track.artist)
            source = "acousticbrainz"
        if result is None and not self.api_only:
            result = local_analyze(track.name, track.artist)
            source = "local"

        if result is not None:
            track = apply_metadata(track, result, source)
            self.cache.save(track)
        else:
            log.info("No metadata found for %s — %s", track.artist, track.name)
        return track

    def resolve_all(self, tracks: list[Track], label: str = "") -> list[Track]:
        resolved = []
        for i, track in enumerate(tracks, 1):
            log.info("[%s %d/%d] %s — %s", label, i, len(tracks), track.artist, track.name)
            resolved.append(self.resolve(track))
        return resolved
