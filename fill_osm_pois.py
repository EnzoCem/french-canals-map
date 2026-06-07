#!/usr/bin/env python3
"""
fill_osm_pois.py — Bulk-import OSM POIs (towns, lock gates, marinas, moorings,
fuel docks) for the 9 non-French countries in the Inland Europe app.

Reads existing data/waypoints.json + data/moorings.json, fetches OSM via
Overpass per-country, normalises hits into our schema, dedups against
curated entries, and writes back. Idempotent — re-running preserves
curated data and user-edited entries.

Usage:
    python3 fill_osm_pois.py                   # full run, all 9 countries
    python3 fill_osm_pois.py --countries NL DE # only specific countries
    python3 fill_osm_pois.py --dry-run         # print what would be fetched
"""
import argparse
import json
import os
import re
import sys
import time
from collections import defaultdict
from math import radians, sin, cos, sqrt, atan2

import requests

# ── Constants ────────────────────────────────────────────────────────────────

OVERPASS_URL = "https://overpass-api.de/api/interpreter"
OVERPASS_HEADERS = {
    'User-Agent': 'inland-europe-map/1.0 (https://github.com/EnzoCem/french-canals-map; contact: a.cem.ugur@gmail.com)',
    'Accept': 'application/json',
}

# Per-country bbox (south, west, north, east). Used for Overpass queries.
COUNTRY_BBOX = {
    'BE': (49.5,  2.5, 51.6,  6.5),
    'NL': (50.7,  3.3, 53.7,  7.3),
    'LU': (49.4,  5.7, 50.2,  6.6),
    'DE': (47.2,  5.8, 54.9, 15.1),
    'CH': (45.8,  5.9, 47.9, 10.5),
    'AT': (46.3,  9.5, 49.1, 17.2),
    'IT': (44.0,  6.5, 46.6, 13.6),  # northern Italy only — Po + Veneto
    'UK': (49.9, -8.5, 59.0,  1.8),
    'IE': (51.4, -10.6, 55.4, -5.9),
}

ALL_COUNTRIES = list(COUNTRY_BBOX.keys())

# Dedup proximity: if an OSM-sourced entry is within this many metres of an
# existing curated entry AND name-normalised matches, skip it.
DEDUP_RADIUS_M = 200

# Project paths
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
WAYPOINTS_PATH = os.path.join(PROJECT_ROOT, 'data', 'waypoints.json')
MOORINGS_PATH  = os.path.join(PROJECT_ROOT, 'data', 'moorings.json')


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--countries', nargs='+', default=ALL_COUNTRIES,
                   choices=ALL_COUNTRIES,
                   help='Countries to fetch (default: all 9)')
    p.add_argument('--dry-run', action='store_true',
                   help='Print what would be fetched, no network or file writes')
    args = p.parse_args()

    if args.dry_run:
        print(f'DRY RUN — would fetch from: {", ".join(args.countries)}')
        for c in args.countries:
            print(f'  {c}: bbox {COUNTRY_BBOX[c]}')
        return

    # Real work follows in later tasks.
    raise NotImplementedError('Body added in Task 8')


if __name__ == '__main__':
    main()
