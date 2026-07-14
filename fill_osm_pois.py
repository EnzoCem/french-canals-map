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

# Per-country bbox (south, west, north, east). Used ONLY to limit query extent
# (e.g. restrict IT to the navigable north) — country attribution comes from
# the OSM admin_level=2 area filter (see area_clause), never from the bbox.
# Bboxes overlap heavily at borders; attributing by bbox mis-tagged e.g.
# Kallosluis/Antwerp and Brussels as NL.
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
    # Danube corridor only (Vienna→Budapest scope, PR #22) — like IT, the bbox
    # limits extent to the navigable reach; attribution stays area-based.
    'SK': (47.7, 16.8, 48.5, 18.9),
    'HU': (47.3, 17.2, 47.9, 19.35),
}

ALL_COUNTRIES = list(COUNTRY_BBOX.keys())

# App country code → OSM ISO3166-1 tag value, where they differ.
_APP_CC_TO_ISO = {'UK': 'GB'}

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


def area_clause(cc):
    """Overpass QL statement binding the country's admin_level=2 area to .cc.

    Selectors then use (area.cc) so hits are attributed to the country whose
    borders actually contain them, regardless of bbox overlap."""
    iso = _APP_CC_TO_ISO.get(cc, cc)
    return f'area["ISO3166-1"="{iso}"][admin_level=2]->.cc;'


def moorings_ql(cc):
    """Overpass QL for marinas / public moorings / fuel docks in country cc."""
    s, w, n, e = COUNTRY_BBOX[cc]
    return f'''[out:json][timeout:180];
{area_clause(cc)}
(
  node["leisure"="marina"](area.cc)({s},{w},{n},{e});
  way["leisure"="marina"](area.cc)({s},{w},{n},{e});
  node["mooring"~"^(yes|public|guest)$"](area.cc)({s},{w},{n},{e});
  node["waterway"="fuel"](area.cc)({s},{w},{n},{e});
);
out center tags;'''


def lock_gates_ql(cc):
    """Overpass QL for waterway lock gates in country cc."""
    s, w, n, e = COUNTRY_BBOX[cc]
    return f'''[out:json][timeout:180];
{area_clause(cc)}
(
  node["waterway"="lock_gate"](area.cc)({s},{w},{n},{e});
  node["lock"="yes"](area.cc)({s},{w},{n},{e});
);
out;'''


def riverside_towns_ql(cc):
    """Overpass QL for named villages/towns/cities in country cc."""
    s, w, n, e = COUNTRY_BBOX[cc]
    return f'''[out:json][timeout:180];
{area_clause(cc)}
(
  node["place"~"^(village|town|city)$"]["name"](area.cc)({s},{w},{n},{e});
);
out;'''


def prune_stale_osm(entries, seen_ids):
    """Drop OSM-sourced entries whose id was not returned by the sweep.

    Under bbox attribution the sweep imported POIs that lie outside all nine
    countries (e.g. French POIs inside the BE/NL bboxes); with area-scoped
    queries those are never re-fetched, so they'd linger with a wrong country
    tag. Curated entries are always kept."""
    return [e for e in entries
            if e.get('source') != 'osm' or e['id'] in seen_ids]


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


# ── Network-dependent helpers ────────────────────────────────────────────────

def _overpass_query(ql, retries=3):
    """POST an Overpass QL query, return parsed JSON. Retries on transient failure.

    Overpass returns HTTP 406 if you use python-requests's default User-Agent,
    so we identify ourselves. See fill_waterways.py for the original discovery."""
    for attempt in range(retries):
        try:
            resp = requests.post(OVERPASS_URL, data={'data': ql},
                                 headers=OVERPASS_HEADERS, timeout=180)
            resp.raise_for_status()
            return resp.json()
        except Exception as exc:
            if attempt < retries - 1:
                wait = 15 * (attempt + 1)
                print(f'    Overpass error ({exc}), retrying in {wait}s…', flush=True)
                time.sleep(wait)
            else:
                raise


