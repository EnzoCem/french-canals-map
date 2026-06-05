#!/usr/bin/env python3
"""
fill_waterways.py — Re-fetch navigable waterways from OSM across multiple
European regions, stitch ways into continuous LineStrings, RDP-simplify,
and update waterways.geojson.

Usage:
    python fill_waterways.py               # full multi-region run (~30–60 min)
    python fill_waterways.py --dry-run     # print what would be fetched, no network calls
    python fill_waterways.py --clean-geojson  # remove non-navigable / duplicate features only
"""

import json
import os
import re
import sys
import time
from collections import defaultdict

import requests
from rdp import rdp as _rdp


# ── Constants ────────────────────────────────────────────────────────────────

OVERPASS_URL = "https://overpass-api.de/api/interpreter"
FRANCE_BBOX  = "(42.3,-5.2,51.1,8.3)"  # south,west,north,east — covers all of France (legacy)
RDP_EPSILON  = 0.0003                   # ~33 m at French latitudes


# ── Geographic regions for the Overpass sweep ────────────────────────────────
# Each entry is (south, west, north, east) in WGS84 degrees. Smaller regions
# keep individual Overpass queries under the 180 s timeout and reduce memory
# pressure on the server. Regions overlap slightly — dedup handles joins.

REGIONS = {
    # France — split into 4 quadrants for query budget
    'FR-NW':  (47.0, -5.5, 51.5,  3.0),
    'FR-NE':  (47.0,  3.0, 51.5,  8.5),
    'FR-SW':  (42.0, -2.5, 47.0,  3.5),
    'FR-SE':  (42.0,  3.5, 47.0,  8.0),

    # Benelux
    'BE':     (49.5,  2.5, 51.6,  6.5),
    'NL':     (50.7,  3.3, 53.7,  7.3),
    'LU':     (49.4,  5.7, 50.2,  6.6),

    # Germany — split E/W due to size
    'DE-W':   (47.2,  5.8, 54.0, 10.5),
    'DE-E':   (47.2, 10.5, 54.9, 15.1),

    # Alpine
    'CH':     (45.8,  5.9, 47.9, 10.5),
    'AT':     (46.3,  9.5, 49.1, 17.2),

    # Italy — only northern (Po) is navigable
    'IT-N':   (44.0,  6.5, 46.6, 13.6),

    # British Isles
    'UK-S':   (49.9, -6.5, 53.5,  1.8),
    'UK-N':   (53.5, -8.5, 59.0,  1.8),
    'IE':     (51.4, -10.6, 55.4, -5.9),
}


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
    'River Yonne':                   ["L'Yonne", 'River Yonne', 'Yonne'],
    'Canal de la Somme':             ['Canal de la Somme', 'Somme', 'Canal de la Somme à la Sensée'],
    'Canal entre Champagne et Bourgogne': ['Canal Entre Champagne et Bourgogne', 'Canal entre Champagne et Bourgogne', 'Canal de la Marne à la Saône'],
    'Liaison Dunkerque\u2013Escaut': ['Liaison Dunkerque\u2013Escaut', 'Canal Dunkerque-Escaut'],
    'Canal de la Marne à la Saône':  ['Canal de la Marne à la Saône', 'Canal entre Champagne et Bourgogne'],

    # ── EU waterways added Wave 1 ─────────────────────────────────────────────
    'Rhine':                         ['Rhine', 'Rhein', 'Rijn', 'Le Rhin'],
    'Moselle (DE/LU)':               ['Mosel', 'Musel'],
    'Main':                          ['Main'],
    'Main-Donau-Kanal':              ['Main-Donau-Kanal', 'Rhein-Main-Donau-Kanal'],
    'Danube':                        ['Danube', 'Donau'],
    'Standing Mast Route':           ['Staande Mastroute'],
    'IJsselmeer':                    ['IJsselmeer'],
    'Markermeer':                    ['Markermeer'],
    'Amsterdam-Rijnkanaal':          ['Amsterdam-Rijnkanaal'],
    'Albert Canal':                  ['Albertkanaal', 'Albert Canal'],
    'Scheldt':                       ['Schelde', 'Escaut', 'Scheldt'],
    'Meuse (BE/NL)':                 ['Maas'],
    'Po':                            ['Po'],
    'Thames':                        ['River Thames', 'Thames'],
    'Kennet and Avon Canal':         ['Kennet and Avon Canal'],
    'Caledonian Canal':              ['Caledonian Canal'],
    'Grand Union Canal':             ['Grand Union Canal'],
    'Shannon':                       ['River Shannon', 'Shannon'],
    'Erne':                          ['River Erne', 'Erne'],
    'Shannon-Erne Waterway':         ['Shannon–Erne Waterway', 'Shannon-Erne Waterway'],
    'Royal Canal':                   ['Royal Canal'],
    'Grand Canal (IE)':              ['Grand Canal'],
    'Mittellandkanal':               ['Mittellandkanal'],
    'Elbe-Lübeck-Kanal':        ['Elbe-Lübeck-Kanal'],
    'Nord-Ostsee-Kanal':             ['Nord-Ostsee-Kanal', 'Kiel Canal'],
    'Dortmund-Ems-Kanal':            ['Dortmund-Ems-Kanal'],
    'Hochrhein':                     ['Hochrhein'],
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

    # ── EU waterways added Wave 1 (route=0 = no French route number) ──────────
    'Rhine':                          0,
    'Moselle (DE/LU)':                0,
    'Main':                           0,
    'Main-Donau-Kanal':               0,
    'Danube':                         0,
    'Standing Mast Route':            0,
    'IJsselmeer':                     0,
    'Markermeer':                     0,
    'Amsterdam-Rijnkanaal':           0,
    'Albert Canal':                   0,
    'Scheldt':                        0,
    'Meuse (BE/NL)':                  0,
    'Po':                             0,
    'Thames':                         0,
    'Kennet and Avon Canal':          0,
    'Caledonian Canal':               0,
    'Grand Union Canal':              0,
    'Shannon':                        0,
    'Erne':                           0,
    'Shannon-Erne Waterway':          0,
    'Royal Canal':                    0,
    'Grand Canal (IE)':               0,
    'Mittellandkanal':                0,
    'Elbe-Lübeck-Kanal':              0,
    'Nord-Ostsee-Kanal':              0,
    'Dortmund-Ems-Kanal':             0,
    'Hochrhein':                      0,
}

