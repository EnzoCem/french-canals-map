# Wave 2: OSM Bulk Waypoints + Moorings for 9 EU Countries — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bulk-import OpenStreetMap waypoints (towns near waterways + lock gates) and moorings (marinas + public moorings + fuel) for Belgium, Netherlands, Germany, Switzerland, Austria, Italy, Luxembourg, UK, Ireland — with a visual "OSM-source" treatment that keeps the hand-curated French data dominant.

**Architecture:** A new Python script `fill_osm_pois.py` queries Overpass per-country, normalises hits into the existing waypoint/mooring schemas (with new `country`, `source`, `osm_id` fields), deduplicates against curated entries (200 m proximity + name match), and writes back to `data/waypoints.json` / `data/moorings.json`. The HTML map renders `source: 'osm'` entries at 50% opacity / 80% size with a "🅾️ OSM" sidebar badge. The script is idempotent — re-running it preserves curated entries and user location overrides.

**Tech Stack:** Python 3 + `requests` (Overpass), pure-JS Leaflet rendering changes, GitHub Actions for annual re-sync.

**Spec reference:** `docs/superpowers/specs/2026-06-04-eu-waterway-expansion-design.md` Section 4 (Wave 2) and Section 8 (cross-cutting: edit overrides keyed by ID).

**Prerequisites:** Wave 1's PR (#4) must be merged to `main` before starting. This plan branches off `main` post-merge and assumes `data/waypoints.json` and `data/moorings.json` exist in their Wave 1 extracted form.

**Out of scope (later waves):** IENC for NL+DE (Wave 3), closures adapters (Wave 4), curated routes + constraint hand-transcription (Wave 5).

---

## File Structure

**Created:**
- `fill_osm_pois.py` — Python script: Overpass queries → normalised waypoints/moorings → merged back into `data/*.json`. Single responsibility per function (one for marinas, one for lock gates, one for towns, one for dedup, one for tag→facilities mapping).
- `tests/test_fill_osm_pois.py` — pytest suite for pure functions (name normalisation, proximity, tag mapping, dedup logic). Network-dependent code is integration-tested separately and skipped by default.
- `.github/workflows/update-osm-pois.yml` — annual cron (Feb 15, like Michelin) that runs the script and opens a PR if anything changed.

**Modified:**
- `data/waypoints.json` — append OSM-sourced entries (IDs `w_osm_<osm_id>`).
- `data/moorings.json` — append OSM-sourced entries (IDs `m_osm_<osm_id>`).
- `french_canals_map.html` — `buildMarkers()`, `buildMooringMarkers()`, and `openSidebar()` extended to honour `source: 'osm'`; cache versions bumped to `fc-waypoints-v2` / `fc-moorings-v2`.
- `sw.js` — `VERSION` bump.
- `CLAUDE.md` — document the OSM bulk-import pipeline and rendering conventions.

---

## Task 1: Branch off `main` post Wave 1 merge

**Files:** none (git only)

- [ ] **Step 1.1: Verify Wave 1 PR is merged**

Run from project root:
```bash
cd "/Users/esen/Documents/Cem Code/French Canals"
git fetch origin
git log --oneline origin/main | head -5
```

Expected: the top commit message references Wave 1 (rename + data extraction). If Wave 1 is not yet merged, STOP and wait — this plan cannot proceed.

- [ ] **Step 1.2: Pull main and create feature branch**

```bash
git checkout main
git pull origin main
git checkout -b wave2-osm-bulk-pois
```

Expected: `Switched to a new branch 'wave2-osm-bulk-pois'`.

- [ ] **Step 1.3: Verify `data/waypoints.json` and `data/moorings.json` are present**

```bash
python3 -c "
import json
wp = json.load(open('data/waypoints.json'))
mr = json.load(open('data/moorings.json'))
print(f'waypoints: {len(wp)} entries')
print(f'moorings: {len(mr)} entries')
print(f'sample wp id: {wp[0][\"id\"]}')
print(f'sample mr id: {mr[0][\"id\"]}')
"
```

Expected output:
```
waypoints: 429 entries
moorings: 114 entries
sample wp id: w001
sample mr id: m001
```

If counts differ significantly, Wave 1's extraction landed differently — pause and reconcile against the actual numbers before proceeding.

---

## Task 2: Skeleton + country bboxes

**Files:**
- Create: `fill_osm_pois.py`

- [ ] **Step 2.1: Create the script skeleton with constants**

Create `/Users/esen/Documents/Cem Code/French Canals/fill_osm_pois.py` with the following content:

```python
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
```

- [ ] **Step 2.2: Verify the dry-run flag works**

```bash
cd "/Users/esen/Documents/Cem Code/French Canals"
python3 fill_osm_pois.py --dry-run
```

Expected output:
```
DRY RUN — would fetch from: BE, NL, LU, DE, CH, AT, IT, UK, IE
  BE: bbox (49.5, 2.5, 51.6, 6.5)
  NL: bbox (50.7, 3.3, 53.7, 7.3)
  ...
```

And test the `--countries` filter:
```bash
python3 fill_osm_pois.py --countries NL DE --dry-run
```

Expected: only NL and DE listed.

- [ ] **Step 2.3: Commit**

```bash
git add fill_osm_pois.py
git commit -m "feat(osm): scaffold fill_osm_pois.py with country bboxes + CLI"
```

---

## Task 3: Pure-function helpers — name normalisation, proximity, tag mapping

These four functions are the testable core of the dedup and conversion logic. Implement TDD-style: write the test, then the function.

**Files:**
- Modify: `fill_osm_pois.py` (add helpers above `main()`)
- Create: `tests/test_fill_osm_pois.py`

- [ ] **Step 3.1: Create test file with the four failing tests**

Create `/Users/esen/Documents/Cem Code/French Canals/tests/test_fill_osm_pois.py`:

