# Mashup Matcher

Cross-playlist harmonic compatibility for DJ mashup prep.

Give it two Spotify playlists — any two genres — and for every track in
playlist A it finds the tracks in playlist B close enough in **BPM** and
**key** (Camelot wheel) to blend without heroic effort. Output is a CSV for
spreadsheets and a color-coded HTML report you open in a browser.

The original itch: pairing neurofunk with screamo. But it works for any
playlists A and B.

## How it works

1. **Fetch** both playlists from the Spotify Web API (public playlists, no login).
2. **Resolve** BPM + key for each track through a tiered fallback:
   - **Tier 1 — GetSongBPM API** (fast, free, needs an API key)
   - **Tier 2 — AcousticBrainz** (free, patchy — stopped collecting in 2022)
   - **Tier 3 — Local analysis** (yt-dlp download + librosa; slow last resort, audio deleted after)
3. **Cache** everything in SQLite — re-runs are instant, new tracks are incremental.
4. **Match** every A×B pair: ±10% BPM (with halftime/doubletime ratios) and
   ±2 Camelot steps by default. Each pair gets a 0–100 score.
5. **Render** `matches.csv` and `matches.html` into the output directory.

Full design rationale lives in [docs/DESIGN.md](docs/DESIGN.md).

## Setup

Python 3.11+ required.

```bash
pip install -r requirements.txt

# Optional: enables Tier 3 local audio analysis (heavy — librosa, yt-dlp)
pip install -r requirements-analysis.txt
```

Copy `.env.example` to `.env` and fill in:

| Variable | Where to get it |
|---|---|
| `SPOTIFY_CLIENT_ID` / `SPOTIFY_CLIENT_SECRET` | Create an app at [developer.spotify.com/dashboard](https://developer.spotify.com/dashboard) |
| `GETSONGBPM_API_KEY` | Free registration at [getsongbpm.com/api](https://getsongbpm.com/api) |

Without a GetSongBPM key the tool still runs, falling straight through to
Tiers 2/3 (slower, patchier).

## Usage

```bash
# Basic — playlist IDs, URLs, or spotify: URIs all work
python matcher.py \
  --playlist-a "1rqwZ1zl6oIvUYM0QtbSPE" \
  --playlist-b "https://open.spotify.com/playlist/YOUR_OTHER_PLAYLIST" \
  --output results/

# Friendly labels show up in the CSV columns and HTML report
python matcher.py --playlist-a ... --playlist-b ... \
  --label-a neurofunk --label-b screamo

# Custom tolerances
python matcher.py --playlist-a ... --playlist-b ... \
  --bpm-tolerance 0.08 \
  --camelot-tolerance 1 \
  --min-score 60

# Skip the slow local-analysis fallback (API-only, fast)
python matcher.py ... --api-only

# Ignore the cache and re-resolve everything
python matcher.py ... --no-cache
```

Run `python matcher.py --help` for the full flag list.

### Scoring

Every pair starts at 100 and loses points for distance:

- **−20 per Camelot step** (same key = 0 steps, relative major/minor or
  adjacent wheel position = 1 step, …)
- **−1 per percent of BPM distance**, measured at the best of 1×, 2×, or ½×
  tempo (halftime/doubletime blends count)
- **−25 if key is unknown** for either track (BPM-only match, flagged in notes)

Pairs outside the tolerances, or below `--min-score`, are dropped.

### Tips

- First run on an obscure playlist is the slow one (local analysis can take
  ~30–90s per track). Everything after hits the SQLite cache.
- For screamy/distorted material, key detection is unreliable — consider
  `--camelot-tolerance 4` to lean on BPM and treat key as a suggestion.
- Top pairs from the report are good candidates for stem separation with
  [Demucs](https://github.com/facebookresearch/demucs)
  (`demucs --two-stems=vocals track.mp3`) — deliberately not built in.

## Known limitations

- librosa's beat tracker can be confused by irregular rhythms, blast beats,
  and tempo changes; verify BPMs on tracks that matter.
- Chroma-based key detection struggles with heavily distorted guitars.
- Tier 3 depends on the track existing on YouTube. Audio is analyzed and
  deleted, never kept or redistributed — personal/private use only.

## Development

```bash
pip install pytest
python -m pytest tests/
```

---

Tempo & key data partly provided by [GetSongBPM](https://getsongbpm.com).
