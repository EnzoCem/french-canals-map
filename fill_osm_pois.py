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
import unicodedata
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


# ── Pure helpers ─────────────────────────────────────────────────────────────

def norm_name(s):
    """Lowercase, strip diacritics, collapse whitespace. Used for dedup."""
    if not s:
        return ''
    # Decompose accents, drop combining marks
    nfd = unicodedata.normalize('NFD', s)
    no_accents = ''.join(c for c in nfd if not unicodedata.combining(c))
    return re.sub(r'\s+', ' ', no_accents.lower().strip())


def haversine_m(lat1, lon1, lat2, lon2):
    """Great-circle distance in metres between two WGS84 points."""
    R = 6_371_000  # mean Earth radius in metres
    phi1, phi2 = radians(lat1), radians(lat2)
    dphi = radians(lat2 - lat1)
    dlambda = radians(lon2 - lon1)
    a = sin(dphi / 2) ** 2 + cos(phi1) * cos(phi2) * sin(dlambda / 2) ** 2
    return 2 * R * atan2(sqrt(a), sqrt(1 - a))


# OSM tag → our facilities code mapping.
# Codes: W (water), E (electric), S (shower), T (toilet), P (pump-out).
# We keep this order stable in the output string for visual consistency.
_FACILITY_TAG_TO_CODE = [
    ('drinking_water', 'W'),
    ('electricity',    'E'),
    ('shower',         'S'),
    ('toilets',        'T'),
    ('waste_disposal', 'P'),
]

def osm_tags_to_facilities(tags):
    """Convert an OSM tag dict to our slash-separated facility code string.

    Anything that isn't explicitly 'no' counts as present (some marinas tag
    'limited' or describe the facility — those still mean it's available)."""
    codes = []
    for tag_key, code in _FACILITY_TAG_TO_CODE:
        v = tags.get(tag_key, '').strip().lower()
        if v and v != 'no':
            codes.append(code)
    return '/'.join(codes)


def osm_tags_to_mooring_type(tags):
    """Classify an OSM-tagged mooring point into our 'port' | 'halte' | 'fuel' type.

    Order of precedence: marina (port) > fuel > anything else (halte)."""
    if tags.get('leisure') == 'marina':
        return 'port'
    if tags.get('waterway') == 'fuel':
        return 'fuel'
    return 'halte'


def is_duplicate_of_curated(name, lat, lon, curated_list, radius_m=DEDUP_RADIUS_M):
    """Return True if an entry matching (name, lat, lon) is within radius_m of
    an entry in curated_list with a normalised-name match.

    curated_list: iterable of dicts with 'name', 'lat', 'lon' keys."""
    target = norm_name(name)
    if not target:
        return False
    for c in curated_list:
        if norm_name(c.get('name')) != target:
            continue
        if haversine_m(lat, lon, c['lat'], c['lon']) <= radius_m:
            return True
    return False


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