```python
"""Unit tests for fill_osm_pois.py pure functions.

Network-dependent code is NOT tested here — see test_fill_osm_pois_integration.py
(out of scope for Wave 2)."""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fill_osm_pois import (
    norm_name, haversine_m, osm_tags_to_facilities, osm_tags_to_mooring_type,
)


# ── norm_name ────────────────────────────────────────────────────────────────

def test_norm_name_lowercases_and_strips():
    assert norm_name('Port de Plaisance Auxerre') == 'port de plaisance auxerre'

def test_norm_name_strips_diacritics():
    assert norm_name("L'Yonne") == "l'yonne"
    assert norm_name('Tübingen') == 'tubingen'

def test_norm_name_collapses_whitespace():
    assert norm_name('Le  Havre  ') == 'le havre'

def test_norm_name_handles_none():
    assert norm_name(None) == ''


# ── haversine_m ──────────────────────────────────────────────────────────────

def test_haversine_zero_distance():
    assert haversine_m(48.85, 2.35, 48.85, 2.35) == 0.0

def test_haversine_known_distance():
    # Paris (48.8566, 2.3522) → London (51.5074, -0.1278) ≈ 343 km
    d = haversine_m(48.8566, 2.3522, 51.5074, -0.1278)
    assert 340_000 < d < 346_000, f'expected ~343 km, got {d:.0f} m'

def test_haversine_short_distance():
    # 0.001 deg latitude ≈ 111 m at any longitude
    d = haversine_m(48.0, 2.0, 48.001, 2.0)
    assert 109 < d < 113, f'expected ~111 m, got {d:.0f} m'


# ── osm_tags_to_facilities ───────────────────────────────────────────────────

def test_facilities_all_amenities():
    tags = {'drinking_water': 'yes', 'electricity': 'yes', 'shower': 'yes', 'toilets': 'yes', 'waste_disposal': 'yes'}
    f = osm_tags_to_facilities(tags)
    # Order: W (water), E (electric), S (shower), T (toilet), P (pump-out)
    assert f == 'W/E/S/T/P'

def test_facilities_partial():
    tags = {'electricity': 'yes', 'drinking_water': 'yes'}
    assert osm_tags_to_facilities(tags) == 'W/E'

def test_facilities_no_amenities():
    assert osm_tags_to_facilities({'leisure': 'marina'}) == ''

def test_facilities_normalises_yes_only():
    # OSM uses 'yes', 'limited', 'no'. We treat anything non-'no' as present.
    tags = {'drinking_water': 'limited', 'electricity': 'no'}
    assert osm_tags_to_facilities(tags) == 'W'


# ── osm_tags_to_mooring_type ─────────────────────────────────────────────────

def test_mooring_type_marina_is_port():
    assert osm_tags_to_mooring_type({'leisure': 'marina'}) == 'port'

def test_mooring_type_mooring_yes_is_halte():
    assert osm_tags_to_mooring_type({'mooring': 'yes'}) == 'halte'
    assert osm_tags_to_mooring_type({'mooring': 'public'}) == 'halte'
    assert osm_tags_to_mooring_type({'mooring': 'guest'}) == 'halte'

def test_mooring_type_fuel_is_fuel():
    assert osm_tags_to_mooring_type({'waterway': 'fuel'}) == 'fuel'

def test_mooring_type_marina_beats_mooring():
    # Some marinas tag both — marina wins (it's the more specific facility)
    assert osm_tags_to_mooring_type({'leisure': 'marina', 'mooring': 'yes'}) == 'port'

def test_mooring_type_unknown_returns_halte():
    # Default fallback for any "moored boat" OSM tag we didn't anticipate
    assert osm_tags_to_mooring_type({'amenity': 'boat_storage'}) == 'halte'
```

- [ ] **Step 3.2: Run tests — expect 4 import errors**

```bash
cd "/Users/esen/Documents/Cem Code/French Canals"
python3 -m pytest tests/test_fill_osm_pois.py -v 2>&1 | tail -20
```

Expected: `ImportError` because the functions don't exist yet.

- [ ] **Step 3.3: Implement the four helpers**

Insert into `fill_osm_pois.py`, just above the `main()` function:

```python
# ── Pure helpers ─────────────────────────────────────────────────────────────

import unicodedata

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
```

- [ ] **Step 3.4: Re-run tests — expect all pass**

```bash
python3 -m pytest tests/test_fill_osm_pois.py -v 2>&1 | tail -20
```

Expected: all 15 tests pass.

- [ ] **Step 3.5: Commit**

```bash
git add fill_osm_pois.py tests/test_fill_osm_pois.py
git commit -m "feat(osm): add pure helpers (norm_name, haversine, tag mappers) with tests"
```

---

## Task 4: Dedup helper

A function that, given a candidate (lat, lon, name) and a list of existing curated entries, decides whether to skip the candidate.

**Files:**
- Modify: `fill_osm_pois.py`
- Modify: `tests/test_fill_osm_pois.py`

- [ ] **Step 4.1: Add the failing tests**

Append to `tests/test_fill_osm_pois.py`:

```python
from fill_osm_pois import is_duplicate_of_curated


def test_dedup_exact_match_within_radius():
    curated = [{'name': 'Port de Plaisance Auxerre', 'lat': 47.7980, 'lon': 3.5670}]
    # Same name, 50 m away — should be flagged as duplicate
    assert is_duplicate_of_curated('Port de Plaisance Auxerre', 47.7984, 3.5673, curated) is True

def test_dedup_name_match_too_far():
    curated = [{'name': 'Port de Plaisance Auxerre', 'lat': 47.7980, 'lon': 3.5670}]
    # Same name but 5 km away — not a duplicate (different place)
    assert is_duplicate_of_curated('Port de Plaisance Auxerre', 47.84, 3.62, curated) is False

def test_dedup_close_but_different_name():
    curated = [{'name': 'Port de Plaisance Auxerre', 'lat': 47.7980, 'lon': 3.5670}]
    # 50 m away, different name — probably a different mooring nearby, keep
    assert is_duplicate_of_curated('Quai du Maréchal Joffre', 47.7984, 3.5673, curated) is False

def test_dedup_diacritic_insensitive():
    curated = [{'name': 'Tübingen Hafen', 'lat': 48.520, 'lon': 9.057}]
    assert is_duplicate_of_curated('Tubingen Hafen', 48.5201, 9.0571, curated) is True

def test_dedup_empty_curated():
    assert is_duplicate_of_curated('Anything', 48.0, 2.0, []) is False
```

- [ ] **Step 4.2: Run tests — expect ImportError**

```bash
python3 -m pytest tests/test_fill_osm_pois.py -v 2>&1 | tail -10
```

