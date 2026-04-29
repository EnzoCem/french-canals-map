#!/usr/bin/env python3
"""
patch_canal_gaps.py — Fetch the four waterways identified as missing
from waterways.geojson by the 2026-04-24 position audit:

  - Le Doubs             (Besançon — canalised river)
  - La Scarpe            (Arras → Douai)
  - Canal de la Deûle    (Lille)
  - La Somme             (Amiens — canalised river)

Each is fetched by OSM name (regional bbox), stitched, RDP-simplified
at the same 33 m tolerance as fill_waterways.py, and appended to
waterways.geojson. Run once, commit the resulting geojson.

Usage:
    source venv/bin/activate
    python3 patch_canal_gaps.py
"""

from __future__ import annotations

import json
import os
import sys
import time
from collections import defaultdict

import requests
from rdp import rdp as _rdp

OVERPASS_URL = "https://overpass-api.de/api/interpreter"
HEADERS = {"User-Agent": "french-canals-map/1.0 (gap-fill; enzocem on github)"}
RDP_EPSILON = 0.0003  # ~33 m, matches fill_waterways.py

# Each entry: (app-facing name, [osm names to try], bbox south,west,north,east)
# Each target: (osm_name, bbox, force) where force=True re-fetches even
# if a feature of that name already exists (used for infill gaps).
TARGETS = [
    # 2026-04-24 follow-up — the navigable canalised sections
    ("La Scarpe Canalisée", (50.15, 2.65, 50.60, 3.55), False),
    # Central-Amiens gap: existing 48 La-Somme-Canalisée segments skip over
    # central Amiens. Force re-fetch in a tight bbox to close the gap.
    ("La Somme Canalisée",  (49.85, 2.20, 49.95, 2.40), True),
    # First-pass targets
    ("Le Doubs",            (46.85, 5.40, 47.60, 6.75), False),
    ("La Scarpe",           (50.15, 2.65, 50.55, 3.50), False),
    ("Canal de la Deûle",   (50.40, 2.80, 50.85, 3.25), False),
    # Rhône mid-valley (Avignon ↔ Pont-Saint-Esprit) — gap prompted by the
    # original Laudun-l'Ardoise user report. Force because "Le Rhône"
    # already exists elsewhere in the geojson but skips this stretch.
    ("Le Rhône",            (43.95, 4.55, 44.25, 4.85), True),
    # Full Rhône Lyon → Mediterranean (covers all 3T5RHO* cell range
    # 45.7°N Lyon down to 43.4°N Port-Saint-Louis). Force because
    # mid-valley already partially fetched.
    ("Le Rhône",            (43.30, 4.50, 45.80, 5.00), True),
    # Saar (Saarbrücken area + Sarreguemines) — adds river line under the
    # 16 newly-imported IENC Saar locks. OSM tags it "Die Saar".
    ("Die Saar",            (49.10, 6.50, 49.50, 7.10), False),
    ("Saar",                (49.10, 6.50, 49.50, 7.10), False),
]


def _overpass(ql: str, retries: int = 3) -> dict:
    for attempt in range(retries):
        try:
            r = requests.post(OVERPASS_URL, data={"data": ql}, headers=HEADERS, timeout=180)
            r.raise_for_status()
            return r.json()
        except Exception as exc:
            if attempt < retries - 1:
                wait = 15 * (attempt + 1)
                print(f"  Overpass error ({exc}); retrying in {wait}s…")
                time.sleep(wait)
            else:
                raise


def _extract_ways(elements: list) -> list[list[list[float]]]:
    """Turn a list of Overpass `way` elements with `geometry` into a list
    of `[[lon, lat], …]` linestrings."""
    ways = []
    for el in elements:
        if el.get("type") != "way":
            continue
        geom = el.get("geometry", [])
        if len(geom) < 2:
            continue
        ways.append([[p["lon"], p["lat"]] for p in geom])
    return ways


