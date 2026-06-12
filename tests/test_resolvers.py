from unittest.mock import MagicMock

from mashup_matcher.cache import MetadataCache
from mashup_matcher.models import Track
from mashup_matcher.resolver import MetadataResolver, apply_metadata
from mashup_matcher.resolvers.getsongbpm import getsongbpm_lookup


def fake_session(payload, status=200):
    session = MagicMock()
    response = MagicMock()
    response.status_code = status
    response.json.return_value = payload
    response.raise_for_status.return_value = None
    session.get.return_value = response
    return session


def test_getsongbpm_picks_best_candidate():
    session = fake_session({
        "search": [
            {"song_title": "Totally Different Song", "tempo": "99",
             "key_of": "C", "artist": {"name": "Someone Else"}},
            {"song_title": "Right Song", "tempo": "172.5",
             "key_of": "C#m", "artist": {"name": "Right Artist"}},
        ]
    })
    result = getsongbpm_lookup("Right Song", "Right Artist", "KEY", session=session)
    assert result == {"bpm": 172.5, "key": 1, "mode": 0}


def test_getsongbpm_no_results():
    session = fake_session({"search": {"error": "no result"}})
    assert getsongbpm_lookup("X", "Y", "KEY", session=session) is None


def test_getsongbpm_rejects_weak_match():
    session = fake_session({
        "search": [
            {"song_title": "Completely Unrelated", "tempo": "99",
             "key_of": "C", "artist": {"name": "Nobody"}},
        ]
    })
    assert getsongbpm_lookup("My Song", "My Artist", "KEY", session=session) is None


def test_getsongbpm_missing_key_still_returns_bpm():
    session = fake_session({
        "search": [
            {"song_title": "My Song", "tempo": "140",
             "key_of": None, "artist": {"name": "My Artist"}},
        ]
    })
    result = getsongbpm_lookup("My Song", "My Artist", "KEY", session=session)
    assert result == {"bpm": 140.0, "key": None, "mode": None}


def test_apply_metadata_sets_camelot():
    track = Track(id="t", name="N", artist="A")
    apply_metadata(track, {"bpm": 170.0, "key": 9, "mode": 0}, source="getsongbpm")
    assert track.camelot == "8A"
    assert track.source == "getsongbpm"


def test_resolver_uses_cache(tmp_path, monkeypatch):
    cache = MetadataCache(tmp_path / "c.sqlite3")
    cache.save(Track(id="t1", name="N", artist="A", bpm=170.0,
                     key=9, mode=0, camelot="8A", source="getsongbpm"))
    resolver = MetadataResolver(cache, "KEY")

    def boom(*args, **kwargs):
        raise AssertionError("network lookup should not run on cache hit")

    monkeypatch.setattr("mashup_matcher.resolver.getsongbpm_lookup", boom)
    resolved = resolver.resolve(Track(id="t1", name="N", artist="A"))
    assert resolved.bpm == 170.0
    assert resolved.source == "getsongbpm"
    cache.close()


def test_resolver_tier_fallthrough(tmp_path, monkeypatch):
    cache = MetadataCache(tmp_path / "c.sqlite3")
    resolver = MetadataResolver(cache, "KEY", api_only=True)

    monkeypatch.setattr(
        "mashup_matcher.resolver.getsongbpm_lookup", lambda *a, **k: None)
    monkeypatch.setattr(
        "mashup_matcher.resolver.acousticbrainz_lookup",
        lambda *a, **k: {"bpm": 120.0, "key": 0, "mode": 1})
    local_called = []
    monkeypatch.setattr(
        "mashup_matcher.resolver.local_analyze",
        lambda *a, **k: local_called.append(1))

    resolved = resolver.resolve(Track(id="t2", name="N", artist="A"))
    assert resolved.source == "acousticbrainz"
    assert resolved.camelot == "8B"
    assert not local_called

    # And the result was cached
    assert cache.get("t2").bpm == 120.0
    cache.close()


def test_resolver_api_only_skips_local(tmp_path, monkeypatch):
    cache = MetadataCache(tmp_path / "c.sqlite3")
    resolver = MetadataResolver(cache, "KEY", api_only=True)
    monkeypatch.setattr(
        "mashup_matcher.resolver.getsongbpm_lookup", lambda *a, **k: None)
    monkeypatch.setattr(
        "mashup_matcher.resolver.acousticbrainz_lookup", lambda *a, **k: None)

    def boom(*args, **kwargs):
        raise AssertionError("local analysis should not run with api_only")

    monkeypatch.setattr("mashup_matcher.resolver.local_analyze", boom)
    resolved = resolver.resolve(Track(id="t3", name="N", artist="A"))
    assert not resolved.resolved
    cache.close()
