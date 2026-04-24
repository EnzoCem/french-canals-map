#!/usr/bin/env python3
"""
audit_positions.py — sanity-check every MOORING and WAYPOINT position in
`french_canals_map.html` against `waterways.geojson`. Any point that is
far from the nearest navigable waterway is likely pinned at the
commune centre (or a similar wrong address) rather than at the actual
port/halte/lock.

Usage:
    python3 audit_positions.py                       # human report
    python3 audit_positions.py --csv audit.csv       # also dump CSV
    python3 audit_positions.py --min-dist 400        # lower threshold

No dependencies beyond the stdlib. Fast enough without numpy
(~115 moorings × ~3,474 waterway features ≈ a few seconds).
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


# ──────────────────────────────────────────────────────────────────────
# Parse WAYPOINTS + MOORINGS out of the main HTML (reuse the same
# bracket-walk + json5 trick used by extract_ienc.py).
# ──────────────────────────────────────────────────────────────────────
def parse_app_data(html_path: str) -> tuple[list[dict], list[dict]]:
    import json5
    with open(html_path) as f:
        text = f.read()

    def extract_array(const_name: str) -> list[dict]:
        m = re.search(rf"const\s+{const_name}\s*=\s*\[", text)
        if not m:
            return []
        start = m.end() - 1
        depth = 0
        in_str = False
        str_ch = ""
        i = start
        L = len(text)
        while i < L:
            ch = text[i]
            if in_str:
                if ch == "\\" and i + 1 < L:
                    i += 2
                    continue
                if ch == str_ch:
                    in_str = False
                i += 1
                continue
            if ch == "/" and i + 1 < L and text[i + 1] == "/":
                while i < L and text[i] != "\n":
                    i += 1
                continue
            if ch == "/" and i + 1 < L and text[i + 1] == "*":
                i += 2
                while i + 1 < L and not (text[i] == "*" and text[i + 1] == "/"):
                    i += 1
                i += 2
                continue
            if ch in ("'", '"'):
                in_str = True
                str_ch = ch
            elif ch == "[":
                depth += 1
            elif ch == "]":
                depth -= 1
                if depth == 0:
                    i += 1
                    break
            i += 1
        return json5.loads(text[start:i])

    return extract_array("WAYPOINTS"), extract_array("MOORINGS")


# ──────────────────────────────────────────────────────────────────────
# Distance math
# ──────────────────────────────────────────────────────────────────────
def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6_371_000.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2
         + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2))
         * math.sin(dlon / 2) ** 2)
    return 2 * R * math.asin(math.sqrt(a))


def bbox_of(coords: list[list[float]]) -> tuple[float, float, float, float]:
    """Return (min_lon, min_lat, max_lon, max_lat) of a LineString."""
    lons = [c[0] for c in coords]
    lats = [c[1] for c in coords]
    return (min(lons), min(lats), max(lons), max(lats))


def bbox_distance_lower_bound(lat: float, lon: float,
                              bb: tuple[float, float, float, float]) -> float:
    """Quick lower bound: straight-line distance from (lat,lon) to the
    bbox. If the bbox is far away, we skip iterating its points.
    Uses haversine on the closest bbox corner/edge point."""
    min_lon, min_lat, max_lon, max_lat = bb
    nlon = max(min_lon, min(lon, max_lon))
    nlat = max(min_lat, min(lat, max_lat))
    return haversine_m(lat, lon, nlat, nlon)


def min_distance_to_waterways(lat: float, lon: float,
                              features: list[dict],
                              matching_names: set[str] | None = None) -> tuple[float, str]:
    """Minimum haversine distance (m) from (lat, lon) to any LineString in
    `features`. If `matching_names` is given, restrict to features whose
    name normalises into that set. Returns (distance, matched_name)."""
    best = float("inf")
    best_name = ""
    for feat in features:
        geom = feat.get("geometry", {})
        if geom.get("type") != "LineString":
            continue
        name = (feat.get("properties", {}).get("name") or "")
        if matching_names is not None:
            nk = norm_waterway(name)
            if nk not in matching_names:
                continue
        coords = geom["coordinates"]
        if not coords:
            continue
        # Bbox quick-reject: skip if the bbox lower-bound is already
        # worse than the current best.
        bb = feat.get("__bbox")
        if bb is None:
            bb = bbox_of(coords)
            feat["__bbox"] = bb
        if bbox_distance_lower_bound(lat, lon, bb) > best:
            continue
        for (c_lon, c_lat) in coords:
            d = haversine_m(lat, lon, c_lat, c_lon)
            if d < best:
                best = d
                best_name = name
    return best, best_name


# ──────────────────────────────────────────────────────────────────────
# Waterway name normalisation (same rules as the app's _normName)
# ──────────────────────────────────────────────────────────────────────
_PREFIX_RE = re.compile(r"^(river |la |le |l'|les |the )", re.I)

def norm_waterway(s: str | None) -> str:
    if not s:
        return ""
    return _PREFIX_RE.sub("", s.lower()).strip()


# ──────────────────────────────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────────────────────────────
def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--html", default=os.path.join(HERE, "french_canals_map.html"))
    ap.add_argument("--waterways", default=os.path.join(HERE, "waterways.geojson"))
    ap.add_argument("--min-dist", type=float, default=500.0,
                    help="Flag items farther than this many metres from any waterway. Default 500.")
    ap.add_argument("--csv", default=None)
    ap.add_argument("--strict-waterway", action="store_true",
                    help="Match each item only against waterway features whose name matches its "
                         "`waterway` field (moorings) or is plausible (waypoints). "
                         "Without this flag, distance is to ANY waterway — better at catching "
                         "mis-placed markers regardless of label accuracy.")
    ap.add_argument("--only", choices=["moorings", "locks", "all"], default="all",
                    help="Restrict audit to a subset. Town waypoints (no `waterway`, not locks) "
                         "are pinned at town centres by design and generate noise — use "
                         "`moorings` or `locks` to skip them.")
    args = ap.parse_args()

    waypoints, moorings = parse_app_data(args.html)
    with open(args.waterways) as f:
        geo = json.load(f)
    features = geo["features"]
    print(f"Loaded {len(waypoints)} waypoints, {len(moorings)} moorings, {len(features)} waterway features.", file=sys.stderr)

    # Build matched-name set per item for --strict-waterway mode.
    rows: list[dict] = []

    def audit(item: dict, kind: str, waterway_override: str | None = None):
        try:
            lat = float(item["lat"])
            lon = float(item["lon"])
        except (KeyError, ValueError, TypeError):
            return
        names: set[str] | None = None
        if args.strict_waterway:
            ww = waterway_override or item.get("waterway")
            if ww:
                names = {norm_waterway(ww)}
        dist, matched = min_distance_to_waterways(lat, lon, features, names)
        rows.append({
            "kind": kind,
            "id": item.get("id", ""),
            "name": item.get("name", ""),
            "waterway": item.get("waterway", ""),
            "lat": lat,
            "lon": lon,
            "distance_m": round(dist, 1),
            "nearest_waterway_name": matched,
        })

    if args.only in ("moorings", "all"):
        for m in moorings:
            audit(m, "mooring")
    if args.only in ("locks", "all"):
        for w in waypoints:
            if w.get("is_lock"):
                audit(w, "lock")
    if args.only == "all":
        for w in waypoints:
            if not w.get("is_lock"):
                audit(w, "waypoint")

    rows.sort(key=lambda r: -r["distance_m"])

    # Report
    outliers = [r for r in rows if r["distance_m"] > args.min_dist]
    print(f"\n=== Position-audit summary (>{args.min_dist:.0f} m from nearest waterway) ===")
    print(f"Total items: {len(rows)}")
    print(f"Within threshold: {len(rows) - len(outliers)}")
    print(f"Flagged outliers: {len(outliers)}")
    print()

    if outliers:
        print(f"{'DIST(m)':>8s} │ {'KIND':<8s} │ {'ID':<6s} │ {'WATERWAY':<25s} │ NAME")
        print("─" * 110)
        for r in outliers[:40]:
            print(f"{r['distance_m']:>8.0f} │ {r['kind']:<8s} │ {r['id']:<6s} │ "
                  f"{(r['waterway'] or '')[:25]:<25s} │ {r['name']}")

    if args.csv:
        with open(args.csv, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=["kind", "id", "name", "waterway", "lat", "lon",
                                              "distance_m", "nearest_waterway_name"])
            w.writeheader()
            for r in rows:
                w.writerow(r)
        print(f"\nFull CSV written to {args.csv}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
