"""Spotify playlist fetcher (Client Credentials flow — public playlists only)."""

from __future__ import annotations

import re

import spotipy
from spotipy.oauth2 import SpotifyClientCredentials

from .models import Track

_PLAYLIST_URL_RE = re.compile(r"playlist[/:]([A-Za-z0-9]+)")


def extract_playlist_id(value: str) -> str:
    """Accept a bare playlist ID, spotify: URI, or open.spotify.com URL."""
    m = _PLAYLIST_URL_RE.search(value)
    return m.group(1) if m else value


class SpotifyFetcher:
    def __init__(self, client_id: str, client_secret: str):
        self._client = spotipy.Spotify(
            auth_manager=SpotifyClientCredentials(
                client_id=client_id, client_secret=client_secret
            )
        )

    def fetch_playlist(self, playlist: str) -> list[Track]:
        playlist_id = extract_playlist_id(playlist)
        tracks: list[Track] = []
        page = self._client.playlist_items(
            playlist_id,
            fields="items(track(id,name,duration_ms,artists(name),is_local)),next",
            additional_types=("track",),
        )
        while page:
            for item in page["items"]:
                t = item.get("track")
                # Skip local files, podcasts, and ghost entries — no Spotify
                # ID means nothing to cache against.
                if not t or t.get("is_local") or not t.get("id"):
                    continue
                tracks.append(
                    Track(
                        id=t["id"],
                        name=t["name"],
                        artist=", ".join(a["name"] for a in t.get("artists", [])),
                        duration_ms=t.get("duration_ms") or 0,
                    )
                )
            page = self._client.next(page) if page.get("next") else None
        return tracks
