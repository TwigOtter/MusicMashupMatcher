#!/usr/bin/env python3
"""Convenience entry point: python matcher.py --playlist-a ... --playlist-b ..."""

import sys

from mashup_matcher.cli import main

if __name__ == "__main__":
    sys.exit(main())
