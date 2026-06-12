"""Tier 3 — local audio analysis (yt-dlp download + librosa).

Slow last resort: searches YouTube for the track, downloads the audio,
detects BPM with librosa's beat tracker and key via Krumhansl-Schmuckler
profile correlation on averaged chroma. Audio is deleted after analysis.

yt-dlp and librosa are heavy optional dependencies
(requirements-analysis.txt); everything here imports them lazily so the
rest of the tool works without them.
"""

from __future__ import annotations

import logging
import tempfile
from pathlib import Path

log = logging.getLogger(__name__)

# Krumhansl-Schmuckler key profiles (major / minor), indexed by pitch class
# relative to the tonic.
_MAJOR_PROFILE = [6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88]
_MINOR_PROFILE = [6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17]


def local_analysis_available() -> bool:
    try:
        import librosa  # noqa: F401
        import yt_dlp   # noqa: F401
        return True
    except ImportError:
        return False


def _download_audio(name: str, artist: str, dest_dir: Path) -> Path | None:
    import yt_dlp

    opts = {
        "format": "bestaudio/best",
        "outtmpl": str(dest_dir / "audio.%(ext)s"),
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "default_search": "ytsearch1",
        # Cap at ~12 minutes — anything longer is probably a mix/compilation,
        # not the track we asked for.
        "match_filter": yt_dlp.utils.match_filter_func("duration < 720"),
    }
    query = f"{artist} {name} audio"
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.download([query])
    except Exception as exc:
        log.warning("yt-dlp download failed for %s — %s: %s", artist, name, exc)
        return None
    files = list(dest_dir.glob("audio.*"))
    return files[0] if files else None


def _detect_key(chroma_mean) -> tuple[int, int]:
    """Correlate averaged chroma against all 24 rotated K-S profiles."""
    import numpy as np

    best = (-2.0, 0, 1)
    for mode, profile in ((1, _MAJOR_PROFILE), (0, _MINOR_PROFILE)):
        for tonic in range(12):
            rotated = np.roll(profile, tonic)
            corr = float(np.corrcoef(chroma_mean, rotated)[0, 1])
            if corr > best[0]:
                best = (corr, tonic, mode)
    return best[1], best[2]


def _analyze_file(path: Path) -> dict | None:
    import librosa
    import numpy as np

    y, sr = librosa.load(path, sr=22050, mono=True)
    if y.size == 0:
        return None
    tempo, _ = librosa.beat.beat_track(y=y, sr=sr)
    bpm = float(np.atleast_1d(tempo)[0])
    if bpm <= 0:
        return None
    chroma = librosa.feature.chroma_cqt(y=y, sr=sr)
    key, mode = _detect_key(chroma.mean(axis=1))
    return {"bpm": round(bpm, 1), "key": key, "mode": mode}


def local_analyze(name: str, artist: str) -> dict | None:
    """Download + analyze a track. Returns {"bpm", "key", "mode"} or None."""
    if not local_analysis_available():
        log.warning(
            "Local analysis unavailable (install requirements-analysis.txt);"
            " skipping %s — %s", artist, name,
        )
        return None
    with tempfile.TemporaryDirectory(prefix="mashup_matcher_") as tmp:
        audio = _download_audio(name, artist, Path(tmp))
        if audio is None:
            return None
        try:
            return _analyze_file(audio)
        except Exception as exc:
            log.warning("librosa analysis failed for %s — %s: %s", artist, name, exc)
            return None
        # TemporaryDirectory cleanup deletes the audio — we don't hoard files.
