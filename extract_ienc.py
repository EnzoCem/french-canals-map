#!/usr/bin/env python3
"""
extract_ienc.py — Extract navigationally useful features from VNF IENC
(Inland Electronic Navigational Chart) S-57 cells into compact GeoJSON.

MVP scope: bridges with per-bridge air clearance (VERCLR). See plan
docs/superpowers/plans/2026-04-23-ienc-bridge-heights.md for context.

Usage:
    python3 extract_ienc.py --zip ienc/FR.zip --out data/bridges.geojson

    # Multiple zips (later bundles override earlier by (cell_name))
    python3 extract_ienc.py \\
        --zip ienc/FR.zip \\
        --zip "VNF Charts/ENC_ROOT_SEINE_AVAL_ED2.zip" \\
        --zip "VNF Charts/ENC_ROOT_SEINE_AMONT_ED1.zip" \\
        --zip "VNF Charts/ENC_ROOT_SAONE_ED_2.zip" \\
        --zip "VNF Charts/Garonne_edition3.zip" \\
        --zip "VNF Charts/ENC_ROOT_OISE.zip" \\
        --out data/bridges.geojson

Requires: GDAL system install + matching Python bindings (venv/).
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
import zipfile
from collections import defaultdict

try:
    from osgeo import ogr, gdal
except ImportError:
    sys.exit(
        "ERROR: osgeo.ogr not available. Activate venv and install: "
        "`source venv/bin/activate && pip install GDAL==$(gdal-config --version)`."
    )

gdal.UseExceptions()
ogr.UseExceptions()
# Suppress the harmless "wtwdis not in expected schema" / "illegal attribute 17103"
# warnings that every VNF cell triggers. They are informational only.
gdal.PushErrorHandler("CPLQuietErrorHandler")

# VERCLR sentinel that IENC uses for aggregate bridge polygons — meaning
# "see the child `passe` features for actual clearances". Must be filtered.
VERCLR_SENTINEL = 9999.0


# ──────────────────────────────────────────────────────────────────────
# Waterway classification by cell-name prefix. Established in Task 1.
# ──────────────────────────────────────────────────────────────────────
def _waterway_for_cell(cell_name: str) -> str:
    """Map 8-char IENC cell name → user-facing waterway label.

    Cell names look like `4V7SEI10`, `4V5MOS01`, `1W7RH250`. See plan
    for the full table; this mirrors it.
    """
    name = cell_name.upper()
    if re.match(r"^4V7SEI\d{2}$", name):
        n = int(name[6:])
        return "Seine" if n <= 17 else "Seine (Amont)"
    if re.match(r"^4V7OIS\d{2}$", name):
        return "Oise"
    if re.match(r"^4V5MOS\d{2}$", name):
        return "Moselle"
    if re.match(r"^4V5\d{3}DE$", name):
        return "Canal Dunkerque–Escaut"
    if re.match(r"^4V5SAO\d{2}$", name):
        return "Saône"
    if re.match(r"^4V5RHO\d{2}$", name):
        return "Rhône"
    if re.match(r"^(4V5|4V6)GA\d{3}$", name):
        return "Garonne (tidal)"
    if re.match(r"^1W7RH\d{3}$", name):
        return "Rhine"
    if re.match(r"^1W7SR\d{3}$", name):
        return "Saône (upper)"
    if re.match(r"^1W7RRS\d{2}$", name):
        return "Canal du Rhône au Rhin"
    if name.startswith("7V7LEIE"):
        return "Leie"
    if name.startswith("7V7PLDU"):
        return "Canal Nieuwpoort–Dunkerque"
    return "Unknown waterway"


# ──────────────────────────────────────────────────────────────────────
# Zip → local cell paths
# ──────────────────────────────────────────────────────────────────────
def unpack_zip(zip_path: str, dest_dir: str) -> list[tuple[str, str]]:
    """Extract zip into `dest_dir`. Return list of (cell_name, abs_path)
    for every `.000` cell found (cell_name = basename without ext)."""
    if not os.path.exists(zip_path):
        raise FileNotFoundError(zip_path)
    with zipfile.ZipFile(zip_path) as z:
        z.extractall(dest_dir)
    cells: list[tuple[str, str]] = []
    for root, _, files in os.walk(dest_dir):
        for f in files:
            if f.lower().endswith(".000"):
                cells.append((os.path.splitext(f)[0], os.path.join(root, f)))
    return cells


# ──────────────────────────────────────────────────────────────────────
# Bridge extraction per cell
# ──────────────────────────────────────────────────────────────────────
def _feature_centroid(feature) -> tuple[float, float] | None:
    """Return (lon, lat) centroid of a feature geometry, or None."""
    geom = feature.GetGeometryRef()
    if geom is None:
        return None
    # Polygon → centroid; Point → coords; LineString → midpoint
    try:
        c = geom.Centroid()
        if c is None:
            return None
        return (c.GetX(), c.GetY())
    except Exception:
        return None


def extract_bridges_from_cell(cell_path: str, cell_name: str) -> list[dict]:
    """Return list of raw bridge feature dicts from one S-57 cell.

    Filters: drops features with VERCLR=9999 sentinel; drops features
    with no geometry. Keeps features with no VERCLR (they might be
    named bridges useful for cross-reference even without clearance).
    """
    ds = ogr.Open(cell_path)
    if ds is None:
        return []
    layer = ds.GetLayerByName("bridge")
    if layer is None:
        return []
    out: list[dict] = []
    layer.ResetReading()
    for feat in layer:
        centroid = _feature_centroid(feat)
        if centroid is None:
            continue
        lon, lat = centroid
        verclr = feat.GetField("VERCLR")
        if verclr is not None and abs(verclr - VERCLR_SENTINEL) < 0.01:
            verclr = None  # drop the "see children" sentinel
        # 0.0 (and negatives) are also "unknown / missing" in practice — a
        # real bridge with a 0 m air draught would be non-navigable and
        # should not appear in a pleasure-boating clearance dataset.
        if verclr is not None and verclr <= 0.0:
            verclr = None
        horclr = feat.GetField("HORCLR")
        if horclr is not None and horclr <= 0.0:
            horclr = None
        name = feat.GetField("OBJNAM") or feat.GetField("NOBJNM") or None
        catbrg = feat.GetField("catbrg")  # StringList → list or None
        out.append(
            {
                "name": name,
                "lat": round(lat, 6),
                "lon": round(lon, 6),
                "verclr_m": round(verclr, 2) if verclr is not None else None,
                "horclr_m": round(horclr, 2) if horclr is not None else None,
                "catbrg": catbrg if catbrg else None,
                "cell": cell_name,
                "waterway": _waterway_for_cell(cell_name),
            }
        )
    return out


# ──────────────────────────────────────────────────────────────────────
# Aggregation across spans → one feature per named bridge (min VERCLR)
# ──────────────────────────────────────────────────────────────────────
def aggregate_bridges(raw: list[dict]) -> list[dict]:
    """Collapse per-span features into per-named-bridge features.

    Rules (see Task 1 findings):
    - Bridges with the same `name` on the same waterway within 150 m of
      each other are the same physical bridge. Take the MIN VERCLR
      (worst-case clearance a vessel faces) and the centroid of the
      group.
    - Unnamed bridges (name is None) are kept individually — no safe
      way to merge without a name.
    - Drop bridges that end up with no VERCLR at all (nothing to show
      in a vessel-profile popup).
    """

    def cluster_key(b: dict) -> tuple | None:
        if not b["name"]:
            return None
        # Round coordinates into ~150 m grid for clustering (4dp ≈ 11 m,
        # 3dp ≈ 110 m). Using 3dp strikes the right balance.
        return (b["waterway"], b["name"], round(b["lat"], 3), round(b["lon"], 3))

    groups: dict[tuple, list[dict]] = defaultdict(list)
    unnamed: list[dict] = []
    for b in raw:
        k = cluster_key(b)
        if k is None:
            unnamed.append(b)
        else:
            groups[k].append(b)

    merged: list[dict] = []
    for _, members in groups.items():
        # Minimum non-null VERCLR across spans
        vs = [m["verclr_m"] for m in members if m["verclr_m"] is not None]
        if not vs:
            continue  # no clearance — drop
        hs = [m["horclr_m"] for m in members if m["horclr_m"] is not None]
        # Centroid of cluster members
        lat = sum(m["lat"] for m in members) / len(members)
        lon = sum(m["lon"] for m in members) / len(members)
        merged.append(
            {
                "name": members[0]["name"],
                "waterway": members[0]["waterway"],
                "lat": round(lat, 6),
                "lon": round(lon, 6),
                "verclr_m": round(min(vs), 2),
                "horclr_m": round(min(hs), 2) if hs else None,
                "span_count": len(members),
                "cells": sorted({m["cell"] for m in members}),
            }
        )

    # Unnamed: keep only those with a VERCLR so we have something to show
    for b in unnamed:
        if b["verclr_m"] is None:
            continue
        merged.append(
            {
                "name": None,
                "waterway": b["waterway"],
                "lat": b["lat"],
                "lon": b["lon"],
                "verclr_m": b["verclr_m"],
                "horclr_m": b["horclr_m"],
                "span_count": 1,
                "cells": [b["cell"]],
            }
        )

    return merged


# ──────────────────────────────────────────────────────────────────────
# Cross-zip dedup: keep the richest record per (name, rough location)
# ──────────────────────────────────────────────────────────────────────
def dedupe_across_zips(all_bridges: list[dict]) -> list[dict]:
    """When two zips supply the same bridge (e.g. FR.zip + SEINE_AVAL_ED2
    both carry SEI13), keep the record with the lowest VERCLR (most
    conservative) — or, if tied, the one with more span evidence.
    """
    by_key: dict[tuple, dict] = {}
    for b in all_bridges:
        k = (
            b["waterway"],
            b["name"] or "",
            round(b["lat"], 3),
            round(b["lon"], 3),
        )
        cur = by_key.get(k)
        if cur is None:
            by_key[k] = b
            continue
        # Prefer lower VERCLR (more conservative), then higher span count
        if (b["verclr_m"], -b["span_count"]) < (cur["verclr_m"], -cur["span_count"]):
            by_key[k] = b
    return list(by_key.values())


# ──────────────────────────────────────────────────────────────────────
# GeoJSON emit
# ──────────────────────────────────────────────────────────────────────
def to_geojson(bridges: list[dict]) -> dict:
    feats = []
    for b in bridges:
        feats.append(
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [b["lon"], b["lat"]]},
                "properties": {
                    "name": b["name"],
                    "waterway": b["waterway"],
                    "verclr_m": b["verclr_m"],
                    "horclr_m": b["horclr_m"],
                    "spans": b["span_count"],
                    "source": "VNF IENC (Licence Ouverte 2.0)",
                },
            }
        )
    return {"type": "FeatureCollection", "features": feats}


# ──────────────────────────────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────────────────────────────
def main() -> int:
    ap = argparse.ArgumentParser(
        description="Extract VNF IENC bridge clearances into GeoJSON."
    )
    ap.add_argument(
        "--zip",
        action="append",
        required=True,
        help="Path to an IENC zip (repeatable; later zips override cells in earlier ones).",
    )
    ap.add_argument("--out", required=True, help="Output GeoJSON path.")
    args = ap.parse_args()

    all_raw: list[dict] = []
    zip_stats: list[tuple[str, int, int]] = []  # (zip_path, cell_count, raw_bridges)

    with tempfile.TemporaryDirectory(prefix="ienc_") as tmp:
        for zp in args.zip:
            if not os.path.exists(zp):
                print(f"WARN: zip not found, skipping: {zp}", file=sys.stderr)
                continue
            sub = os.path.join(tmp, re.sub(r"[^A-Za-z0-9]+", "_", os.path.basename(zp)))
            cells = unpack_zip(zp, sub)
            raw_this = []
            for cell_name, cell_path in cells:
                raw_this.extend(extract_bridges_from_cell(cell_path, cell_name))
            zip_stats.append((zp, len(cells), len(raw_this)))
            all_raw.extend(raw_this)

    aggregated = aggregate_bridges(all_raw)
    deduped = dedupe_across_zips(aggregated)

    gj = to_geojson(deduped)
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    tmp_out = args.out + ".tmp"
    with open(tmp_out, "w") as f:
        json.dump(gj, f, separators=(",", ":"))
    os.replace(tmp_out, args.out)

    # ── Report ────────────────────────────────────────────────────
    print("\n=== IENC bridge extraction summary ===")
    for zp, cells, raw in zip_stats:
        print(f"  {os.path.basename(zp):45s} {cells:4d} cells  {raw:4d} raw bridges")
    print(f"\n  Raw bridge features (all zips): {len(all_raw)}")
    print(f"  After per-name aggregation:     {len(aggregated)}")
    print(f"  After cross-zip dedup:          {len(deduped)}")
    print(f"\n  Waterway breakdown (final):")
    ww_count: dict[str, int] = defaultdict(int)
    for b in deduped:
        ww_count[b["waterway"]] += 1
    for ww in sorted(ww_count, key=lambda w: -ww_count[w]):
        print(f"    {ww:30s} {ww_count[ww]:4d}")
    print(f"\n  Wrote {args.out} ({os.path.getsize(args.out) / 1024:.1f} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