def fetch_moorings_for_country(cc):
    """Fetch all "where to tie up" POIs for a country (marinas, public moorings, fuel).

    cc: 2-letter country code (must be a key of COUNTRY_BBOX).

    Returns: list of dicts shaped like data/moorings.json entries:
      { 'id': 'm_osm_<osm_id>', 'name': str, 'type': 'port'|'halte'|'fuel',
        'lat': float, 'lon': float, 'waterway': str or '',
        'cost': 'unknown', 'facilities': str, 'max_vessel': None, 'contact': '',
        'country': cc, 'source': 'osm', 'osm_id': int }"""
    data = _overpass_query(moorings_ql(cc))
    out = []
    for el in data.get('elements', []):
        if el.get('type') == 'way':
            lat = el.get('center', {}).get('lat')
            lon = el.get('center', {}).get('lon')
        else:
            lat, lon = el.get('lat'), el.get('lon')
        if lat is None or lon is None:
            continue
        tags = el.get('tags', {})
        name = tags.get('name', '').strip()
        if not name:
            # Skip unnamed POIs — they're noise; without a name the user can't
            # distinguish them from each other on the map.
            continue
        osm_id = el['id']
        out.append({
            'id': f'm_osm_{osm_id}',
            'name': name,
            'type': osm_tags_to_mooring_type(tags),
            'lat': lat, 'lon': lon,
            'waterway': tags.get('waterway') or tags.get('addr:waterway') or '',
            'cost': 'unknown',
            'facilities': osm_tags_to_facilities(tags),
            'max_vessel': None,
            'contact': (tags.get('phone') or tags.get('contact:phone') or '').strip(),
            'country': cc,
            'source': 'osm',
            'osm_id': osm_id,
        })
    return out


def fetch_lock_gates_for_country(cc):
    """Fetch waterway lock gates (the user-visible "🔒 Lock" markers) for a country.

    Returns: list of waypoint-shaped dicts with is_lock=True."""
    data = _overpass_query(lock_gates_ql(cc))
    out = []
    for el in data.get('elements', []):
        if el.get('type') != 'node':
            continue
        tags = el.get('tags', {})
        name = tags.get('name', '').strip()
        if not name:
            continue
        osm_id = el['id']
        out.append({
            'id': f'w_osm_{osm_id}',
            'name': name,
            'route': 0,       # 0 = no curated route number (Wave 5 will assign)
            'section': 0,
            'lat': el['lat'], 'lon': el['lon'],
            'is_lock': True,
            'pk': '',
            'desc': '',
            'country': cc,
            'source': 'osm',
            'osm_id': osm_id,
        })
    return out


def _load_waterway_segments():
    """Load every navigable waterway segment from waterways.geojson into a
    flat list of (lat, lon) sample points. Used for "is this town near a
    waterway?" proximity checks.

    Returns: list of (lat, lon) tuples. May be smallish if waterways.geojson
    has not yet been regenerated with EU coverage — in that case riverside
    town discovery will be sparse for non-French countries, which is OK
    (Wave 5 / future curation will catch the gaps)."""
    path = os.path.join(PROJECT_ROOT, 'waterways.geojson')
    with open(path) as f:
        gj = json.load(f)
    pts = []
    for feat in gj.get('features', []):
        geom = feat.get('geometry') or {}
        coords = geom.get('coordinates') or []
        gtype = geom.get('type')
        if gtype == 'LineString':
            for lon, lat in coords:
                pts.append((lat, lon))
        elif gtype == 'MultiLineString':
            for line in coords:
                for lon, lat in line:
                    pts.append((lat, lon))
    return pts


def _is_near_any(lat, lon, waterway_pts, radius_m=500):
    """O(N) proximity test. N is large (~50k+) but we run this once per
    candidate town (~1000 towns/country), and each test is just arithmetic —
    fast enough in pure Python."""
    for plat, plon in waterway_pts:
        if haversine_m(lat, lon, plat, plon) <= radius_m:
            return True
    return False


