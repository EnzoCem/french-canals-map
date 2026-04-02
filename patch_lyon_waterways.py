#!/usr/bin/env python3
"""
patch_lyon_waterways.py — Fetch Canal de Miribel, Canal de Jonage, and the
missing Rhône segments through Lyon, then add them to waterways.geojson.

Usage:
    python3 patch_lyon_waterways.py
"""

import json
import os
import sys
import time

import requests
from rdp import rdp as _rdp

OVERPASS_URL = "https://overpass-api.de/api/interpreter"
RDP_EPSILON  = 0.0003  # ~33 m, same as fill_waterways.py

# Waterways to fetch (app_name, osm_names, route_num)
TARGETS = [
    ('Canal de Miribel',  ['Canal de Miribel'],   16),
    ('Canal de Jonage',   ['Canal de Jonage'],     16),
    # Rhône through Lyon — fetch by bbox to get the gap through the city
    ('River Rhône',       ['Le Rhône', 'River Rhône'], 16),
]

# Bounding box for the Lyon area (slightly wider than the gap)
LYON_BBOX = "(45.55,4.75,45.90,5.20)"  # south,west,north,east


def _overpass_query(ql, retries=3):
    for attempt in range(retries):
        try:
            resp = requests.post(OVERPASS_URL, data={'data': ql}, timeout=180)
            resp.raise_for_status()
            return resp.json()
        except Exception as exc:
            if attempt < retries - 1:
                wait = 15 * (attempt + 1)
                print(f'  Overpass error ({exc}), retrying in {wait}s…')
                time.sleep(wait)
            else:
                raise


def _extract_ways(elements):
    ways = []
    for el in elements:
        if el.get('type') != 'way':
            continue
        geom = el.get('geometry', [])
        if len(geom) < 2:
            continue
        ways.append([[pt['lon'], pt['lat']] for pt in geom])
    return ways


def fetch_by_name_bbox(osm_names, bbox):
    """Fetch waterway ways by name within a bounding box."""
    for osm_name in osm_names:
        ql = f'''[out:json][timeout:180];
way[waterway][name="{osm_name}"]{bbox};
out geom;'''
        try:
            data = _overpass_query(ql)
            ways = _extract_ways(data.get('elements', []))
            if ways:
                print(f'  Found {len(ways)} ways for "{osm_name}" in bbox')
                return ways
        except Exception as exc:
            print(f'  Query failed for "{osm_name}": {exc}')
        time.sleep(2)
    return []


def fetch_by_relation(osm_names):
    """Fetch waterway ways via relation query (whole waterway, not bbox-limited)."""
    for osm_name in osm_names:
        ql = f'''[out:json][timeout:180];
relation[type=waterway][name="{osm_name}"];
way(r);
out geom;'''
        try:
            data = _overpass_query(ql)
            ways = _extract_ways(data.get('elements', []))
            if ways:
                print(f'  Found {len(ways)} ways via relation for "{osm_name}"')
                return ways
        except Exception as exc:
            print(f'  Relation query failed for "{osm_name}": {exc}')
        time.sleep(2)
    return []


def stitch_ways(ways, tol=5):
    from collections import defaultdict
    if not ways:
        return []

    def ekey(pt):
        return (round(pt[0], tol), round(pt[1], tol))

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
                chain.extend(w[1:])
            else:
                chain.extend(w[-2::-1])

        chains.append(chain)

    return chains


def rdp_simplify(coords):
    if len(coords) < 3:
        return coords
    simplified = _rdp(coords, epsilon=RDP_EPSILON)
    return [list(pt) for pt in simplified]


def main():
    geojson_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'waterways.geojson')
    if not os.path.exists(geojson_path):
        sys.exit(f'ERROR: {geojson_path} not found.')

    with open(geojson_path) as f:
        geojson = json.load(f)

    old_count = len(geojson['features'])
    print(f'Loaded waterways.geojson: {old_count} features\n')

    new_features = []

    # ── Canal de Miribel ────────────────────────────────────────────────────
    print('Fetching Canal de Miribel...')
    ways = fetch_by_relation(['Canal de Miribel'])
    if not ways:
        print('  Trying bbox query...')
        ways = fetch_by_name_bbox(['Canal de Miribel'], LYON_BBOX)
    if ways:
        chains = stitch_ways(ways)
        for chain in chains:
            s = rdp_simplify(chain)
            if len(s) >= 2:
                new_features.append({
                    'type': 'Feature',
                    'geometry': {'type': 'LineString', 'coordinates': s},
                    'properties': {'name': 'Canal de Miribel', 'route': 16, 'section': 4},
                })
        print(f'  → {len(chains)} chains added for Canal de Miribel')
    else:
        print('  WARNING: No data found for Canal de Miribel')
    time.sleep(2)

    # ── Canal de Jonage ─────────────────────────────────────────────────────
    print('\nFetching Canal de Jonage...')
    ways = fetch_by_relation(['Canal de Jonage'])
    if not ways:
        print('  Trying bbox query...')
        ways = fetch_by_name_bbox(['Canal de Jonage'], LYON_BBOX)
    if ways:
        chains = stitch_ways(ways)
        for chain in chains:
            s = rdp_simplify(chain)
            if len(s) >= 2:
                new_features.append({
                    'type': 'Feature',
                    'geometry': {'type': 'LineString', 'coordinates': s},
                    'properties': {'name': 'Canal de Jonage', 'route': 16, 'section': 4},
                })
        print(f'  → {len(chains)} chains added for Canal de Jonage')
    else:
        print('  WARNING: No data found for Canal de Jonage')
    time.sleep(2)

    # ── River Rhône through Lyon (bbox-only to fill the gap) ────────────────
    print('\nFetching River Rhône through Lyon (gap fill)...')
    # Use bbox query to get only the Lyon segment, avoiding duplicate full-river re-fetch
    ways = fetch_by_name_bbox(['Le Rhône', 'River Rhône', 'Rhône'], LYON_BBOX)
    if ways:
        chains = stitch_ways(ways)
        for chain in chains:
            s = rdp_simplify(chain)
            if len(s) >= 2:
                new_features.append({
                    'type': 'Feature',
                    'geometry': {'type': 'LineString', 'coordinates': s},
                    'properties': {'name': 'River Rhône', 'route': 16, 'section': 4},
                })
        print(f'  → {len(chains)} chains added for River Rhône (Lyon segment)')
    else:
        print('  WARNING: No Rhône data found in Lyon bbox')

    if not new_features:
        print('\nNo new features to add. Exiting.')
        return

    # Add new features to geojson (don't remove existing River Rhône — just append)
    geojson['features'].extend(new_features)
    new_count = len(geojson['features'])

    tmp_path = geojson_path + '.tmp'
    with open(tmp_path, 'w') as f:
        json.dump(geojson, f, separators=(',', ':'))
    os.replace(tmp_path, geojson_path)

    print(f'\nDone. Added {len(new_features)} new features.')
    print(f'Total: {old_count} → {new_count} features')


if __name__ == '__main__':
    main()