def fetch_by_name(osm_name: str, bbox: tuple[float, float, float, float]) -> list[list[list[float]]]:
    s, w, n, e = bbox
    ql = f'''[out:json][timeout:180];
way[waterway]["name"="{osm_name}"]({s},{w},{n},{e});
out geom;'''
    data = _overpass(ql)
    return _extract_ways(data.get("elements", []))


def stitch_ways(ways: list[list[list[float]]], precision: int = 5) -> list[list[list[float]]]:
    """Join ways that share endpoints into longer chains."""
    if not ways:
        return []

    def ekey(pt):
        return (round(pt[0], precision), round(pt[1], precision))

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
            chain.extend(w[1:] if at_start else w[-2::-1])
        chains.append(chain)
    return chains


def rdp_simplify(coords: list[list[float]]) -> list[list[float]]:
    if len(coords) < 3:
        return coords
    return [list(pt) for pt in _rdp(coords, epsilon=RDP_EPSILON)]


def _existing_names(features: list[dict]) -> set[str]:
    return {
        (f.get("properties") or {}).get("name", "") for f in features
    }


def main() -> int:
    here = os.path.dirname(os.path.abspath(__file__))
    path = os.path.join(here, "waterways.geojson")
    if not os.path.exists(path):
        sys.exit(f"ERROR: {path} not found.")

    with open(path) as f:
        geo = json.load(f)
    old_count = len(geo["features"])
    existing = _existing_names(geo["features"])
    print(f"Loaded waterways.geojson: {old_count} features")
    print(f"Existing canonical names (sample of relevant): " +
          ", ".join(sorted(n for n in existing if any(k in n for k in ('Doubs', 'Scarpe', 'Deûle', 'Somme'))))
          or "  (none of the target canals present)")

    # Collect existing coordinate hashes so we don't emit duplicate chains
    # on a re-run.
    def _chain_hash(coords):
        return (round(coords[0][0], 4), round(coords[0][1], 4),
                round(coords[-1][0], 4), round(coords[-1][1], 4),
                len(coords))
    existing_hashes = set()
    for f in geo["features"]:
        g = f.get("geometry") or {}
        if g.get("type") == "LineString" and g.get("coordinates"):
            existing_hashes.add(_chain_hash(g["coordinates"]))

    new_features: list[dict] = []
    for osm_name, bbox, force in TARGETS:
        print(f"\n─── {osm_name} ───")
        if osm_name in existing and not force:
            print(f"  Already present as '{osm_name}'. Skipping (use force=True to re-fetch).")
            continue
        if osm_name in existing and force:
            print(f"  Already present — forcing re-fetch for gap-infill.")
        try:
            ways = fetch_by_name(osm_name, bbox)
        except Exception as exc:
            print(f"  ERROR: {exc}")
            continue
        if not ways:
            print(f"  WARNING: no geometry fetched")
            continue
        print(f"  → {len(ways)} ways found")

        chains = stitch_ways(ways)
        kept = dupes = 0
        for chain in chains:
            simplified = rdp_simplify(chain)
            if len(simplified) < 2:
                continue
            h = _chain_hash(simplified)
            if h in existing_hashes:
                dupes += 1
                continue
            existing_hashes.add(h)
            new_features.append({
                "type": "Feature",
                "geometry": {"type": "LineString", "coordinates": simplified},
                "properties": {"name": osm_name},
            })
            kept += 1
        extra = f" ({dupes} duplicates skipped)" if dupes else ""
        print(f"  → {kept} new chains appended (from {len(chains)} stitched){extra}")

    if not new_features:
        print("\nNo new features to add.")
        return 0

    geo["features"].extend(new_features)
    new_count = len(geo["features"])
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(geo, f, separators=(",", ":"))
    os.replace(tmp, path)

    print(f"\nDone. Added {len(new_features)} new features.")
    print(f"Total: {old_count} → {new_count} features")
    print(f"Wrote {path} ({os.path.getsize(path) / 1024 / 1024:.2f} MB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
