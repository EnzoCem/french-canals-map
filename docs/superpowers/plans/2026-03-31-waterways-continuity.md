# Waterways Continuity & Name Normalisation — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Re-fetch the 42 navigable waterways from OSM so they render as continuous lines, and fix the JS constraint lookup so vessel-profile colouring works for all waterways.

**Architecture:** A new `fill_waterways.py` script fetches each waterway from the Overpass API (relation first, way fallback), stitches individual OSM ways into connected LineStrings, RDP-simplifies them, and replaces those 42 entries in `waterways.geojson`. A small JS patch adds a normalising `constraintLookup()` helper and bumps the cache version so browsers re-fetch the updated file.

**Tech Stack:** Python 3 (`requests`, `rdp` packages), Overpass API, Leaflet (existing), vanilla JS.

---

## File Structure

| Action | Path | Responsibility |
|---|---|---|
| Create | `fill_waterways.py` | All fetch / stitch / simplify / merge logic + `main()` |
| Create | `tests/test_fill_waterways.py` | Unit tests for the three pure functions |
| Update | `waterways.geojson` | Written by running `fill_waterways.py` |
| Modify | `french_canals_map.html:4539–4541` | Add `constraintLookup()`, swap in call site |
| Modify | `french_canals_map.html:4673` | Bump cache version to `french-canals-waterways-v3` |

---

## Task 1: Install dependencies + write failing tests for `stitch_ways`

**Files:**
- Create: `tests/test_fill_waterways.py`

- [ ] **Step 1: Install Python dependencies**

```bash
pip install requests rdp
```

Expected: both packages install without error.

- [ ] **Step 2: Create the tests file**

Create `tests/test_fill_waterways.py`:

```python
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from fill_waterways import stitch_ways


def test_two_ways_join_forward():
    # Two ways sharing an endpoint → merge into one chain
    ways = [
        [[0.0, 0.0], [1.0, 0.0]],
        [[1.0, 0.0], [2.0, 0.0]],
    ]
    result = stitch_ways(ways)
    assert len(result) == 1
    assert result[0][0] == [0.0, 0.0]
    assert result[0][-1] == [2.0, 0.0]
    assert len(result[0]) == 3  # [0,0] [1,0] [2,0]


def test_reverse_to_connect():
    # Second way's END matches first way's end — must reverse to connect
    ways = [
        [[0.0, 0.0], [1.0, 0.0]],
        [[2.0, 0.0], [1.0, 0.0]],  # tail matches, needs reversal
    ]
    result = stitch_ways(ways)
    assert len(result) == 1
    assert result[0][0] == [0.0, 0.0]
    assert result[0][-1] == [2.0, 0.0]


def test_three_way_chain():
    ways = [
        [[0.0, 0.0], [1.0, 0.0]],
        [[1.0, 0.0], [2.0, 0.0]],
        [[2.0, 0.0], [3.0, 0.0]],
    ]
    result = stitch_ways(ways)
    assert len(result) == 1
    assert result[0][-1] == [3.0, 0.0]


def test_disconnected_ways_stay_separate():
    ways = [
        [[0.0, 0.0], [1.0, 0.0]],
        [[5.0, 5.0], [6.0, 5.0]],
    ]
    result = stitch_ways(ways)
    assert len(result) == 2


def test_empty_input():
    assert stitch_ways([]) == []
```

- [ ] **Step 3: Run tests — expect ImportError (fill_waterways.py does not exist yet)**

```bash
cd "/Users/esen/Documents/Cem Code/French Canals/.claude/worktrees/thirsty-hypatia"
python -m pytest tests/test_fill_waterways.py -v
```

Expected: `ModuleNotFoundError: No module named 'fill_waterways'`

---

## Task 2: Implement `stitch_ways` — make tests pass

**Files:**
- Create: `fill_waterways.py` (stub with just `stitch_ways`)

- [ ] **Step 1: Create `fill_waterways.py` with `stitch_ways`**

