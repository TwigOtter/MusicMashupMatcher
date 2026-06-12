"""CLI entry point for Mashup Matcher."""

from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

from .cache import MetadataCache
from .engine import MatchConfig, find_matches
from .output import write_csv, write_html
from .resolver import MetadataResolver
from .spotify import SpotifyFetcher

log = logging.getLogger("mashup_matcher")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="matcher",
        description=(
            "Cross-playlist harmonic compatibility for DJ mashup prep: for every"
            " track in playlist A, find the tracks in playlist B close enough in"
            " BPM and key to blend."
        ),
    )
    parser.add_argument("--playlist-a", required=True,
                        help="Spotify playlist ID, URI, or URL for playlist A")
    parser.add_argument("--playlist-b", required=True,
                        help="Spotify playlist ID, URI, or URL for playlist B")
    parser.add_argument("--label-a", default="playlist_a",
                        help="Friendly name for playlist A in output (default: playlist_a)")
    parser.add_argument("--label-b", default="playlist_b",
                        help="Friendly name for playlist B in output (default: playlist_b)")
    parser.add_argument("--output", default="results",
                        help="Output directory for CSV/HTML reports (default: results/)")
    parser.add_argument("--bpm-tolerance", type=float, default=0.10,
                        help="Max BPM distance as a fraction, after halftime/doubletime"
                             " adjustment (default: 0.10 = ±10%%)")
    parser.add_argument("--camelot-tolerance", type=int, default=2,
                        help="Max distance in Camelot steps (default: 2)")
    parser.add_argument("--min-score", type=int, default=40,
                        help="Exclude pairs scoring below this (default: 40)")
    parser.add_argument("--no-cache", action="store_true",
                        help="Ignore cached metadata and re-resolve every track")
    parser.add_argument("--api-only", action="store_true",
                        help="Skip the slow yt-dlp/librosa local-analysis fallback")
    parser.add_argument("--cache-db", default="metadata_cache.sqlite3",
                        help="Path to the SQLite metadata cache (default: metadata_cache.sqlite3)")
    parser.add_argument("-v", "--verbose", action="store_true",
                        help="Verbose logging")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(message)s",
    )
    # Quiet down chatty third-party loggers unless -v
    if not args.verbose:
        for name in ("urllib3", "spotipy", "requests"):
            logging.getLogger(name).setLevel(logging.WARNING)

    load_dotenv()
    client_id = os.getenv("SPOTIFY_CLIENT_ID")
    client_secret = os.getenv("SPOTIFY_CLIENT_SECRET")
    getsongbpm_key = os.getenv("GETSONGBPM_API_KEY")

    if not client_id or not client_secret:
        log.error(
            "Missing Spotify credentials. Set SPOTIFY_CLIENT_ID and"
            " SPOTIFY_CLIENT_SECRET in your environment or a .env file"
            " (see .env.example)."
        )
        return 2
    if not getsongbpm_key:
        log.warning(
            "GETSONGBPM_API_KEY not set — skipping Tier 1 lookups."
            " Expect more cache misses and slower runs."
        )

    log.info("Fetching playlists from Spotify...")
    fetcher = SpotifyFetcher(client_id, client_secret)
    tracks_a = fetcher.fetch_playlist(args.playlist_a)
    tracks_b = fetcher.fetch_playlist(args.playlist_b)
    log.info("Playlist A (%s): %d tracks | Playlist B (%s): %d tracks",
             args.label_a, len(tracks_a), args.label_b, len(tracks_b))

    cache = MetadataCache(args.cache_db)
    resolver = MetadataResolver(
        cache,
        getsongbpm_key,
        use_cache=not args.no_cache,
        api_only=args.api_only,
    )
    log.info("Resolving metadata (BPM + key)...")
    tracks_a = resolver.resolve_all(tracks_a, label="A")
    tracks_b = resolver.resolve_all(tracks_b, label="B")
    cache.close()

    unresolved_a = [t for t in tracks_a if not t.resolved]
    unresolved_b = [t for t in tracks_b if not t.resolved]
    for t in unresolved_a + unresolved_b:
        log.warning("Unresolved (no BPM found): %s — %s", t.artist, t.name)

    config = MatchConfig(
        bpm_tolerance=args.bpm_tolerance,
        camelot_tolerance=args.camelot_tolerance,
        min_score=args.min_score,
    )
    matches = find_matches(tracks_a, tracks_b, config)

    out_dir = Path(args.output)
    csv_path = write_csv(matches, out_dir / "matches.csv", args.label_a, args.label_b)
    html_path = write_html(matches, out_dir / "matches.html", args.label_a, args.label_b)

    resolved_a = len(tracks_a) - len(unresolved_a)
    resolved_b = len(tracks_b) - len(unresolved_b)
    log.info("")
    log.info("Resolved %d/%d tracks in A, %d/%d in B.",
             resolved_a, len(tracks_a), resolved_b, len(tracks_b))
    log.info("Found %d compatible pairs.", len(matches))
    log.info("CSV:  %s", csv_path)
    log.info("HTML: %s", html_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
