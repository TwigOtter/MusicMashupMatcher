"""Musical key utilities: pitch-class parsing and Camelot wheel conversion."""

from __future__ import annotations

import re

# Note name -> pitch class (0-11), including enharmonic spellings.
NOTE_TO_PITCH = {
    "C": 0, "B#": 0,
    "C#": 1, "Db": 1,
    "D": 2,
    "D#": 3, "Eb": 3,
    "E": 4, "Fb": 4,
    "F": 5, "E#": 5,
    "F#": 6, "Gb": 6,
    "G": 7,
    "G#": 8, "Ab": 8,
    "A": 9,
    "A#": 10, "Bb": 10,
    "B": 11, "Cb": 11,
}

PITCH_TO_NOTE = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]

# Camelot number for each major-key tonic pitch class (8B = C major).
_MAJOR_PITCH_TO_CAMELOT_NUM = {
    0: 8,   # C
    1: 3,   # C#/Db
    2: 10,  # D
    3: 5,   # D#/Eb
    4: 12,  # E
    5: 7,   # F
    6: 2,   # F#/Gb
    7: 9,   # G
    8: 4,   # G#/Ab
    9: 11,  # A
    10: 6,  # A#/Bb
    11: 1,  # B
}

_KEY_STRING_RE = re.compile(r"^\s*([A-Ga-g])\s*([#b♯♭]?)\s*(.*?)\s*$")

_MINOR_WORDS = {"m", "min", "minor", "-"}
_MAJOR_WORDS = {"", "maj", "major", "M"}


def parse_key_string(text: str | None) -> tuple[int, int] | None:
    """Parse a key string like "C#m", "Ebm", "F", "A minor" into (pitch, mode).

    Returns None if unparseable. mode: 0 = minor, 1 = major.
    """
    if not text:
        return None
    m = _KEY_STRING_RE.match(text)
    if not m:
        return None
    letter, accidental, rest = m.groups()
    accidental = accidental.replace("♯", "#").replace("♭", "b")
    note = letter.upper() + accidental
    if note not in NOTE_TO_PITCH:
        return None
    rest_lower = rest.strip().lower()
    if rest == "M":
        mode = 1
    elif rest_lower in _MINOR_WORDS:
        mode = 0
    elif rest_lower in {w.lower() for w in _MAJOR_WORDS}:
        mode = 1
    else:
        return None
    return NOTE_TO_PITCH[note], mode


def to_camelot(pitch: int, mode: int) -> str:
    """Convert (pitch class, mode) to Camelot notation, e.g. (9, 0) -> "8A"."""
    if mode == 1:
        number = _MAJOR_PITCH_TO_CAMELOT_NUM[pitch % 12]
        return f"{number}B"
    # A minor key shares its Camelot number with its relative major
    # (3 semitones up): Am (9) -> C major (0) -> 8A.
    number = _MAJOR_PITCH_TO_CAMELOT_NUM[(pitch + 3) % 12]
    return f"{number}A"


def key_name(pitch: int, mode: int) -> str:
    """Human-readable key name, e.g. (9, 0) -> "Am"."""
    return PITCH_TO_NOTE[pitch % 12] + ("m" if mode == 0 else "")


def camelot_distance(camelot_a: str, camelot_b: str) -> int:
    """Distance between two Camelot positions.

    Circular distance around the 12-position wheel, plus 1 for a
    letter swap (relative major/minor shift).
    """
    num_a, letter_a = int(camelot_a[:-1]), camelot_a[-1]
    num_b, letter_b = int(camelot_b[:-1]), camelot_b[-1]
    diff = abs(num_a - num_b)
    wheel = min(diff, 12 - diff)
    return wheel + (0 if letter_a == letter_b else 1)