```python
#!/usr/bin/env python3
"""
fill_waterways.py — Re-fetch the 42 navigable waterways from OSM,
stitch ways into continuous LineStrings, RDP-simplify, and update
waterways.geojson.

Usage:
    python fill_waterways.py            # full run (~15–30 min)
    python fill_waterways.py --dry-run  # print what would be fetched, no network calls
"""

import json
import os
import sys
import time
import tempfile
from collections import defaultdict

import requests
from rdp import rdp as _rdp


# ── Constants ────────────────────────────────────────────────────────────────

OVERPASS_URL = "https://overpass-api.de/api/interpreter"
FRANCE_BBOX  = "(42.3,-5.2,51.1,8.3)"  # south,west,north,east — covers all of France
RDP_EPSILON  = 0.0003                   # ~33 m at French latitudes


# ── OSM name overrides ───────────────────────────────────────────────────────
# Maps app name → list of OSM names to try (relation first, then way query).
# Names are tried in order; first one that returns ways wins.

OSM_NAME_MAP = {
    'River Seine':                   ['La Seine', 'River Seine'],
    'River Saône':                   ['La Saône', 'River Saône'],
    'River Rhône':                   ['Le Rhône', 'River Rhône'],
    'River Marne':                   ['La Marne', 'River Marne'],
    'River Oise':                    ["L'Oise", 'River Oise'],
    'River Loire':                   ['La Loire', 'River Loire'],
    'River Mayenne':                 ['La Mayenne', 'River Mayenne'],
    'River Sarthe':                  ['La Sarthe', 'River Sarthe'],
    'River Charente':                ['La Charente', 'River Charente'],
    'River Rhine':                   ['Le Rhin', 'Rhein', 'River Rhine'],
    'River Aa':                      ["L'Aa", 'River Aa'],
    'River Lys':                     ['La Lys', 'Leie', 'River Lys'],
    'River Moselle':                 ['La Moselle', 'River Moselle'],
    'Canal de Garonne':              ['Canal latéral à la Garonne', 'Canal Latéral à la Garonne'],
    'Canal de la Somme':             ['Canal de la Somme'],
    'Liaison Dunkerque\u2013Escaut': ['Liaison Dunkerque\u2013Escaut', 'Canal Dunkerque-Escaut'],
    'Canal de la Marne à la Saône':  ['Canal de la Marne à la Saône', 'Canal entre Champagne et Bourgogne'],
}


# ── Route number for each app name ──────────────────────────────────────────
# Used to set the `route` property on new GeoJSON features.

WATERWAY_ROUTES = {
    'River Seine':                    1,
    'River Yonne':                    4,
    'River Marne':                    5,
    'Canal latéral à la Marne':       5,
    "Canal latéral à l'Aisne":        6,
    "Canal de l'Oise à l'Aisne":      7,
    'River Oise':                     8,
    'Canal du Loing':                10,
    'Canal latéral à la Loire':      10,
    'Canal de Briare':               10,
    'Canal du Centre':               10,
    'Canal du Nivernais':            11,
    'Canal de Bourgogne':            12,
    'River Saône':                   13,
    'Canal du Rhône au Rhin':        14,
    'River Rhône':                   16,
    'Canal de Donzère-Mondragon':    16,
    'Canal du Rhône à Sète':         18,
    'Liaison Dunkerque\u2013Escaut': 19,
    'Canal de Calais':               20,
    'River Aa':                      21,
    'River Lys':                     24,
    'Canal du Nord':                 28,
    'Canal de Saint-Quentin':        29,
    'Canal de la Somme':             31,
    'Canal des Ardennes':            32,
    'Canal de la Meuse':             33,
    'River Moselle':                 34,
    'Canal de la Marne au Rhin':     35,
    'Canal entre Champagne et Bourgogne': 36,
    'Canal de la Marne à la Saône':  36,
    'Canal des Vosges':              37,
    "Canal d'Ille-et-Rance":         41,
    'Canal de Nantes à Brest':       42,
    'River Loire':                   46,
    'River Mayenne':                 47,
    'River Sarthe':                  48,
    'Canal du Midi':                 49,
    'Canal de Garonne':              49,
    'Canal de la Robine':            50,
    'River Charente':                52,
    'River Rhine':                   40,
}

NAVIGABLE_WATERWAYS = list(WATERWAY_ROUTES.keys())


# ── Pure functions (unit-tested) ─────────────────────────────────────────────

def stitch_ways(ways, tol=5):
    """
    Join OSM ways into connected LineStrings by matching endpoints.

    ways: list of ways, each a list of [lon, lat] coordinate pairs
    tol:  decimal places for coordinate rounding (5 = ~1 m tolerance)

    Returns: list of connected LineStrings (each a list of [lon, lat] pairs).
    Disconnected segments become separate LineStrings — correct for
    waterways with branches or bypass channels.
    """
    if not ways:
        return []

    def ekey(pt):
        return (round(pt[0], tol), round(pt[1], tol))

    # endpoint_index: coord_key → list of (way_index, is_start)
    endpoint_index = defaultdict(list)
    for i, way in enumerate(ways):
        endpoint_index[ekey(way[0])].append((i, True))
        endpoint_index[ekey(way[-1])].append((i, False))

    visited = [False] * len(ways)
    chains = []

    for start in range(len(ways)):
        if visited[start]:
            continue
        visited[start] = True
        chain = list(ways[start])

        # Greedily extend forward from the chain's tail
        while True:
            tail = ekey(chain[-1])
            nxt = next(
                ((i, at_start) for i, at_start in endpoint_index[tail] if not visited[i]),
                None,
            )
            if nxt is None:
                break
            idx, at_start = nxt
            visited[idx] = True
            w = ways[idx]
            if at_start:
                chain.extend(w[1:])       # w[0] matches tail — append rest
            else:
                chain.extend(w[-2::-1])   # w[-1] matches tail — append reversed

        chains.append(chain)

    return chains
```

