from mashup_matcher.engine import MatchConfig, best_bpm_ratio, find_matches, score_pair
from mashup_matcher.models import Track


def make_track(tid, bpm=None, camelot=None, key=None, mode=None, name=None):
    return Track(
        id=tid, name=name or f"track-{tid}", artist=f"artist-{tid}",
        bpm=bpm, camelot=camelot, key=key, mode=mode,
    )


def test_best_bpm_ratio_same_tempo():
    ratio, dist = best_bpm_ratio(170, 172)
    assert ratio == 1.0
    assert dist < 0.02


def test_best_bpm_ratio_doubletime():
    ratio, dist = best_bpm_ratio(85, 170)
    assert ratio == 2.0
    assert dist == 0.0


def test_best_bpm_ratio_halftime():
    ratio, dist = best_bpm_ratio(170, 85)
    assert ratio == 0.5
    assert dist == 0.0


def test_perfect_match_scores_100():
    a = make_track("a", bpm=170, camelot="8A", key=9, mode=0)
    b = make_track("b", bpm=170, camelot="8A", key=9, mode=0)
    m = score_pair(a, b, MatchConfig())
    assert m is not None
    assert m.score == 100
    assert m.camelot_distance == 0
    assert "same key" in m.notes


def test_doubletime_match_noted():
    a = make_track("a", bpm=170, camelot="8A", key=9, mode=0)
    b = make_track("b", bpm=85, camelot="8A", key=9, mode=0)
    m = score_pair(a, b, MatchConfig())
    assert m is not None
    assert m.bpm_ratio == 0.5
    assert "halftime match" in m.notes


def test_bpm_outside_tolerance_rejected():
    a = make_track("a", bpm=170)
    b = make_track("b", bpm=140)
    assert score_pair(a, b, MatchConfig()) is None


def test_camelot_outside_tolerance_rejected():
    a = make_track("a", bpm=170, camelot="8A", key=9, mode=0)
    b = make_track("b", bpm=170, camelot="3A", key=10, mode=0)
    assert score_pair(a, b, MatchConfig()) is None


def test_unknown_key_penalized_not_rejected():
    a = make_track("a", bpm=170, camelot="8A", key=9, mode=0)
    b = make_track("b", bpm=170)  # no key data
    m = score_pair(a, b, MatchConfig())
    assert m is not None
    assert m.camelot_distance is None
    assert m.score == 75
    assert "key unknown" in m.notes


def test_unresolved_track_skipped():
    a = make_track("a")  # no bpm at all
    b = make_track("b", bpm=170)
    assert score_pair(a, b, MatchConfig()) is None


def test_min_score_filter():
    a = make_track("a", bpm=170, camelot="8A", key=9, mode=0)
    b = make_track("b", bpm=180, camelot="6A", key=7, mode=0)  # 2 steps + ~5.6% bpm
    assert score_pair(a, b, MatchConfig(min_score=60)) is None
    assert score_pair(a, b, MatchConfig(min_score=40)) is not None


def test_find_matches_sorted_by_track_then_score():
    a1 = make_track("a1", bpm=170, camelot="8A", key=9, mode=0, name="Alpha")
    a2 = make_track("a2", bpm=120, camelot="5B", key=3, mode=1, name="Beta")
    b1 = make_track("b1", bpm=170, camelot="8A", key=9, mode=0)
    b2 = make_track("b2", bpm=174, camelot="7A", key=2, mode=0)
    b3 = make_track("b3", bpm=121, camelot="5B", key=3, mode=1)
    matches = find_matches([a2, a1], [b1, b2, b3])
    assert [(m.track_a.id, m.track_b.id) for m in matches] == [
        ("a1", "b1"), ("a1", "b2"), ("a2", "b3"),
    ]
    scores = [m.score for m in matches if m.track_a.id == "a1"]
    assert scores == sorted(scores, reverse=True)