def fetch_riverside_towns_for_country(cc, waterway_pts):
    """Fetch villages/towns/cities within 500 m of a navigable waterway in
    waterway_pts.

    waterway_pts: list of (lat, lon) tuples from _load_waterway_segments()."""
    data = _overpass_query(riverside_towns_ql(cc))
    out = []
    skipped_far = 0
    for el in data.get('elements', []):
        if el.get('type') != 'node':
            continue
        lat = el.get('lat')
        lon = el.get('lon')
        if lat is None or lon is None:
            continue
        tags = el.get('tags', {})
        name = tags.get('name', '').strip()
        if not name:
            continue
        if not _is_near_any(lat, lon, waterway_pts):
            skipped_far += 1
            continue
        osm_id = el['id']
        out.append({
            'id': f'w_osm_{osm_id}',
            'name': name,
            'route': 0,
            'section': 0,
            'lat': lat, 'lon': lon,
            'is_lock': False,
            'pk': '',
            'desc': '',
            'country': cc,
            'source': 'osm',
            'osm_id': osm_id,
        })
    print(f'    [{cc}] {len(out)} riverside towns kept, {skipped_far} skipped (too far from any waterway)', flush=True)
    return out


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--countries', nargs='+', default=ALL_COUNTRIES,
                   choices=ALL_COUNTRIES,
                   help='Countries to fetch (default: all 9)')
    p.add_argument('--dry-run', action='store_true',
                   help='Print what would be fetched, no network or file writes')
    p.add_argument('--prune-stale', action='store_true',
                   help='After the sweep, remove OSM-sourced entries not returned '
                        'by any country query (e.g. POIs actually in France that '
                        'the old bbox attribution imported). Only applied when '
                        'sweeping ALL countries with zero fetch failures.')
    args = p.parse_args()

    if args.dry_run:
        print(f'DRY RUN — would fetch from: {", ".join(args.countries)}')
        for c in args.countries:
            print(f'  {c}: bbox {COUNTRY_BBOX[c]}')
        return

    # ── Load existing waypoints + moorings ───────────────────────────────────
    with open(WAYPOINTS_PATH) as f:
        existing_wp = json.load(f)
    with open(MOORINGS_PATH) as f:
        existing_mr = json.load(f)
    print(f'Loaded {len(existing_wp)} existing waypoints, {len(existing_mr)} existing moorings.', flush=True)

    # Curated subset (source != 'osm') for dedup purposes
    curated_wp = [w for w in existing_wp if w.get('source') != 'osm']
    curated_mr = [m for m in existing_mr if m.get('source') != 'osm']
    print(f'  Curated subset for dedup: {len(curated_wp)} waypoints, {len(curated_mr)} moorings.', flush=True)

    # Pre-load waterway sample points once (used for every country)
    waterway_pts = _load_waterway_segments()
    print(f'  Waterway sample points: {len(waterway_pts)}.', flush=True)

    # ── Track which OSM IDs we already have, to update vs append ──────────────
    existing_wp_by_id = {w['id']: w for w in existing_wp}
    existing_mr_by_id = {m['id']: m for m in existing_mr}

    # ── Per-country sweep ─────────────────────────────────────────────────────
    new_wp_total = 0
    new_mr_total = 0
    updated_wp_total = 0
    updated_mr_total = 0
    skipped_dup = 0
    fetch_failures = 0
    seen_wp_ids = set()   # every waypoint id returned this sweep (incl. dups)
    seen_mr_ids = set()

    for cc in args.countries:
        print(f'\n=== Country {cc} ===', flush=True)

        # Moorings
        try:
            moorings = fetch_moorings_for_country(cc)
        except Exception as exc:
            print(f'  [{cc}] mooring fetch FAILED ({exc}) — skipping moorings', flush=True)
            moorings = []
            fetch_failures += 1
        print(f'    [{cc}] {len(moorings)} raw mooring candidates', flush=True)

        for m in moorings:
            seen_mr_ids.add(m['id'])
            if is_duplicate_of_curated(m['name'], m['lat'], m['lon'], curated_mr):
                skipped_dup += 1
                continue
            if m['id'] in existing_mr_by_id:
                existing_mr_by_id[m['id']].update(m)
                updated_mr_total += 1
            else:
                existing_mr.append(m)
                existing_mr_by_id[m['id']] = m
                new_mr_total += 1

        time.sleep(2)

        # Lock gates
        try:
            locks = fetch_lock_gates_for_country(cc)
        except Exception as exc:
            print(f'  [{cc}] lock fetch FAILED ({exc}) — skipping locks', flush=True)
            locks = []
            fetch_failures += 1
        print(f'    [{cc}] {len(locks)} raw lock candidates', flush=True)

        for lk in locks:
            seen_wp_ids.add(lk['id'])
            if is_duplicate_of_curated(lk['name'], lk['lat'], lk['lon'], curated_wp):
                skipped_dup += 1
                continue
            if lk['id'] in existing_wp_by_id:
                existing_wp_by_id[lk['id']].update(lk)
                updated_wp_total += 1
            else:
                existing_wp.append(lk)
                existing_wp_by_id[lk['id']] = lk
                new_wp_total += 1

        time.sleep(2)

        # Riverside towns (depend on waterway_pts coverage for this country)
        try:
            towns = fetch_riverside_towns_for_country(cc, waterway_pts)
        except Exception as exc:
            print(f'  [{cc}] town fetch FAILED ({exc}) — skipping towns', flush=True)
            towns = []
            fetch_failures += 1

        for t in towns:
            seen_wp_ids.add(t['id'])
            if is_duplicate_of_curated(t['name'], t['lat'], t['lon'], curated_wp):
                skipped_dup += 1
                continue
            if t['id'] in existing_wp_by_id:
                existing_wp_by_id[t['id']].update(t)
                updated_wp_total += 1
            else:
                existing_wp.append(t)
                existing_wp_by_id[t['id']] = t
                new_wp_total += 1

        time.sleep(2)

    # ── Optional prune of stale OSM entries ───────────────────────────────────
    pruned_wp = pruned_mr = 0
    if args.prune_stale:
        if set(args.countries) != set(ALL_COUNTRIES):
            print('\n--prune-stale skipped: sweep did not cover all countries.', flush=True)
        elif fetch_failures:
            print(f'\n--prune-stale skipped: {fetch_failures} fetch(es) failed.', flush=True)
        else:
            before_wp, before_mr = len(existing_wp), len(existing_mr)
            existing_wp = prune_stale_osm(existing_wp, seen_wp_ids)
            existing_mr = prune_stale_osm(existing_mr, seen_mr_ids)
            pruned_wp = before_wp - len(existing_wp)
            pruned_mr = before_mr - len(existing_mr)

    # ── Atomic writes ─────────────────────────────────────────────────────────
    tmp_wp = WAYPOINTS_PATH + '.tmp'
    tmp_mr = MOORINGS_PATH  + '.tmp'
    with open(tmp_wp, 'w') as f:
        json.dump(existing_wp, f, indent=2, ensure_ascii=False)
    os.replace(tmp_wp, WAYPOINTS_PATH)
    with open(tmp_mr, 'w') as f:
        json.dump(existing_mr, f, indent=2, ensure_ascii=False)
    os.replace(tmp_mr, MOORINGS_PATH)

    print(f'\n=== Done ===')
    print(f'  Waypoints: +{new_wp_total} new, ~{updated_wp_total} updated, total now {len(existing_wp)}')
    print(f'  Moorings:  +{new_mr_total} new, ~{updated_mr_total} updated, total now {len(existing_mr)}')
    print(f'  Duplicates skipped: {skipped_dup}')
    if pruned_wp or pruned_mr:
        print(f'  Stale OSM entries pruned: {pruned_wp} waypoints, {pruned_mr} moorings')


if __name__ == '__main__':
    main()