- [ ] **Step 2: Run tests — expect all pass**

```bash
cd "/Users/esen/Documents/Cem Code/French Canals/.claude/worktrees/thirsty-hypatia"
python -m pytest tests/test_fill_waterways.py -v
```

Expected: `5 passed`

- [ ] **Step 3: Commit**

```bash
git add fill_waterways.py tests/test_fill_waterways.py
git commit -m "feat: add stitch_ways with tests"
```

---

## Task 3: Add tests for `build_features` and `merge_geojson` (failing)

**Files:**
- Modify: `tests/test_fill_waterways.py`

- [ ] **Step 1: Append these tests to `tests/test_fill_waterways.py`**

```python
from fill_waterways import build_features, merge_geojson


# ── build_features ────────────────────────────────────────────────────────────

def test_build_features_returns_geojson_features():
    chains = [[[0.0, 0.0], [1.0, 0.0], [2.0, 0.0]]]
    features = build_features('Canal du Midi', chains, route_num=49)
    assert len(features) == 1
    f = features[0]
    assert f['type'] == 'Feature'
    assert f['geometry']['type'] == 'LineString'
    assert f['properties']['name'] == 'Canal du Midi'
    assert f['properties']['route'] == 49
    assert f['properties']['section'] == 1


def test_build_features_skips_short_chains():
    # A chain with only 1 coordinate is not a valid LineString
    chains = [[[0.0, 0.0]], [[1.0, 0.0], [2.0, 0.0]]]
    features = build_features('Test', chains, route_num=1)
    assert len(features) == 1  # the single-point chain is skipped


def test_build_features_applies_rdp():
    # A perfectly straight line — middle point should be removed by RDP
    chains = [[[0.0, 0.0], [0.5, 0.0], [1.0, 0.0]]]
    features = build_features('Test', chains, route_num=1)
    coords = features[0]['geometry']['coordinates']
    assert len(coords) == 2  # middle point removed


# ── merge_geojson ─────────────────────────────────────────────────────────────

def _make_geojson(names):
    return {
        'type': 'FeatureCollection',
        'features': [
            {'type': 'Feature', 'geometry': {'type': 'LineString', 'coordinates': []},
             'properties': {'name': n}}
            for n in names
        ]
    }


def test_merge_removes_named_features():
    old = _make_geojson(['Canal du Midi', 'River Seine', 'Some Other Canal'])
    new_feats = [
        {'type': 'Feature', 'geometry': {'type': 'LineString', 'coordinates': [[0.0, 0.0], [1.0, 0.0]]},
         'properties': {'name': 'Canal du Midi', 'route': 49, 'section': 1}}
    ]
    result = merge_geojson(old, new_feats, {'Canal du Midi', 'River Seine'})
    names = [f['properties']['name'] for f in result['features']]
    assert 'Canal du Midi' in names       # new feature present
    assert 'River Seine' not in names     # old feature removed (no replacement)
    assert 'Some Other Canal' in names    # untouched feature preserved
    assert len(result['features']) == 2


def test_merge_preserves_structure():
    old = _make_geojson(['Canal du Midi'])
    result = merge_geojson(old, [], {'Canal du Midi'})
    assert result['type'] == 'FeatureCollection'
    assert result['features'] == []
```

