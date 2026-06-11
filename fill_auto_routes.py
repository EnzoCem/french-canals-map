#!/usr/bin/env python3
"""
fill_auto_routes.py — Emit route entries for every named waterway in
waterways.geojson that isn't already in the curated `routes` list.

Idempotent: re-running replaces previous source='osm' entries; curated
entries are never touched.

Usage:
    python3 fill_auto_routes.py             # full run
    python3 fill_auto_routes.py --dry-run   # print would-add, no write
"""
import argparse
import json
import os
import re
import sys
from collections import defaultdict
from math import radians, sin, cos, sqrt, atan2

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
WATERWAYS_PATH = os.path.join(PROJECT_ROOT, 'waterways.geojson')
ROUTES_PATH = os.path.join(PROJECT_ROOT, 'data', 'routes.json')
WAYPOINTS_PATH = os.path.join(PROJECT_ROOT, 'data', 'waypoints.json')

AUTO_ROUTE_NUM_START = 200  # route numbers 1-199 reserved for curated


def haversine_km(lat1, lon1, lat2, lon2):
    """Great-circle distance in kilometres."""
    R = 6371.0
    phi1, phi2 = radians(lat1), radians(lat2)
    dphi = radians(lat2 - lat1)
    dlambda = radians(lon2 - lon1)
    a = sin(dphi / 2) ** 2 + cos(phi1) * cos(phi2) * sin(dlambda / 2) ** 2
    return 2 * R * atan2(sqrt(a), sqrt(1 - a))


def polyline_length_km(coords):
    """Sum of haversine distances between consecutive (lon, lat) points."""
    total = 0.0
    for i in range(1, len(coords)):
        lon1, lat1 = coords[i - 1]
        lon2, lat2 = coords[i]
        total += haversine_km(lat1, lon1, lat2, lon2)
    return total


def group_features_by_name(features):
    """Group GeoJSON features by their properties.name. Returns dict of
    name → list-of-lines (each line is a list of [lon, lat] pairs)."""
    groups = defaultdict(list)
    for f in features:
        name = (f.get('properties') or {}).get('name')
        if not name:
            continue
        geom = f.get('geometry') or {}
        gtype = geom.get('type')
        coords = geom.get('coordinates') or []
        if gtype == 'LineString':
            groups[name].append(coords)
        elif gtype == 'MultiLineString':
            for line in coords:
                groups[name].append(line)
    return groups


def count_locks_near_segments(segments, waypoints, radius_m=200):
    """Count distinct lock waypoints within `radius_m` of any segment vertex."""
    radius_km = radius_m / 1000
    count = 0
    seen_ids = set()
    for wp in waypoints:
        if not wp.get('is_lock'):
            continue
        wid = wp.get('id') or (wp['lat'], wp['lon'])
        if wid in seen_ids:
            continue
        for seg in segments:
            hit = False
            for lon, lat in seg:
                if haversine_km(wp['lat'], wp['lon'], lat, lon) <= radius_km:
                    hit = True
                    break
            if hit:
                count += 1
                seen_ids.add(wid)
                break
    return count


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--dry-run', action='store_true')
    args = p.parse_args()

    with open(WATERWAYS_PATH) as f:
        gj = json.load(f)
    with open(ROUTES_PATH) as f:
        rj = json.load(f)
    with open(WAYPOINTS_PATH) as f:
        wp = json.load(f)

    # Names already covered by curated routes (extract main token from `canal` field)
    curated_names = set()
    for r in rj['routes']:
        if r.get('source') == 'osm':
            continue
        canal = r.get('canal', '').split(' (')[0].split('—')[0].strip()
        if canal:
            curated_names.add(canal)

    groups = group_features_by_name(gj.get('features', []))
    print(f'Found {len(groups)} distinct waterway names in waterways.geojson')

    new_routes = []
    next_num = AUTO_ROUTE_NUM_START
    for name, segments in sorted(groups.items()):
        if name in curated_names:
            continue
        if not segments:
            continue
        length_km = sum(polyline_length_km(seg) for seg in segments)
        if length_km < 5:
            continue  # skip tiny stubs
        locks = count_locks_near_segments(segments, wp)
        new_routes.append({
            'num': next_num,
            'section': 1,
            'canal': name,
            'from': '', 'to': '',
            'locks': locks,
            'dist_km': round(length_km, 1),
            'max_height': None,
            'max_draught': None,
            'color': '#90a4ae',
            'country': [],
            'source': 'osm',
            'description': f'Auto-derived from OSM. {name} — {round(length_km)} km, {locks} locks counted within 200 m.',
        })
        next_num += 1

    print(f'Generated {len(new_routes)} auto-derived routes (nums {AUTO_ROUTE_NUM_START}-{next_num-1})')

    if args.dry_run:
        for nr in new_routes[:10]:
            print(f'  {nr["num"]:4d}  {nr["canal"]:50s}  {nr["dist_km"]:6.1f} km  {nr["locks"]:3d} locks')
        if len(new_routes) > 10:
            print(f'  … and {len(new_routes) - 10} more')
        return

    # Replace previous source='osm' entries in rj
    rj['routes'] = [r for r in rj['routes'] if r.get('source') != 'osm']
    rj['routes'].extend(new_routes)

    with open(ROUTES_PATH, 'w') as f:
        json.dump(rj, f, indent=2, ensure_ascii=False)
    print(f'Wrote {ROUTES_PATH}: {len(rj["routes"])} total routes (curated + osm)')


if __name__ == '__main__':
    main()