NAVIGABLE_WATERWAYS = list(WATERWAY_ROUTES.keys())


# ── Name normalisation & non-navigable filter ────────────────────────────────

_PREFIX_RE = re.compile(r'^(river |la |le |l\'|les |the )', re.I)

def _norm_name(name):
    """
    Normalise a waterway name for fuzzy matching.
    Strips leading natural-language articles and lowercases so that, e.g.,
    'Canal Entre Champagne et Bourgogne' == 'Canal entre Champagne et Bourgogne',
    'Canal Latéral à la Marne' == 'Canal latéral à la Marne', and
    'La Seine' == 'River Seine' (both strip to 'seine').

    Does NOT strip 'canal de' — that is part of the name, not a mere article.
    'La Garonne' (the river) and 'Canal de Garonne' (the lateral canal) are
    intentionally kept as distinct waterways.
    """
    return _PREFIX_RE.sub('', (name or '').lower()).strip()


# Pattern matching non-navigable waterway-segment names across languages.
# Each language group cites its source so future maintainers can audit.
# Word boundaries are loose because OSM names are not consistent
# (e.g. "Ancien Canal", "L'Ancien Bras", "Bras Mort").
_NON_NAVIGABLE_RE = re.compile(
    r'\b('
    # French (original set) — Ancien Canal de…, Bras Mort, Vieux Rhin, Écluse n°X,
    # Pont-Canal (aqueduct bridges), Aqueduc du Loing, Prise d'Eau, Souterrain
    r'ancien(ne)?|bras[ -]mort|vieux|vieille|[ée]cluse|pont-canal|aqueduc|prise\s+d.eau|souterrain'
    # Dutch — sources: PDOK BRT-Achtergrondkaart, Wikipedia NL on canal naming
    r'|voorhaven|oude|verlaten|gedempt|stuw'
    # German — sources: WSV waterway register, Wikipedia DE on Wasserstraßen
    r'|alter|altes|alte|wehr|schleusenkanal'
    # English (UK/IE) — disused canal terminology
    r'|disused|abandoned|former|filled[-\s]in'
    # Italian — Naviglio terminology
    r'|abbandonat[oa]|antic[oa]'
    r')\b',
    re.I,
)