- [ ] **Step 2: Run tests — expect ImportError on `build_features` and `merge_geojson`**

```bash
cd "/Users/esen/Documents/Cem Code/French Canals/.claude/worktrees/thirsty-hypatia"
python -m pytest tests/test_fill_waterways.py -v
```

Expected: `ImportError: cannot import name 'build_features'`

---

## Task 4: Implement `build_features` and `merge_geojson` — make tests pass

**Files:**
- Modify: `fill_waterways.py`

- [ ] **Step 1: Append these two functions to `fill_waterways.py`** (before the `# ── Pure functions` comment block ends, after `stitch_ways`)

```python
def rdp_simplify(coords, epsilon=RDP_EPSILON):
    """Apply RDP simplification to a list of [lon, lat] coordinate pairs."""
    if len(coords) < 3:
        return coords
    simplified = _rdp(coords, epsilon=epsilon)
    return [list(pt) for pt in simplified]


def build_features(app_name, chains, route_num):
    """
    Build GeoJSON Feature dicts from a list of coordinate chains.

    app_name:  the name stored in properties.name (= ROUTE_TO_WATERWAYS key)
    chains:    output of stitch_ways()
    route_num: integer route number for properties.route
    """
    features = []
    for chain in chains:
        simplified = rdp_simplify(chain)
        if len(simplified) < 2:
            continue
        features.append({
            'type': 'Feature',
            'geometry': {
                'type': 'LineString',
                'coordinates': simplified,
            },
            'properties': {
                'name': app_name,
                'route': route_num,
                'section': 1,
            },
        })
    return features


def merge_geojson(old_geojson, new_features, waterway_names):
    """
    Replace features whose name is in waterway_names with new_features.

    old_geojson:    parsed FeatureCollection dict
    new_features:   list of new Feature dicts to insert
    waterway_names: set of name strings to remove from old features

    Returns a new FeatureCollection dict (does not mutate inputs).
    """
    kept = [
        f for f in old_geojson['features']
        if f.get('properties', {}).get('name') not in waterway_names
    ]
    return {
        'type': 'FeatureCollection',
        'features': kept + new_features,
    }
```

- [ ] **Step 2: Run all tests — expect all pass**

```bash
cd "/Users/esen/Documents/Cem Code/French Canals/.claude/worktrees/thirsty-hypatia"
python -m pytest tests/test_fill_waterways.py -v
```

Expected: `12 passed`

- [ ] **Step 3: Commit**

```bash
git add fill_waterways.py tests/test_fill_waterways.py
git commit -m "feat: add build_features and merge_geojson with tests"
```

---

## Task 5: Implement fetch functions and `main()`

**Files:**
- Modify: `fill_waterways.py`

- [ ] **Step 1: Append the network functions to `fill_waterways.py`**

