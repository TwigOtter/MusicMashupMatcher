from mashup_matcher.cache import MetadataCache
from mashup_matcher.models import Track


def test_roundtrip(tmp_path):
    cache = MetadataCache(tmp_path / "cache.sqlite3")
    track = Track(
        id="abc123", name="Song", artist="Artist",
        bpm=172.0, key=9, mode=0, camelot="8A", source="getsongbpm",
    )
    cache.save(track)
    loaded = cache.get("abc123")
    assert loaded is not None
    assert loaded.bpm == 172.0
    assert loaded.camelot == "8A"
    assert loaded.source == "getsongbpm"
    cache.close()


def test_miss_returns_none(tmp_path):
    cache = MetadataCache(tmp_path / "cache.sqlite3")
    assert cache.get("nope") is None
    cache.close()


def test_persists_across_connections(tmp_path):
    db = tmp_path / "cache.sqlite3"
    cache = MetadataCache(db)
    cache.save(Track(id="x", name="N", artist="A", bpm=100.0))
    cache.close()

    cache2 = MetadataCache(db)
    loaded = cache2.get("x")
    assert loaded is not None and loaded.bpm == 100.0
    cache2.close()
