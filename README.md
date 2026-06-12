# Mashup Matcher — Design Document

**Project:** Cross-playlist harmonic compatibility tool for DJ mashup prep  
**Author:** Twig  
**Status:** Pre-implementation design  
**Stack:** Python, ottserver0

---

## Problem Statement

You have two Spotify playlists:
- **Playlist A** — neurofunk (EDM, well-catalogued, Beatport-native)
- **Playlist B** — screamo (niche, sparse metadata coverage)

You want to know: *for each track in A, which tracks in B are a plausible mashup candidate?* Specifically, tracks that are close enough in key and BPM to blend without heroic effort.

No existing tool does this cross-playlist pairing. We're building one.

---

## Goals

- For every track in Playlist A, output a ranked list of compatible tracks from Playlist B
- Compatibility defined by configurable tolerances (default: ±10% BPM, ±2 Camelot steps)
- Run fast — prioritize API lookups over local audio analysis
- Only download/analyze audio when no metadata exists elsewhere
- Produce output a DJ can actually use (Camelot wheel keys, sortable table, exportable)
- Optionally flag tracks as good stem-separation candidates for vocals

---

## Non-Goals

- Not a real-time tool — batch processing is fine
- Not doing the actual mixing or stem separation (that's a separate step)
- Not building a UI (for now — CLI + CSV/HTML output is enough)
- Not handling DRM-protected audio

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────┐
│                    MASHUP MATCHER                    │
│                                                      │
│  [1] Spotify Playlist Fetcher                        │
│       └─ Returns: track name, artist, spotify ID    │
│                        │                            │
│                        ▼                            │
│  [2] Metadata Resolver (tiered fallback)            │
│       ├─ Tier 1: GetSongBPM API     (fast, free)   │
│       ├─ Tier 2: AcousticBrainz    (free, patchy)  │
│       └─ Tier 3: Local Analysis    (slow, accurate) │
│                        │                            │
│                        ▼                            │
│  [3] Metadata Cache (SQLite)                        │
│       └─ Persists results, skips re-fetching        │
│                        │                            │
│                        ▼                            │
│  [4] Match Engine                                   │
│       └─ Scores every A×B pair by BPM + key        │
│                        │                            │
│                        ▼                            │
│  [5] Output Renderer                               │
│       ├─ CSV (for spreadsheet / Notion)            │
│       └─ HTML table (for browser review)           │
└─────────────────────────────────────────────────────┘
```

---

## Component Breakdown

### [1] Spotify Playlist Fetcher

Uses the **Spotify Web API** (Client Credentials flow — no user login needed for public playlists).

Fetches:
- Track name
- Artist(s)
- Spotify track ID
- Duration (ms) — useful as a sanity check on BPM detection

**Endpoints used:**
- `GET /playlists/{playlist_id}/tracks`

**Note:** This endpoint is *not* deprecated. Only `audio-features` is gone. We're just grabbing the track list.

**Output:** List of `Track` objects:
```python
@dataclass
class Track:
    id: str           # Spotify ID
    name: str
    artist: str
    duration_ms: int
    bpm: float | None = None
    key: int | None = None        # 0–11, Pitch class notation
    mode: int | None = None       # 0 = minor, 1 = major
    camelot: str | None = None    # e.g. "8A", "5B"
    source: str | None = None     # which tier provided the metadata
```

---

### [2] Metadata Resolver

The core of the architecture. Tries each tier in order, stops when it gets a result, caches it.

#### Tier 1 — GetSongBPM API
- **URL:** `https://api.getsong.co/search/?api_key=KEY&type=song&lookup=TITLE&artist=ARTIST`
- **Returns:** BPM, key (as string, e.g. "C#m")
- **Free**, requires API key (free registration) + backlink credit in any public UI
- **Coverage:** Good for mainstream/catalogued music. Neurofunk: likely high hit rate. Screamo: variable.
- **Speed:** Fast (JSON, no audio download)

#### Tier 2 — AcousticBrainz
- Lookup by MusicBrainz ID (requires a MusicBrainz search first to resolve MBID from track name + artist)
- **Returns:** BPM, key, key confidence score
- **Coverage:** Stopped collecting data in 2022 — use if Tier 1 misses, but don't count on it
- **Speed:** Fast, but two API calls (MusicBrainz lookup → AcousticBrainz fetch)
- May be removed in a future version if hit rate proves too low to be worth the latency

#### Tier 3 — Local Audio Analysis (librosa)
- Download audio via `yt-dlp` (searches YouTube for "ARTIST TITLE audio")
- Analyze with `librosa.beat.beat_track()` for BPM
- Analyze with `librosa.feature.chroma_cqt()` + key detection for key
- **Coverage:** If it exists on YouTube, we can analyze it. For screamo: very high likelihood.
- **Speed:** Slow — yt-dlp download + analysis is ~30–90s per track depending on length and connection
- Only triggered when Tiers 1 and 2 both return nothing

**Resolver pseudocode:**
```python
def resolve_metadata(track: Track) -> Track:
    # Check cache first
    if cached := db.get(track.id):
        return cached
    
    # Tier 1
    if result := getsongbpm_lookup(track.name, track.artist):
        track = apply_metadata(track, result, source="getsongbpm")
    
    # Tier 2
    elif result := acousticbrainz_lookup(track.name, track.artist):
        track = apply_metadata(track, result, source="acousticbrainz")
    
    # Tier 3 — last resort
    else:
        audio_path = yt_dlp_download(track.name, track.artist)
        result = librosa_analyze(audio_path)
        track = apply_metadata(track, result, source="local")
        cleanup(audio_path)  # don't hoard audio files
    
    db.save(track)
    return track
```

---

### [3] Metadata Cache

Simple **SQLite database** (fits the ottserver0 vibe — no infrastructure required).

Schema:
```sql
CREATE TABLE track_metadata (
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
```

Re-running the tool on the same playlists = instant, no re-fetching.  
Adding new songs to either playlist = only the new tracks get resolved.

---

### [4] Match Engine

Takes the fully-resolved track lists for both playlists and scores every A×B pair.

#### Key Compatibility — Camelot Wheel

The Camelot wheel maps musical keys to a clock-like system where adjacent positions mix harmonically. Compatible keys are those within N steps on the wheel.

```
Camelot position distance:
- Same position (e.g. 8A → 8A): 0 steps — perfect
- Adjacent number (e.g. 8A → 7A or 9A): 1 step — great
- Letter swap, same number (e.g. 8A → 8B): 1 step — energy shift
- 2 steps away: 2 steps — workable
- 3+ steps: probably too much harmonic clash for a mashup
```

Default tolerance: **±2 Camelot steps**

#### BPM Compatibility

Two tracks can be matched if one's BPM is within N% of the other (or its double/half — since halftime and doubletime are common mashup techniques).

```python
def bpm_compatible(bpm_a: float, bpm_b: float, tolerance: float = 0.10) -> bool:
    ratios = [1.0, 2.0, 0.5]  # normal, doubletime, halftime
    return any(
        abs(bpm_a * r - bpm_b) / bpm_b <= tolerance
        for r in ratios
    )
```

Default tolerance: **±10%**

#### Scoring

Each pair gets a compatibility score (0–100) for display:

```
score = 100
score -= camelot_distance * 20     # 0, 20, or 40 points off
score -= bpm_distance_pct * 100    # proportional to how far off BPM is
```

Pairs below a threshold score (default: 40) are excluded from output entirely.

#### Match Engine Output

```python
@dataclass
class Match:
    track_a: Track       # neurofunk track
    track_b: Track       # screamo track
    score: int
    camelot_distance: int
    bpm_ratio: float     # 1.0 = same tempo, 2.0 = doubletime, etc.
    bpm_distance_pct: float
    notes: list[str]     # e.g. ["doubletime match", "same key"]
```

---

### [5] Output Renderer

#### CSV
One row per match, sorted by track_a then score descending.

Columns: `neurofunk_track | neurofunk_artist | neurofunk_bpm | neurofunk_key | screamo_track | screamo_artist | screamo_bpm | screamo_key | score | bpm_ratio | camelot_distance | notes`

Good for importing into Notion, sorting manually, or feeding into Beatport searches.

#### HTML
Grouped by neurofunk track. Each track shows its top N screamo matches in a table.  
Color-coded by score. Print-friendly. Openable locally, no server needed.

---

## Stem Separation (Optional Future Step)

This is deliberately **out of scope for the initial tool** — doing it for all 50+ tracks upfront would be impractical and wasteful. Instead:

Once you have the match report, you'll have a short list of actually promising pairs. *Then* you run stem separation on just those tracks.

Recommended tool: **Demucs** (Meta's open-source model, runs locally, excellent vocal isolation quality).

```bash
# Example — isolate vocals from a screamo track
demucs --two-stems=vocals "track.mp3"
# outputs: track/vocals.wav + track/no_vocals.wav
```

This is a separate script/step, not integrated into Mashup Matcher v1. Could become a flag in v2: `--stems track_id`.

---

## CLI Interface

```bash
# Basic usage
python matcher.py \
  --playlist-a "1rqwZ1zl6oIvUYM0QtbSPE" \   # neurofunk
  --playlist-b "YOUR_SCREAMO_PLAYLIST_ID" \
  --output results/

# With custom tolerances
python matcher.py \
  --playlist-a "..." \
  --playlist-b "..." \
  --bpm-tolerance 0.08 \
  --camelot-tolerance 1 \
  --min-score 60 \
  --output results/

# Force re-analysis (ignore cache)
python matcher.py ... --no-cache

# Skip local analysis fallback (API-only, fast)
python matcher.py ... --api-only
```

---

## Tech Stack

| Component | Choice | Why |
|---|---|---|
| Language | Python 3.11+ | librosa ecosystem, yt-dlp, runs great on ottserver0 |
| Spotify API | `spotipy` | Well-maintained wrapper, handles auth cleanly |
| BPM/Key lookup | `requests` | Direct HTTP to GetSongBPM + AcousticBrainz |
| Audio download | `yt-dlp` | Reliable, actively maintained, handles YouTube well |
| Audio analysis | `librosa` | Industry standard for MIR, BPM + chroma detection |
| Cache | `sqlite3` (stdlib) | No dependencies, persistent, trivially portable |
| Output | `csv` (stdlib) + `jinja2` | CSV for data, Jinja for HTML template |
| Stem separation (later) | `demucs` | Best open-source vocal isolation available |

---

## Expected Performance

| Scenario | Time estimate |
|---|---|
| Both playlists fully cached | ~5 seconds |
| All tracks found via Tier 1/2 API | ~2–5 min for 100 tracks |
| 50% require Tier 3 local analysis | ~30–60 min depending on track length |
| Full local analysis, no API hits | ~2–3 hours |

The first run on a new screamo playlist will be the slow one. Every subsequent run is fast.

---

## Known Limitations

- **BPM accuracy for screamo:** Irregular rhythms, blast beats, and tempo changes can confuse librosa's beat tracker. Results may need manual verification for some tracks.
- **Key accuracy for screamo:** Heavily distorted guitars make chroma-based key detection unreliable. This is probably the biggest real limitation. Treat key matches as suggestions, not gospel.
- **YouTube availability:** Tier 3 depends on the track being findable on YouTube. Obscure releases on tiny screamo labels may not be there.
- **yt-dlp and ToS:** Using yt-dlp for analysis and then discarding the audio is a grey area. We're not distributing or keeping the files. Use for personal/private purposes only.

---

## Implementation Phases

**Phase 1 — Proof of concept**
- [ ] Spotify fetcher (playlist → track list)
- [ ] GetSongBPM integration (Tier 1)
- [ ] SQLite cache
- [ ] Match engine (BPM + Camelot scoring)
- [ ] CSV output

**Phase 2 — Fallback analysis**
- [ ] AcousticBrainz integration (Tier 2)
- [ ] yt-dlp + librosa pipeline (Tier 3)
- [ ] HTML output renderer

**Phase 3 — Quality of life**
- [ ] `--api-only` flag
- [ ] Per-track confidence indicators in output
- [ ] Demucs integration flag for flagging top match pairs
- [ ] Maybe: simple web UI via Flask so you can review matches in the browser

---

## Open Questions

1. **What's the screamo playlist ID?** We have the neurofunk one already.
2. **Do you want halftime/doubletime matching on by default?** Neurofunk at 170 BPM + screamo at 85 BPM could actually be a sick combination, but it's a big tempo manipulation.
3. **Key matching strictness:** For screamo vocals specifically, you might care less about key and more about BPM. Worth testing with `--camelot-tolerance 4` or even disabling key matching entirely for this use case.
4. **Output destination:** CSV that you import somewhere, or HTML you just open in a browser and screenshot?