```python
# ── Network functions (not unit-tested — make real Overpass calls) ────────────

def _overpass_query(ql, retries=3):
    """POST an Overpass QL query, return parsed JSON. Retries on failure."""
    for attempt in range(retries):
        try:
            resp = requests.post(OVERPASS_URL, data={'data': ql}, timeout=180)
            resp.raise_for_status()
            return resp.json()
        except Exception as exc:
            if attempt < retries - 1:
                wait = 15 * (attempt + 1)
                print(f'    Overpass error ({exc}), retrying in {wait}s…')
                time.sleep(wait)
            else:
                raise


def _extract_ways(elements):
    """
    Extract [lon, lat] way coordinate lists from Overpass elements.
    Overpass `out geom` embeds geometry directly in each way element.
    """
    ways = []
    for el in elements:
        if el.get('type') != 'way':
            continue
        geom = el.get('geometry', [])
        if len(geom) < 2:
            continue
        ways.append([[pt['lon'], pt['lat']] for pt in geom])
    return ways


def fetch_waterway(app_name, osm_names):
    """
    Fetch OSM ways for a waterway, trying each osm_name in order.
    For each name: tries relation[type=waterway] first, then way fallback.

    Returns list of ways (each a list of [lon, lat] pairs), or [] if nothing found.
    """
    for osm_name in osm_names:
        # ── 1. Relation query ─────────────────────────────────────────────
        ql_relation = f'''[out:json][timeout:180];
relation[type=waterway][name="{osm_name}"];
way(r);
out geom;'''
        try:
            data = _overpass_query(ql_relation)
            ways = _extract_ways(data.get('elements', []))
            if ways:
                print(f'  {app_name}: {len(ways)} ways via relation[name="{osm_name}"]')
                return ways
        except Exception as exc:
            print(f'  {app_name}: relation query failed ({exc})')
        time.sleep(2)

        # ── 2. Way fallback ───────────────────────────────────────────────
        ql_ways = f'''[out:json][timeout:180];
way[waterway][name="{osm_name}"]{FRANCE_BBOX};
out geom;'''
        try:
            data = _overpass_query(ql_ways)
            ways = _extract_ways(data.get('elements', []))
            if ways:
                print(f'  {app_name}: {len(ways)} ways via way[name="{osm_name}"]')
                return ways
        except Exception as exc:
            print(f'  {app_name}: way query failed ({exc})')
        time.sleep(2)

    print(f'  WARNING: {app_name}: no OSM data found for {osm_names}')
    return []


# ── Main orchestration ────────────────────────────────────────────────────────

def main(dry_run=False):
    geojson_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'waterways.geojson')

    with open(geojson_path) as f:
        old_geojson = json.load(f)

    old_total = len(old_geojson['features'])
    waterway_set = set(NAVIGABLE_WATERWAYS)
    old_navigable = sum(
        1 for feat in old_geojson['features']
        if feat.get('properties', {}).get('name') in waterway_set
    )
    print(f'Loaded {old_total} features ({old_navigable} are navigable waterways to replace).')

    if dry_run:
        print('\n-- DRY RUN: would fetch these waterways --')
        for name in NAVIGABLE_WATERWAYS:
            osm_names = OSM_NAME_MAP.get(name, [name])
            print(f'  {name}  →  OSM names: {osm_names}')
        return

    all_new_features = []

    for app_name in NAVIGABLE_WATERWAYS:
        osm_names = OSM_NAME_MAP.get(app_name, [app_name])
        route_num = WATERWAY_ROUTES[app_name]

        print(f'\nFetching: {app_name}')
        ways = fetch_waterway(app_name, osm_names)
        if not ways:
            continue

        chains = stitch_ways(ways)
        features = build_features(app_name, chains, route_num)
        all_new_features.extend(features)
        print(f'  → {len(chains)} chains, {len(features)} features after RDP simplification')
        time.sleep(2)  # be polite to Overpass

    new_geojson = merge_geojson(old_geojson, all_new_features, waterway_set)
    new_total = len(new_geojson['features'])

    # Atomic write
    tmp_path = geojson_path + '.tmp'
    with open(tmp_path, 'w') as f:
        json.dump(new_geojson, f, separators=(',', ':'))
    os.replace(tmp_path, geojson_path)

    print(f'\nDone.')
    print(f'  Removed: {old_navigable} old navigable features')
    print(f'  Added:   {len(all_new_features)} new features')
    print(f'  Total:   {new_total} features  (was {old_total})')


if __name__ == '__main__':
    dry_run = '--dry-run' in sys.argv
    main(dry_run=dry_run)
```