def is_non_navigable(name):
    """Return True if the feature name indicates a non-navigable structure."""
    return bool(_NON_NAVIGABLE_RE.search(name or ''))


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
    Replace features whose name matches waterway_names with new_features.

    old_geojson:    parsed FeatureCollection dict
    new_features:   list of new Feature dicts to insert
    waterway_names: set of name strings to remove from old features

    Matching is normalised (case-insensitive, leading articles stripped) so
    capitalisation variants such as 'Canal Entre Champagne et Bourgogne' are
    treated as the same waterway as 'Canal entre Champagne et Bourgogne'.

    Also strips any non-navigable features (abandoned canals, dead arms,
    lock structures, aqueducts, etc.) from the kept set.

    Returns a new FeatureCollection dict (does not mutate inputs).
    """
    norm_names = {_norm_name(n) for n in waterway_names}
    kept = [
        f for f in old_geojson['features']
        if not (
            _norm_name((f.get('properties') or {}).get('name') or '') in norm_names
            or is_non_navigable((f.get('properties') or {}).get('name') or '')
        )
    ]
    return {
        'type': 'FeatureCollection',
        'features': kept + new_features,
    }


def clean_geojson(geojson):
    """
    One-shot cleanup pass: remove non-navigable structures and non-canonical
    capitalisation variants from an existing FeatureCollection.

    A feature is a 'non-canonical variant' when its name normalises to the
    same string as a known navigable waterway key but differs in spelling
    (e.g. capital-E 'Canal Entre…' alongside lowercase-e 'Canal entre…'),
    AND the canonical spelling already has at least one feature present —
    so we never discard the only data we have for a waterway.

    Returns (cleaned_geojson, n_non_navigable_removed, n_variant_removed).
    """
    # Build normalised → canonical name index from the authoritative list
    canonical_by_norm = {_norm_name(n): n for n in NAVIGABLE_WATERWAYS}

    # Count existing features per exact name
    name_counts = defaultdict(int)
    for f in geojson['features']:
        n = (f.get('properties') or {}).get('name') or ''
        name_counts[n] += 1

    kept = []
    n_non_nav = 0
    n_variant = 0

    for f in geojson['features']:
        name = (f.get('properties') or {}).get('name') or ''

        # 1. Remove known non-navigable structure types
        if is_non_navigable(name):
            n_non_nav += 1
            continue

        # 2. Remove capitalisation variants when the canonical spelling exists
        canonical = canonical_by_norm.get(_norm_name(name))
        if canonical and canonical != name and name_counts.get(canonical, 0) > 0:
            n_variant += 1
            continue

        kept.append(f)

    return {'type': 'FeatureCollection', 'features': kept}, n_non_nav, n_variant


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


def fetch_waterway(app_name, osm_names, bbox=None):
    """
    Fetch OSM ways for a waterway, trying each osm_name in order.
    For each name: tries relation[type=waterway] first (global, no bbox),
    then a way fallback constrained to bbox.

    bbox: (south, west, north, east) tuple in WGS84 degrees. Defaults to
          FRANCE_BBOX (legacy behaviour) when not supplied.

    Returns list of ways (each a list of [lon, lat] pairs), or [] if nothing found.
    """
    if bbox is None:
        # Legacy default — covers all of France (42.3,-5.2,51.1,8.3)
        s, w, n, e = 42.3, -5.2, 51.1, 8.3
    else:
        s, w, n, e = bbox
    bbox_str = f'({s},{w},{n},{e})'

    for osm_name in osm_names:
        # ── 1. Relation query (no bbox — relations span borders) ──────────
        ql_relation = f'''[out:json][timeout:180];
relation[type=waterway][name="{osm_name}"];
way(r)({s},{w},{n},{e});
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
way[waterway][name="{osm_name}"]{bbox_str};
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
        print(f'\n-- DRY RUN: would sweep {len(REGIONS)} regions × {len(WATERWAY_ROUTES)} waterways --')
        print('\nRegions:')
        for region_name, bbox in REGIONS.items():
            print(f'  {region_name}: {bbox}')
        print('\nWaterways:')
        for app_name in NAVIGABLE_WATERWAYS:
            osm_names = OSM_NAME_MAP.get(app_name, [app_name])
            print(f'  {app_name}  →  OSM names: {osm_names}')
        return

    all_new_features = []
    # Track which (app_name, region) combos already yielded data to avoid
    # re-fetching a waterway that spans multiple region tiles.
    seen_ways: dict[str, set] = defaultdict(set)  # app_name → set of way coord hashes

    for region_name, bbox in REGIONS.items():
        print(f'\n=== Region {region_name} {bbox} ===')
        for app_name in NAVIGABLE_WATERWAYS:
            osm_names = OSM_NAME_MAP.get(app_name, [app_name])
            route_num = WATERWAY_ROUTES[app_name]

            try:
                ways = fetch_waterway(app_name, osm_names, bbox=bbox)
            except Exception as exc:
                print(f'  {app_name}: FAILED ({exc}) — skipping')
                continue

            if not ways:
                continue

            # Deduplicate ways across regions using first+last coord as key
            new_ways = []
            for way in ways:
                key = (tuple(way[0]), tuple(way[-1]))
                rev_key = (tuple(way[-1]), tuple(way[0]))
                if key not in seen_ways[app_name] and rev_key not in seen_ways[app_name]:
                    seen_ways[app_name].add(key)
                    new_ways.append(way)

            if not new_ways:
                print(f'  {app_name}: {len(ways)} ways (all duplicates of earlier region — skipped)')
                continue

            chains = stitch_ways(new_ways)
            features = build_features(app_name, chains, route_num)
            all_new_features.extend(features)
            print(f'  {app_name}: {len(new_ways)} new ways → {len(chains)} chains, {len(features)} features')

        time.sleep(2)  # be polite to Overpass between regions

    print(f'\nTotal raw features: {len(all_new_features)}')

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
    if '--clean-geojson' in sys.argv:
        geojson_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'waterways.geojson')
        if not os.path.exists(geojson_path):
            sys.exit(f'ERROR: {geojson_path} not found.')
        with open(geojson_path) as f:
            old = json.load(f)
        old_count = len(old['features'])
        cleaned, n_non_nav, n_variant = clean_geojson(old)
        new_count = len(cleaned['features'])
        tmp = geojson_path + '.tmp'
        with open(tmp, 'w') as f:
            json.dump(cleaned, f, separators=(',', ':'))
        os.replace(tmp, geojson_path)
        print(f'Cleaned waterways.geojson:')
        print(f'  Removed {n_non_nav} non-navigable features (abandoned, dead arms, structures)')
        print(f'  Removed {n_variant} non-canonical capitalisation variants')
        print(f'  Total: {old_count} → {new_count} features')
    else:
        dry_run = '--dry-run' in sys.argv
        main(dry_run=dry_run)
