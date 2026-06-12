"""SQLite metadata cache — persists resolved track metadata across runs."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from .models import Track

_SCHEMA = """
CREATE TABLE IF NOT EXISTS track_metadata (
    spotify_id   TEXT PRIMARY KEY,
    name         TEXT,
    artist       TEXT,
    bpm          REAL,
    key_pitch    INTEGER,   -- 0-11 pitch class
    mode         INTEGER,   -- 0=minor, 1=major
    camelot      TEXT,
    source       TEXT,      -- 'getsongbpm' | 'acousticbrainz' | 'local'
    analyzed_at  TIMESTAMP
);
"""


class MetadataCache:
    def __init__(self, path: str | Path):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(path)
        self._conn.execute(_SCHEMA)
        self._conn.commit()

    def get(self, spotify_id: str) -> Track | None:
        row = self._conn.execute(
            "SELECT spotify_id, name, artist, bpm, key_pitch, mode, camelot, source"
            " FROM track_metadata WHERE spotify_id = ?",
            (spotify_id,),
        ).fetchone()
        if row is None:
            return None
        return Track(
            id=row[0], name=row[1], artist=row[2], bpm=row[3],
            key=row[4], mode=row[5], camelot=row[6], source=row[7],
        )

    def save(self, track: Track) -> None:
        self._conn.execute(
            "INSERT OR REPLACE INTO track_metadata"
            " (spotify_id, name, artist, bpm, key_pitch, mode, camelot, source, analyzed_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                track.id, track.name, track.artist, track.bpm,
                track.key, track.mode, track.camelot, track.source,
                datetime.now(timezone.utc).isoformat(),
            ),
        )
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()
