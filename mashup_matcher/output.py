"""Output renderers: CSV (for spreadsheets) and HTML (for browser review)."""

from __future__ import annotations

import csv
from itertools import groupby
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from .keys import key_name
from .models import Match, Track

_TEMPLATE_DIR = Path(__file__).parent / "templates"


def _key_display(track: Track) -> str:
    if track.camelot and track.has_key:
        return f"{track.camelot} ({key_name(track.key, track.mode)})"
    return "?"


def write_csv(matches: list[Match], path: str | Path, label_a: str = "a", label_b: str = "b") -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            f"{label_a}_track", f"{label_a}_artist", f"{label_a}_bpm", f"{label_a}_key",
            f"{label_b}_track", f"{label_b}_artist", f"{label_b}_bpm", f"{label_b}_key",
            "score", "bpm_ratio", "camelot_distance", "notes",
        ])
        for m in matches:
            writer.writerow([
                m.track_a.name, m.track_a.artist, m.track_a.bpm, _key_display(m.track_a),
                m.track_b.name, m.track_b.artist, m.track_b.bpm, _key_display(m.track_b),
                m.score, m.bpm_ratio,
                m.camelot_distance if m.camelot_distance is not None else "",
                "; ".join(m.notes),
            ])
    return path


def write_html(
    matches: list[Match],
    path: str | Path,
    label_a: str = "Playlist A",
    label_b: str = "Playlist B",
) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    env = Environment(
        loader=FileSystemLoader(_TEMPLATE_DIR),
        autoescape=select_autoescape(["html"]),
    )
    env.filters["key_display"] = _key_display
    groups = [
        (track_a, list(group))
        for track_a, group in groupby(matches, key=lambda m: m.track_a)
    ]
    html = env.get_template("report.html.j2").render(
        groups=groups, label_a=label_a, label_b=label_b,
        total_matches=len(matches),
    )
    path.write_text(html, encoding="utf-8")
    return path