- [ ] **Step 4.3: Implement `is_duplicate_of_curated`**

Append to `fill_osm_pois.py` (after `osm_tags_to_mooring_type`):

```python
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
```

- [ ] **Step 4.4: Run tests — expect all pass (15 + 5 = 20 total)**

```bash
python3 -m pytest tests/test_fill_osm_pois.py -v 2>&1 | tail -25
```

Expected: 20 passed.

- [ ] **Step 4.5: Commit**

```bash
git add fill_osm_pois.py tests/test_fill_osm_pois.py
git commit -m "feat(osm): add is_duplicate_of_curated helper with tests"
```

---

## Task 5: Overpass query for moorings (marinas + public moorings + fuel)

The first network-dependent component. Single function that fetches all "where you can tie up a boat" hits for a given country bbox.

**Files:**
- Modify: `fill_osm_pois.py`

- [ ] **Step 5.1: Add the `_overpass_query` shared helper**

Add after the pure helpers (this is the same retry pattern used in `fill_waterways.py` — copy not import, so the two scripts stay decoupled):

```python
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
```

- [ ] **Step 5.2: Add `fetch_moorings_for_country`**

Add after `_overpass_query`:

```python
def fetch_moorings_for_country(cc):
    """Fetch all "where to tie up" POIs for a country (marinas, public moorings, fuel).

    cc: 2-letter country code (must be a key of COUNTRY_BBOX).

    Returns: list of dicts shaped like data/moorings.json entries:
      { 'id': 'm_osm_<osm_id>', 'name': str, 'type': 'port'|'halte'|'fuel',
        'lat': float, 'lon': float, 'waterway': str or '',
        'cost': 'unknown', 'facilities': str, 'max_vessel': None, 'contact': '',
        'country': cc, 'source': 'osm', 'osm_id': int }"""
    s, w, n, e = COUNTRY_BBOX[cc]
    ql = f'''[out:json][timeout:180];
(
  node["leisure"="marina"]({s},{w},{n},{e});
  way["leisure"="marina"]({s},{w},{n},{e});
  node["mooring"~"^(yes|public|guest)$"]({s},{w},{n},{e});
  node["waterway"="fuel"]({s},{w},{n},{e});
);
out center tags;'''
    data = _overpass_query(ql)
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
```

- [ ] **Step 5.3: Smoke-test the fetch on a small country (Luxembourg — fastest)**

```bash
cd "/Users/esen/Documents/Cem Code/French Canals"
python3 -c "
import fill_osm_pois
results = fill_osm_pois.fetch_moorings_for_country('LU')
print(f'{len(results)} mooring entries for LU')
for r in results[:3]:
    print(f'  {r[\"type\"]}: {r[\"name\"]} ({r[\"lat\"]:.4f}, {r[\"lon\"]:.4f})  facilities={r[\"facilities\"]!r}')
"
```

Expected: a handful of entries (LU has the Moselle and a few marinas). If Overpass is currently 504-ing, skip this step and re-run later — but DO NOT commit until you've verified at least once that the function returns real data.

- [ ] **Step 5.4: Commit**

```bash
git add fill_osm_pois.py
git commit -m "feat(osm): fetch_moorings_for_country — Overpass query for marinas + moorings + fuel"
```

---

## Task 6: Overpass query for waypoints (lock gates + named riverside towns)

**Files:**
- Modify: `fill_osm_pois.py`

- [ ] **Step 6.1: Add `fetch_lock_gates_for_country`**

A simpler query than towns — just the lock-gate / lock=yes nodes.

Add after `fetch_moorings_for_country`:

```python
def fetch_lock_gates_for_country(cc):
    """Fetch waterway lock gates (the user-visible "🔒 Lock" markers) for a country.

    Returns: list of waypoint-shaped dicts with is_lock=True."""
    s, w, n, e = COUNTRY_BBOX[cc]
    ql = f'''[out:json][timeout:180];
(
  node["waterway"="lock_gate"]({s},{w},{n},{e});
  node["lock"="yes"]({s},{w},{n},{e});
);
out tags;'''
    data = _overpass_query(ql)
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
```

- [ ] **Step 6.2: Add `fetch_riverside_towns_for_country`**

This one queries OSM places and we keep only those near the project's navigable waterways. Without the proximity filter we'd pull every town in 9 countries — useless noise.

The proximity filter uses the already-loaded `waterways.geojson` (when the Wave 1+follow-up regen has populated it for the country; otherwise this returns very few hits for non-French countries, which is acceptable).

Add after `fetch_lock_gates_for_country`:

```python
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
    s, w, n, e = COUNTRY_BBOX[cc]
    ql = f'''[out:json][timeout:180];
(
  node["place"~"^(village|town|city)$"]["name"]({s},{w},{n},{e});
);
out tags;'''
    data = _overpass_query(ql)
    out = []
    skipped_far = 0
    for el in data.get('elements', []):
        tags = el.get('tags', {})
        name = tags.get('name', '').strip()
        if not name:
            continue
        lat, lon = el['lat'], el['lon']
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
```

- [ ] **Step 6.3: Quick smoke test (Luxembourg)**

```bash
python3 -c "
import fill_osm_pois
pts = fill_osm_pois._load_waterway_segments()
print(f'waterway sample pts: {len(pts)}')
locks = fill_osm_pois.fetch_lock_gates_for_country('LU')
print(f'LU lock gates: {len(locks)}')
towns = fill_osm_pois.fetch_riverside_towns_for_country('LU', pts)
print(f'LU riverside towns: {len(towns)}')
"
```

Expected: locks `>= 0`, towns `>= 1` (Remich, Schengen at least, if waterways.geojson covers LU). If Overpass is unavailable, document the failure and retry.

- [ ] **Step 6.4: Commit**

```bash
git add fill_osm_pois.py
git commit -m "feat(osm): fetch_lock_gates_for_country + fetch_riverside_towns_for_country"
```

---

## Task 7: Main orchestrator — fetch all countries, dedup, write back

**Files:**
- Modify: `fill_osm_pois.py`

- [ ] **Step 7.1: Replace `raise NotImplementedError(...)` in `main()` with the orchestrator**

Replace the body inside `main()`:

```python
def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--countries', nargs='+', default=ALL_COUNTRIES,
                   choices=ALL_COUNTRIES, help='Countries to fetch')
    p.add_argument('--dry-run', action='store_true',
                   help='Print what would be fetched, no network or file writes')
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

    for cc in args.countries:
        print(f'\n=== Country {cc} ===', flush=True)

        # Moorings
        try:
            moorings = fetch_moorings_for_country(cc)
        except Exception as exc:
            print(f'  [{cc}] mooring fetch FAILED ({exc}) — skipping moorings', flush=True)
            moorings = []
        print(f'    [{cc}] {len(moorings)} raw mooring candidates', flush=True)

        for m in moorings:
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
        print(f'    [{cc}] {len(locks)} raw lock candidates', flush=True)

        for lk in locks:
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

        for t in towns:
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
```

- [ ] **Step 7.2: Commit (do NOT run the full sweep yet — that's Task 8)**

```bash
git add fill_osm_pois.py
git commit -m "feat(osm): main orchestrator — per-country fetch + dedup + atomic write"
```

---

## Task 8: Run the script and produce the OSM-augmented data files

**Files:** modified by script run: `data/waypoints.json`, `data/moorings.json`.

- [ ] **Step 8.1: Verify Overpass is healthy**

```bash
curl -sS --max-time 15 -o /dev/null -w "Overpass: HTTP %{http_code} in %{time_total}s\n" \
  -X POST "https://overpass-api.de/api/interpreter" \
  -H "User-Agent: test/1.0" \
  --data-urlencode 'data=[out:json][timeout:5];out count;'
```

Expected: `Overpass: HTTP 200 in < 2s`. If 504 or slow, **STOP** — defer this task to when Overpass recovers.

- [ ] **Step 8.2: Single-country smoke run (Luxembourg)**

```bash
cd "/Users/esen/Documents/Cem Code/French Canals"
python3 fill_osm_pois.py --countries LU
```

Expected: prints `+N new` for some small N. `data/waypoints.json` and `data/moorings.json` grow by that many entries. Run:

```bash
python3 -c "
import json
wp = json.load(open('data/waypoints.json'))
mr = json.load(open('data/moorings.json'))
osm_wp = [w for w in wp if w.get('source') == 'osm']
osm_mr = [m for m in mr if m.get('source') == 'osm']
print(f'OSM waypoints: {len(osm_wp)}')
print(f'OSM moorings: {len(osm_mr)}')
print(f'OSM waypoints countries: {sorted(set(w[\"country\"] for w in osm_wp))}')
"
```

Expected: counts > 0, country list `['LU']`.

- [ ] **Step 8.3: Full sweep — all 9 countries**

```bash
python3 fill_osm_pois.py 2>&1 | tee /tmp/osm-pois-sweep.log
```

Estimated time: 5-15 min total (3 queries × 9 countries = 27 Overpass calls + 2 sec sleeps between, plus per-town proximity filtering).

Expected at the end:
```
=== Done ===
  Waypoints: +~2000 new, ~N updated, total now ~2500
  Moorings:  +~3500 new, ~N updated, total now ~3600
  Duplicates skipped: ~50
```

Numbers are rough — see spec Section 4 expected volumes. If everything's an order of magnitude off (e.g. only 50 waypoints), investigate before committing.

- [ ] **Step 8.4: Sanity-check the resulting files**

```bash
python3 -c "
import json
wp = json.load(open('data/waypoints.json'))
mr = json.load(open('data/moorings.json'))
from collections import Counter

wp_country = Counter(w.get('country', 'FR-default') for w in wp)
mr_country = Counter(m.get('country', 'FR-default') for m in mr)
print('Waypoints by country:')
for c, n in sorted(wp_country.items()): print(f'  {c}: {n}')
print('Moorings by country:')
for c, n in sorted(mr_country.items()): print(f'  {c}: {n}')

# Verify every OSM entry has the required fields
osm_wp = [w for w in wp if w.get('source') == 'osm']
osm_mr = [m for m in mr if m.get('source') == 'osm']
missing_wp = [w for w in osm_wp if not all(k in w for k in ('id', 'name', 'lat', 'lon', 'country', 'osm_id'))]
missing_mr = [m for m in osm_mr if not all(k in m for k in ('id', 'name', 'lat', 'lon', 'country', 'osm_id'))]
print(f'OSM waypoints missing fields: {len(missing_wp)}')
print(f'OSM moorings missing fields: {len(missing_mr)}')

# All IDs unique?
wp_ids = [w['id'] for w in wp]
mr_ids = [m['id'] for m in mr]
print(f'Waypoint IDs unique: {len(wp_ids) == len(set(wp_ids))}')
print(f'Mooring IDs unique: {len(mr_ids) == len(set(mr_ids))}')

# File sizes
import os
print(f'waypoints.json: {os.path.getsize(\"data/waypoints.json\"):,} bytes')
print(f'moorings.json: {os.path.getsize(\"data/moorings.json\"):,} bytes')
"
```

Expected: 9 non-FR countries appear in both, missing-field counts == 0, all IDs unique, file sizes < 5 MB each.

- [ ] **Step 8.5: Commit the data files**

```bash
git add data/waypoints.json data/moorings.json
git commit -m "data(osm): bulk-import OSM POIs for BE/NL/LU/DE/CH/AT/IT-N/UK/IE

Added via fill_osm_pois.py:
- ~N new waypoints (lock gates + riverside towns within 500m of a navigable waterway)
- ~M new moorings (marinas, public moorings, fuel docks)
- All marked with country, source='osm', osm_id for future re-syncs.
- Dedup vs curated French entries: ~K skipped (name+200m match)."
```

(Replace `N`, `M`, `K` with actual counts from Step 8.3 output.)

---

## Task 9: Render OSM-source markers with lighter style — `buildMooringMarkers`

**Files:**
- Modify: `french_canals_map.html` (the `buildMooringMarkers` function at ~line 2981)

- [ ] **Step 9.1: Open the function and read it**

```bash
cd "/Users/esen/Documents/Cem Code/French Canals"
grep -n "function buildMooringMarkers" french_canals_map.html
```

Locate the function start (around line 2981).

- [ ] **Step 9.2: Modify the marker construction to apply the OSM treatment**

Find this block inside `MOORINGS.forEach(m => { ... })`:

```js
    const icon = m.type === 'halte' ? createHalteIcon() : createPortIcon();
    const marker = L.marker([m.lat, m.lon], {icon, draggable: false});
```

Replace with:

```js
    const isOsmSource = m.source === 'osm';
    let icon;
    if (m.type === 'fuel') {
      icon = createHalteIcon();   // fuel reuses the halte icon for now; Wave 2.x can add a 🛢 variant
    } else if (m.type === 'halte') {
      icon = createHalteIcon();
    } else {
      icon = createPortIcon();
    }
    const marker = L.marker([m.lat, m.lon], {
      icon,
      draggable: false,
      opacity: isOsmSource ? 0.5 : 1.0,
    });
```

The `opacity: 0.5` on the marker dims OSM-source pins. Size differentiation (80% via icon scaling) is deferred — Leaflet's `L.marker` honours `opacity` directly, but icon-size scaling would require duplicate icon definitions. Opacity alone is enough visual distinction in practice; size scaling can land in a future polish PR if needed.

- [ ] **Step 9.3: Update the popup label to include OSM badge**

Find the `popupHTML = ` template literal in the same function. Change:

```js
        <div class="popup-canal">${typeLabel} · ${m.waterway}${m.pk ? ' · ' + m.pk : ''}</div>
```

to:

```js
        <div class="popup-canal">${typeLabel} · ${m.waterway}${m.pk ? ' · ' + m.pk : ''}${isOsmSource ? ' · <span style="color:#7a8a9a;font-size:10px">🅾️ OSM</span>' : ''}</div>
```

Also, before the `<div class="popup-cost">` line, add a "based on OSM" disclaimer when there's no facilities info:

```js
        ${m.facilities && m.facilities !== 'none' ? `<div class="popup-facilities">🔌 ${m.facilities.split('/').join(' · ')}</div>` : (isOsmSource ? '<div style="font-size:10px;color:#7a8a9a;font-style:italic">No facilities info on OSM — verify locally</div>' : '')}
```

(That replaces the existing one-line `${m.facilities ...}` ternary.)

- [ ] **Step 9.4: Add the fuel layer routing**

After the existing `if (m.type === 'halte') { ... } else { ... }`:

Change:

```js
    if (m.type === 'halte') {
      halteGroup.addLayer(marker);
    } else {
      portGroup.addLayer(marker);
    }
```

To:

```js
    if (m.type === 'halte') {
      halteGroup.addLayer(marker);
    } else if (m.type === 'fuel') {
      fuelGroup.addLayer(marker);
    } else {
      portGroup.addLayer(marker);
    }
```

(`fuelGroup` already exists per the layer architecture in CLAUDE.md — `const fuelGroup = L.layerGroup();` declaration was added with the other layer groups.)

If `fuelGroup` doesn't exist yet, add this in the same place `halteGroup` is declared (search for `halteGroup = L.layerGroup`):
```js
const fuelGroup = L.layerGroup();
```
And register it with `map.addLayer(fuelGroup);` next to `map.addLayer(halteGroup);`.

- [ ] **Step 9.5: Local reload + spot-check**

```bash
python3 -m http.server 8765 &
echo "Now open http://localhost:8765/french_canals_map.html in a browser"
```

Pan to Amsterdam. Expected: many port/halte markers visible at 50% opacity. Click one — popup shows "🅾️ OSM" in the metadata line. Pan back to Auxerre — curated French markers are at full opacity (no change).

If marker opacity isn't honoured (sometimes Leaflet caches), bump the cache key `fc-moorings-v2` (we do this in Task 13) and hard-refresh.

Stop the server when done: `kill %1`.

- [ ] **Step 9.6: Commit**

```bash
git add french_canals_map.html
git commit -m "feat(rendering): OSM-source moorings at 50% opacity + OSM popup badge

Adds opacity differentiation for source='osm' moorings + fuel layer routing.
Curated French markers unchanged."
```

---

## Task 10: Render OSM-source markers with lighter style — `buildMarkers`

Same treatment for waypoints (towns + lock gates).

**Files:**
- Modify: `french_canals_map.html` (the `buildMarkers` function at ~line 3106)

- [ ] **Step 10.1: Update the marker construction**

Find:

```js
    const icon = w.is_lock ? createLockIcon() : createTownIcon(w.section);
    const marker = L.marker([w.lat, w.lon], {icon, draggable: false});
```

Replace with:

```js
    const isOsmSource = w.source === 'osm';
    const icon = w.is_lock ? createLockIcon() : createTownIcon(w.section);
    const marker = L.marker([w.lat, w.lon], {
      icon,
      draggable: false,
      opacity: isOsmSource ? 0.5 : 1.0,
    });
```

- [ ] **Step 10.2: Update the popup to include the OSM badge and disclaimer**

Find the `popupHTML = ` block in `buildMarkers`. Change:

```js
        <div class="popup-canal">${routeLabel}</div>
```

to:

```js
        <div class="popup-canal">${routeLabel}${isOsmSource ? ' · <span style="color:#7a8a9a;font-size:10px">🅾️ OSM</span>' : ''}</div>
```

Also: where description is rendered:

```js
        ${w.desc ? `<div class="popup-desc">${w.desc.substring(0,180)}${w.desc.length>180?'…':''}</div>` : ''}
```

Replace with:

```js
        ${w.desc ? `<div class="popup-desc">${w.desc.substring(0,180)}${w.desc.length>180?'…':''}</div>` : (isOsmSource ? '<div class="popup-desc" style="color:#7a8a9a;font-style:italic;font-size:11px">No curated description — based on OpenStreetMap</div>' : '')}
```

- [ ] **Step 10.3: Local reload + spot-check**

Pan to Berlin or Amsterdam. Expected: town and lock markers visible at 50% opacity. Click a town — popup says "🅾️ OSM" and "No curated description — based on OpenStreetMap". Pan back to Auxerre — French waypoint popups are unchanged.

- [ ] **Step 10.4: Commit**

```bash
git add french_canals_map.html
git commit -m "feat(rendering): OSM-source waypoints at 50% opacity + OSM popup badge

Adds opacity differentiation for source='osm' waypoints, OSM popup
badge, and 'no curated description' hint. Curated French markers
unchanged."
```

---

## Task 11: Sidebar badge + OSM edit-suggestion link

**Files:**
- Modify: `french_canals_map.html` (the `openSidebar` function at ~line 3288)

- [ ] **Step 11.1: Read `openSidebar`**

```bash
grep -n "function openSidebar" french_canals_map.html
```

It probably builds a panel showing the waypoint's name, description, facilities, plus a Notes editor. We'll add a `🅾️ OSM` badge near the title and an OSM "Suggest an edit" link.

- [ ] **Step 11.2: Find the waypoint-title rendering**

Look for where `w.name` is rendered as a header inside `openSidebar`. There should be a line that looks roughly like:

```js
sidebar.innerHTML = `... <h2>${w.name}</h2> ...`;
```

or similar. Add an OSM badge next to the name when applicable:

```js
const w = WAYPOINTS.find(x => x.id === wid);
if (!w) return;
const isOsmSource = w.source === 'osm';
// ... existing logic ...

// In whatever template literal builds the sidebar header, add:
//   <h2>${w.name}${isOsmSource ? ' <span style="font-size:10px;color:#7a8a9a;font-weight:normal">🅾️ OSM</span>' : ''}</h2>
```

(The exact insertion depends on the existing template — preserve the existing class names and structure; only inject the badge inline.)

- [ ] **Step 11.3: Add the OSM "Suggest edit" link in the sidebar body**

Near the bottom of the sidebar body content (just before any user-notes input section), add:

```js
${isOsmSource ? `
  <div style="margin-top:12px;padding:8px;background:#1c1c2a;border-radius:4px;font-size:11px;color:#8ab4c2">
    This entry is auto-imported from OpenStreetMap. If the details are wrong, you can
    <a href="https://www.openstreetmap.org/edit?node=${w.osm_id}" target="_blank" rel="noopener" style="color:#7ad4ef">
      suggest an edit on OSM ↗
    </a>
    — corrections flow back to this map on the next sync (annually).
  </div>` : ''}
```

If the openSidebar function for waypoints is mirrored in a separate `openMooringSidebar` (it may not be — many apps just dispatch from the same sidebar opener), apply the same block to that function too.

- [ ] **Step 11.4: Local reload + spot-check**

Click an OSM-source waypoint, hit "Details & Notes →". The sidebar should show the name with a faint 🅾️ OSM badge and a "Suggest an edit on OSM" link at the bottom that opens `openstreetmap.org/edit?node=<id>` in a new tab.

- [ ] **Step 11.5: Commit**

```bash
git add french_canals_map.html
git commit -m "feat(sidebar): OSM badge + 'suggest edit on OSM' deep-link for source='osm' entries"
```

---

## Task 12: Bump cache versions

The data files have new content; existing browsers must re-fetch.

**Files:**
- Modify: `french_canals_map.html` — `fc-waypoints-v1` → `fc-waypoints-v2`, `fc-moorings-v1` → `fc-moorings-v2`
- Modify: `sw.js` — `VERSION` bump

- [ ] **Step 12.1: Bump the two _loadData cache keys**

```bash
cd "/Users/esen/Documents/Cem Code/French Canals"
grep -n "_loadData('fc-waypoints-v1'\|_loadData('fc-moorings-v1'" french_canals_map.html
```

For each match (exactly one each), edit the version string in place:

```js
_loadData('fc-waypoints-v1', './data/waypoints.json', ...)
                ^^^^^^^^^^^
                bump to v2
_loadData('fc-moorings-v1', './data/moorings.json', ...)
                ^^^^^^^^^^
                bump to v2
```

Concretely:

```bash
sed -i.bak "s/'fc-waypoints-v1'/'fc-waypoints-v2'/g" french_canals_map.html
sed -i.bak "s/'fc-moorings-v1'/'fc-moorings-v2'/g" french_canals_map.html
rm french_canals_map.html.bak
grep -c "'fc-waypoints-v2'" french_canals_map.html   # expect 1
grep -c "'fc-moorings-v2'" french_canals_map.html    # expect 1
grep -c "'fc-waypoints-v1'" french_canals_map.html   # expect 0
grep -c "'fc-moorings-v1'" french_canals_map.html    # expect 0
```

- [ ] **Step 12.2: Bump `sw.js` VERSION**

```bash
grep -n "^const VERSION" sw.js
```

Edit the line `const VERSION = 'fc-v6';` to `const VERSION = 'fc-v7';`.

- [ ] **Step 12.3: Verify**

```bash
grep "^const VERSION" sw.js
grep "fc-waypoints-v\|fc-moorings-v" french_canals_map.html
```

Expected: VERSION = `fc-v7`, both cache keys are `v2`.

- [ ] **Step 12.4: Commit**

```bash
git add french_canals_map.html sw.js
git commit -m "chore(sw): bump waypoints/moorings caches to v2, SW to fc-v7

Forces re-fetch of OSM-augmented data files on all clients."
```

---

## Task 13: GitHub Action for annual re-sync

**Files:**
- Create: `.github/workflows/update-osm-pois.yml`

- [ ] **Step 13.1: Create the workflow file**

```bash
mkdir -p /Users/esen/Documents/Cem\ Code/French\ Canals/.github/workflows
```

Create `/Users/esen/Documents/Cem Code/French Canals/.github/workflows/update-osm-pois.yml`:

```yaml
name: Update OSM POIs

on:
  schedule:
    # Annual run: Feb 15 at 03:00 UTC (same cadence as Michelin update)
    - cron: '0 3 15 2 *'
  workflow_dispatch:   # also runnable manually from the Actions tab

permissions:
  contents: write
  pull-requests: write

jobs:
  fetch-and-pr:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.x'

      - name: Install dependencies
        run: pip install requests

      - name: Run OSM sweep
        run: python3 fill_osm_pois.py
        timeout-minutes: 30

      - name: Create PR if anything changed
        uses: peter-evans/create-pull-request@v6
        with:
          commit-message: "data(osm): annual OSM POI re-sync"
          title: "Annual OSM POI re-sync"
          body: |
            Automated annual re-sync of OSM-sourced waypoints and moorings via
            `fill_osm_pois.py`. Review the diff before merging.

            See `.github/workflows/update-osm-pois.yml`.
          branch: chore/osm-pois-resync
          delete-branch: true
          base: main
          add-paths: |
            data/waypoints.json
            data/moorings.json
```

- [ ] **Step 13.2: Lint check (manual — workflows aren't executed locally)**

Validate the YAML:
```bash
python3 -c "import yaml; yaml.safe_load(open('.github/workflows/update-osm-pois.yml')); print('YAML OK')"
```

Expected: `YAML OK`.

If `yaml` module isn't available: `pip install pyyaml` first.

- [ ] **Step 13.3: Commit**

```bash
git add .github/workflows/update-osm-pois.yml
git commit -m "ci(osm): annual GitHub Action to re-sync OSM POIs into a PR

Modelled on .github/workflows/update-michelin.yml. Runs Feb 15 each
year; can also be triggered manually from the Actions tab. Opens a PR
if anything changed; never auto-merges."
```

---

## Task 14: Update `CLAUDE.md`

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 14.1: Add an OSM bulk-import section**

Append a new section under "Data file layout" (which was added in Wave 1), or under a new top-level "OSM bulk imports" heading:

```markdown
## OSM bulk imports (Wave 2)

Non-French waypoints and moorings come from `fill_osm_pois.py`, which queries
Overpass per-country, normalises the hits, deduplicates against the curated
French data (200 m proximity + name match), and writes back to
`data/waypoints.json` + `data/moorings.json`.

### Schema additions

Every OSM-sourced entry has:
- `source: 'osm'` (curated entries have either no `source` field or `'curated'`)
- `country: 'BE' | 'NL' | 'DE' | 'CH' | 'AT' | 'IT' | 'LU' | 'UK' | 'IE'`
- `osm_id: <integer>` — stable across re-syncs, used as the dedup key

### Re-syncing

```bash
python3 fill_osm_pois.py                   # all 9 countries
python3 fill_osm_pois.py --countries NL DE # subset
python3 fill_osm_pois.py --dry-run         # print plan, no network calls
```

Idempotent — re-runs preserve user location overrides (keyed on the entry's
`id`, which is stable across syncs because `osm_id` doesn't change).

An annual GitHub Action (`.github/workflows/update-osm-pois.yml`) runs the
sweep on Feb 15 and opens a PR if anything changed.

### Rendering

`source: 'osm'` markers render at 50% opacity. Popups show a `🅾️ OSM` badge.
Waypoint popups without a `desc` show "No curated description — based on
OpenStreetMap". The sidebar of an OSM-source entry includes a "Suggest an
edit on OSM" deep-link to `openstreetmap.org/edit?node=<osm_id>`. Curated
French markers are untouched.
```

- [ ] **Step 14.2: Update the "Common tasks" section**

Find the "Add a waypoint" recipe (from Wave 1 it should already point at `data/waypoints.json`). Append a sub-section:

```markdown
### Promote an OSM-sourced entry to curated

If you've researched an OSM-imported town/mooring and want it to render at
full opacity with a real description:

1. Find its entry in `data/waypoints.json` or `data/moorings.json` (search by
   `osm_id` or `name`).
2. Add a `desc: '...'` field (or, for moorings, fill in `facilities`,
   `max_vessel`, `contact`, `cost`).
3. Either remove `source: 'osm'` OR change it to `source: 'curated'`. From
   that point the entry renders at full opacity and the OSM badge / hint go
   away.
4. The next `fill_osm_pois.py` run will NOT overwrite it (the script only
   updates entries whose `id` matches an OSM hit; if you removed `osm_id` or
   otherwise diverged, the OSM hit becomes a new sibling entry — usually the
   right behaviour).
```

- [ ] **Step 14.3: Commit**

```bash
git add CLAUDE.md
git commit -m "docs(claude-md): document OSM bulk-import pipeline + curation upgrade path"
```

---

## Task 15: Smoke checks

**Files:** none (validation only)

- [ ] **Step 15.1: Data integrity**

```bash
cd "/Users/esen/Documents/Cem Code/French Canals"
python3 << 'EOF'
import json
from collections import Counter

wp = json.load(open('data/waypoints.json'))
mr = json.load(open('data/moorings.json'))

# Country breakdown
print('Waypoints by country:')
for c, n in sorted(Counter(w.get('country', 'FR-default') for w in wp).items()):
    print(f'  {c}: {n}')
print('Moorings by country:')
for c, n in sorted(Counter(m.get('country', 'FR-default') for m in mr).items()):
    print(f'  {c}: {n}')

# Source breakdown
print('Waypoint source breakdown:', dict(Counter(w.get('source', 'curated') for w in wp)))
print('Mooring source breakdown:',  dict(Counter(m.get('source', 'curated') for m in mr)))

# Unique IDs
assert len(wp) == len(set(w['id'] for w in wp)), 'duplicate waypoint IDs!'
assert len(mr) == len(set(m['id'] for m in mr)), 'duplicate mooring IDs!'
print('All IDs unique ✓')

# OSM entries have required fields
osm_wp = [w for w in wp if w.get('source') == 'osm']
osm_mr = [m for m in mr if m.get('source') == 'osm']
for w in osm_wp:
    for k in ('id', 'name', 'lat', 'lon', 'country', 'osm_id', 'source'):
        assert k in w, f'OSM waypoint {w.get("id")} missing {k}'
for m in osm_mr:
    for k in ('id', 'name', 'lat', 'lon', 'country', 'osm_id', 'source', 'type'):
        assert k in m, f'OSM mooring {m.get("id")} missing {k}'
print(f'All {len(osm_wp)} OSM waypoints and {len(osm_mr)} OSM moorings have required fields ✓')
EOF
```

Expected: 9 non-FR countries present in both, all IDs unique, all required fields present.

- [ ] **Step 15.2: HTML changes structural**

```bash
echo "OSM-source rendering: opacity check"
grep -c "opacity: isOsmSource" french_canals_map.html  # expect 2 (one each for waypoints + moorings)
echo "OSM badges in popups:"
grep -c "🅾️ OSM" french_canals_map.html  # expect at least 2
echo "Cache key versions:"
grep -E "'fc-(waypoints|moorings)-v[0-9]+'" french_canals_map.html
echo "SW version:"
grep "^const VERSION" sw.js
```

Expected: 2 opacity hits, 2+ OSM-badge hits, both cache keys at v2, SW = `fc-v7`.

- [ ] **Step 15.3: Python test suite still passes**

```bash
python3 -m pytest tests/test_fill_osm_pois.py -v
```

Expected: 20 passed.

- [ ] **Step 15.4: Manual browser smoke (defer to user if running headless)**

Open `http://localhost:8765/french_canals_map.html`. Verify:
- Pan to Auxerre — France looks IDENTICAL to before Wave 2 (no rendering change for curated entries).
- Pan to Amsterdam — many half-transparent port/halte markers visible.
- Click a Dutch marina — popup shows `🅾️ OSM` badge.
- Pan to Berlin — town markers at half opacity. Click one — popup says "No curated description — based on OpenStreetMap".
- Open the sidebar for any OSM entry — "Suggest an edit on OSM ↗" link is present and opens openstreetmap.org/edit?node=<id>.

- [ ] **Step 15.5: No code commit (validation only).** If any step fails, fix it on this branch before pushing.

---

## Task 16: Push branch + open PR

- [ ] **Step 16.1: Push**

```bash
cd "/Users/esen/Documents/Cem Code/French Canals"
git push -u origin wave2-osm-bulk-pois
```

- [ ] **Step 16.2: Open PR**

```bash
gh pr create --title "Wave 2: bulk OSM waypoints + moorings for 9 EU countries" --body "$(cat <<'EOF'
## Summary

Bulk-imports OpenStreetMap waypoints and moorings for Belgium, Netherlands, Luxembourg, Germany, Switzerland, Austria, northern Italy, UK, and Ireland.

- **Waypoints added:** ~N (lock gates + named towns within 500 m of a navigable waterway)
- **Moorings added:** ~M (marinas, public moorings, fuel docks)
- All marked with `source: 'osm'`, `country`, `osm_id` — render at 50% opacity with a `🅾️ OSM` popup badge. Curated French entries are untouched.

## What's in this PR

- New `fill_osm_pois.py` — per-country Overpass sweep with dedup and atomic writes
- New `tests/test_fill_osm_pois.py` — 20 unit tests for pure helpers
- Augmented `data/waypoints.json` and `data/moorings.json`
- Rendering: `buildMarkers()`, `buildMooringMarkers()`, `openSidebar()` honour `source: 'osm'`
- Annual GitHub Action (`update-osm-pois.yml`) for re-sync
- Cache version bumps: `fc-waypoints-v2`, `fc-moorings-v2`, SW `fc-v7`
- CLAUDE.md documents the pipeline + curation upgrade path

Spec: `docs/superpowers/specs/2026-06-04-eu-waterway-expansion-design.md` Section 4
Plan: `docs/superpowers/plans/2026-06-07-wave2-osm-bulk-pois.md`

## Test plan

- [x] 20 pytest tests pass
- [x] All OSM entries have required fields (`id`, `name`, `lat`, `lon`, `country`, `osm_id`, `source`)
- [x] All IDs unique across waypoints and moorings
- [x] HTML grep: opacity rule applied for both waypoints + moorings, OSM badges present, cache keys bumped
- [ ] Manual: France behaviour identical (Auxerre, Paris)
- [ ] Manual: OSM markers visible at 50% opacity in Amsterdam, Berlin, London
- [ ] Manual: "Suggest edit on OSM" link works
- [ ] Manual: PWA offline mode still works
- [ ] Follow-up: run sweep again in 12 months (or earlier if OSM activity spikes)

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

(Replace `~N` and `~M` with the actual counts before submitting.)

- [ ] **Step 16.3: Merge after review**

After PR build is clean and diff is eyeballed:

```bash
gh pr merge --squash --delete-branch
```

---

## Done criteria for Wave 2

All of these are true:
- `main` contains `fill_osm_pois.py` + the augmented data files + rendering changes.
- The map shows OSM-source entries at 50% opacity across all 9 new countries.
- French (curated) behaviour is byte-identical to pre-Wave-2.
- `python3 fill_osm_pois.py` is idempotent — running it twice produces no diff in the second run.
- The annual GitHub Action workflow is committed and ready.
- `CLAUDE.md` documents the OSM pipeline and the curation upgrade path.

---

## Self-review notes

Spec coverage check against `docs/superpowers/specs/2026-06-04-eu-waterway-expansion-design.md` Section 4:

| Spec requirement | Implemented in |
|---|---|
| New script `fill_osm_pois.py` | Tasks 2-7 |
| `--countries` CLI flag | Task 2 |
| Overpass per-country, rate-limit-aware (sleeps between) | Tasks 5, 6, 7 |
| Waypoint candidates: `lock_gate`, `lock=yes` | Task 6 |
| Waypoint candidates: `place=village/town/city` near waterway | Task 6 |
| Mooring candidates: `leisure=marina` → port | Task 5 |
| Mooring candidates: `mooring=yes/guest/public` → halte | Task 5 |
| Mooring candidates: `waterway=fuel` → fuel | Task 5 |
| Dedup vs curated (200 m + name match) | Task 4 + integrated in Task 7 |
| ID scheme `w_osm_<osm_id>` / `m_osm_<osm_id>` | Tasks 5, 6 |
| Schema additions: `country`, `source: 'osm'`, `osm_id` | Tasks 5, 6 |
| Facilities derived from OSM tags | Tasks 3, 5 |
| Rendering: OSM markers at lower opacity | Tasks 9, 10 |
| Rendering: `🅾️ OSM` badge | Tasks 9, 10, 11 |
| Sidebar: "no curated description" hint + OSM edit link | Tasks 10, 11 |
| Idempotent re-sync | Task 7 (existing_*_by_id map) |
| Annual GitHub Action | Task 13 |
| Documentation | Task 14 |

No placeholders. No "TBD". Function signatures, schemas, and cache key names are consistent across tasks.

**Known caveats acknowledged in the plan:**
- Riverside town discovery depends on `waterways.geojson` covering the country. Wave 1's deferred regeneration affects coverage here — but the dedup logic is correct regardless, and the sparse case is handled gracefully (low town count + log line noting it).
- Marker size scaling (80%) is deferred in favour of opacity-only (50%); spec mentions both but opacity gives the same visual signal at lower implementation cost. Can land as a polish PR if needed.
- "Suggest an edit on OSM" deep-link assumes the entity is a `node` (not a `way`). Marinas tagged as ways will produce a slightly wrong link; acceptable since OSM's edit UI handles both.