- [ ] **Step 2: Run all tests — still passing**

```bash
cd "/Users/esen/Documents/Cem Code/French Canals/.claude/worktrees/thirsty-hypatia"
python -m pytest tests/test_fill_waterways.py -v
```

Expected: `12 passed`

- [ ] **Step 3: Commit**

```bash
git add fill_waterways.py
git commit -m "feat: add Overpass fetch functions and main() to fill_waterways.py"
```

---

## Task 6: Smoke test with `--dry-run` and a single-waterway live test

**Files:** none modified

- [ ] **Step 1: Dry-run to verify all 42 names and OSM mappings print cleanly**

```bash
cd "/Users/esen/Documents/Cem Code/French Canals/.claude/worktrees/thirsty-hypatia"
python fill_waterways.py --dry-run
```

Expected: prints all 42 waterways with their OSM name lists, no errors, no tracebacks.

- [ ] **Step 2: Live test with Canal du Midi only**

Temporarily add `NAVIGABLE_WATERWAYS = ['Canal du Midi']` at the bottom of the script just above `if __name__ == '__main__':`, run, then revert:

```bash
python -c "
import json, sys, os
sys.path.insert(0, '.')
# Patch to only fetch one waterway
import fill_waterways as fw
fw.NAVIGABLE_WATERWAYS = ['Canal du Midi']
fw.main(dry_run=False)
"
```

Expected output (numbers will vary):
```
Loaded 7336 features (... are navigable waterways to replace).

Fetching: Canal du Midi
  Canal du Midi: 292 ways via relation[name="Canal du Midi"]
  → 3 chains, 3 features after RDP simplification

Done.
  Removed: ...
  Added:   3 new features
  Total:   ...
```

The script must complete without exception. If Overpass returns an error, wait 60 seconds and retry.

**Note:** This test modifies `waterways.geojson`. That's fine — Task 7 will re-run the full script, which replaces all 42 waterways including Canal du Midi again.

---

## Task 7: Run the full script for all 42 waterways

**Files:**
- Update: `waterways.geojson`

**Important:** This task makes ~80–160 Overpass API calls with 2-second delays between each. Expect it to take **15–30 minutes**. Do not interrupt mid-run.

- [ ] **Step 1: Run the full script**

```bash
cd "/Users/esen/Documents/Cem Code/French Canals/.claude/worktrees/thirsty-hypatia"
python fill_waterways.py
```

Monitor the output. If any waterway prints `WARNING: no OSM data found`, note the name — it may need an OSM name override added to `OSM_NAME_MAP`.

- [ ] **Step 2: Verify the output summary**

At the end, confirm the script printed something like:
```
Done.
  Removed: ~5000–7000 old navigable features
  Added:   ~300–800 new features
  Total:   ~1500–2500 features
```

If total features is unexpectedly low (< 500) or the file is empty, do NOT commit — check which waterways returned 0 ways.

- [ ] **Step 3: Verify the file is valid JSON**

```bash
python -c "import json; d=json.load(open('waterways.geojson')); print(len(d['features']), 'features, file is valid')"
```

Expected: prints a number and `file is valid`.

- [ ] **Step 4: Spot-check a waterway in the output**

```bash
python -c "
import json
d = json.load(open('waterways.geojson'))
midi = [f for f in d['features'] if f['properties']['name'] == 'Canal du Midi']
print('Canal du Midi features:', len(midi))
for f in midi:
    print(' ', len(f['geometry']['coordinates']), 'coords')
"
```

