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
        if (f.get('properties') or {}).get('name') not in waterway_names
    ]
    return {
        'type': 'FeatureCollection',
        'features': kept + new_features,
    }


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

    if not os.path.exists(geojson_path):
        sys.exit(f'ERROR: {geojson_path} not found. Run this script from the project root.')

    with open(geojson_path) as f:
        old_geojson = json.load(f)

    old_total = len(old_geojson['features'])
    waterway_set = set(NAVIGABLE_WATERWAYS)
    old_navigable = sum(
        1 for feat in old_geojson['features']
        if feat.get('properties') and feat['properties'].get('name') in waterway_set
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

    removed = old_navigable
    print('\nDone.')
    print(f'  Removed: {removed} old navigable features')
    print(f'  Added:   {len(all_new_features)} new features')
    print(f'  Total:   {new_total} features  (was {old_total})')


if __name__ == '__main__':
    dry_run = '--dry-run' in sys.argv
    main(dry_run=dry_run)
