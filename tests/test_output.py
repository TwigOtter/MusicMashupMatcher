import csv

from mashup_matcher.engine import MatchConfig, find_matches
from mashup_matcher.models import Track
from mashup_matcher.output import write_csv, write_html


def sample_matches():
    a = Track(id="a", name="Neuro Banger", artist="DnB Guy",
              bpm=172.0, key=9, mode=0, camelot="8A")
    b1 = Track(id="b1", name="Sad Scream", artist="Emo Band",
               bpm=86.0, key=9, mode=0, camelot="8A")
    b2 = Track(id="b2", name="Mystery Track", artist="Unknown", bpm=170.0)
    return find_matches([a], [b1, b2], MatchConfig())


def test_write_csv(tmp_path):
    path = write_csv(sample_matches(), tmp_path / "out.csv", "neurofunk", "screamo")
    with open(path, newline="") as f:
        rows = list(csv.reader(f))
    assert rows[0][0] == "neurofunk_track"
    assert rows[0][4] == "screamo_track"
    assert len(rows) == 3  # header + 2 matches
    assert rows[1][0] == "Neuro Banger"
    assert rows[1][8].isdigit()


def test_write_html(tmp_path):
    path = write_html(sample_matches(), tmp_path / "out.html", "Neurofunk", "Screamo")
    html = path.read_text()
    assert "Neuro Banger" in html
    assert "Sad Scream" in html
    assert "getsongbpm.com" in html  # backlink credit required by their ToS


def test_write_html_empty(tmp_path):
    path = write_html([], tmp_path / "out.html")
    assert "No compatible pairs" in path.read_text()