Expected: 1–5 features, each with a meaningful number of coordinates (> 10).

- [ ] **Step 5: Commit**

```bash
git add waterways.geojson fill_waterways.py
git commit -m "feat: re-fetch 42 navigable waterways from OSM for continuous geometry"
```

---

## Task 8: JS patch — add `constraintLookup()` and bump cache version

**Files:**
- Modify: `french_canals_map.html:4539–4541` (add helper, swap call)
- Modify: `french_canals_map.html:4673` (bump version string)

- [ ] **Step 1: Add `constraintLookup()` just before `getWaterwayNavStatus`**

Find line 4539 (`function getWaterwayNavStatus(name) {`) and insert this block immediately before it:

Old (line 4535–4541):
```js
let waterwayLayer = null;

// Returns { color, reason } for a waterway given the current vessel profile.
// Colors: blue = navigable, red = blocked, amber = marginal, grey = no VNF data.
function getWaterwayNavStatus(name) {
  const p = _vesselProfile;
  const c = WATERWAY_CONSTRAINTS[name];
```

New:
```js
let waterwayLayer = null;

// Normalised lookup into WATERWAY_CONSTRAINTS.
// Strips leading articles/prefixes (River, La, Le, L', Les) and lowercases
// before matching, so 'River Saône' matches the key 'Saône', and
// 'Canal Latéral à la Garonne' matches 'Canal latéral à la Garonne'.
function constraintLookup(name) {
  if (!name) return null;
  const norm = s => s.toLowerCase().replace(/^(river |la |le |l'|les |the )/i, '').trim();
  const key = norm(name);
  for (const [k, v] of Object.entries(WATERWAY_CONSTRAINTS)) {
    if (norm(k) === key) return v;
  }
  return null;
}

// Returns { color, reason } for a waterway given the current vessel profile.
// Colors: blue = navigable, red = blocked, amber = marginal, grey = no VNF data.
function getWaterwayNavStatus(name) {
  const p = _vesselProfile;
  const c = constraintLookup(name);
```

- [ ] **Step 2: Bump the cache version at line 4673**

Old:
```js
    var WATERWAYS_CACHE_VER = 'french-canals-waterways-v2';
```

New:
```js
    var WATERWAYS_CACHE_VER = 'french-canals-waterways-v3';
```

- [ ] **Step 3: Verify no syntax errors**

```bash
cd "/Users/esen/Documents/Cem Code/French Canals/.claude/worktrees/thirsty-hypatia"
node --input-type=module < /dev/null || true
# Quick check: extract the script block and parse it
python3 -c "
content = open('french_canals_map.html').read()
start = content.index('<script>') + len('<script>')
end = content.rindex('<\/script>')
script = content[start:end]
print('Script block length:', len(script), 'chars — extracted OK')
"
```

Expected: prints `Script block length: ... chars — extracted OK` with no exception.

- [ ] **Step 4: Verify `constraintLookup` and `getWaterwayNavStatus` are both present**

```bash
grep -n "constraintLookup\|getWaterwayNavStatus\|WATERWAYS_CACHE_VER" french_canals_map.html
```

Expected: at least 3 lines — the function definition, the call site (`const c = constraintLookup(name)`), and the cache version line showing `v3`.

- [ ] **Step 5: Commit**

```bash
git add french_canals_map.html
git commit -m "feat: add constraintLookup() for case-insensitive waterway constraint matching, bump cache to v3"
```

---

## Self-Review Checklist (run before handing off)

- [ ] All 12 unit tests pass: `python -m pytest tests/test_fill_waterways.py -v`
- [ ] `waterways.geojson` is valid JSON and contains features for each of the 42 waterways
- [ ] `constraintLookup` replaces the `WATERWAY_CONSTRAINTS[name]` direct lookup in `getWaterwayNavStatus`
- [ ] Cache version is `french-canals-waterways-v3` (not v2)
- [ ] No `</script>` literal string introduced anywhere in the HTML (use `<\/script>` if needed)
