import pytest

from mashup_matcher.keys import (
    camelot_distance,
    key_name,
    parse_key_string,
    to_camelot,
)


@pytest.mark.parametrize("text,expected", [
    ("C", (0, 1)),
    ("Am", (9, 0)),
    ("C#m", (1, 0)),
    ("Ebm", (3, 0)),
    ("Db", (1, 1)),
    ("F# minor", (6, 0)),
    ("A major", (9, 1)),
    ("g", (7, 1)),
    ("bbm", (10, 0)),
    ("B♭m", (10, 0)),
])
def test_parse_key_string(text, expected):
    assert parse_key_string(text) == expected


@pytest.mark.parametrize("text", [None, "", "H", "Xm", "12", "C# something"])
def test_parse_key_string_invalid(text):
    assert parse_key_string(text) is None


@pytest.mark.parametrize("pitch,mode,expected", [
    (0, 1, "8B"),    # C major
    (9, 0, "8A"),    # A minor
    (7, 1, "9B"),    # G major
    (4, 0, "9A"),    # E minor
    (1, 0, "12A"),   # C#m
    (11, 1, "1B"),   # B major
    (8, 0, "1A"),    # G#m/Abm
    (6, 1, "2B"),    # F# major
])
def test_to_camelot(pitch, mode, expected):
    assert to_camelot(pitch, mode) == expected


def test_to_camelot_covers_all_24_keys():
    positions = {to_camelot(p, m) for p in range(12) for m in (0, 1)}
    assert len(positions) == 24


@pytest.mark.parametrize("a,b,expected", [
    ("8A", "8A", 0),
    ("8A", "7A", 1),
    ("8A", "9A", 1),
    ("8A", "8B", 1),   # letter swap
    ("8A", "10A", 2),
    ("8A", "9B", 2),
    ("1A", "12A", 1),  # wheel wraps around
    ("1A", "11A", 2),
    ("2B", "11B", 3),
])
def test_camelot_distance(a, b, expected):
    assert camelot_distance(a, b) == expected
    assert camelot_distance(b, a) == expected


def test_key_name():
    assert key_name(9, 0) == "Am"
    assert key_name(0, 1) == "C"
    assert key_name(1, 0) == "C#m"
