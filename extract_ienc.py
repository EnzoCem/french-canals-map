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
# UTF-8 mojibake repair for S-57 strings
# ──────────────────────────────────────────────────────────────────────
# The French VNF IENC cells store text as UTF-8 bytes in their `ATTF`
# attribute records. GDAL's S-57 driver reads them as Latin-1 (one
# codepoint per byte), so a name like "Écluses" (UTF-8 bytes C3 89 63
# 6C 75 73 65 73) comes back as the Python string "Ã\x89cluses" with
# codepoints U+00C3, U+0089, 'c', 'l', ...  Left uncorrected, this
# bleeds all the way into the front-end popups.
#
# `_safe_str` detects the pattern (any char ≤ U+00FF whose Latin-1
# encoding decodes cleanly as UTF-8) and reverses it.  It is a no-op
# for pure-ASCII strings and for strings already containing codepoints
# above U+00FF (where the mojibake pattern cannot apply).
def _safe_str(s):
    # Some IENC cells are DOUBLE-mojibaked (the string was re-interpreted as
    # Latin-1 twice before reaching us), so each pass only peels one layer
    # off.  Iterate until the string stops changing — but cap at 3 rounds
    # and reject any pass that introduces control characters.
    if s is None or not isinstance(s, str) or not s:
        return s
    MAX_ROUNDS = 3
    for _ in range(MAX_ROUNDS):
        # Cheap early-out for pure ASCII
        if all(ord(c) < 0x80 for c in s):
            return s
        # Only consider the candidate if every char fits in Latin-1 —
        # strings already containing non-Latin-1 Unicode have been
        # decoded correctly and should pass through.
        if any(ord(c) > 0xFF for c in s):
            return s
        try:
            cand = s.encode("latin-1").decode("utf-8")
        except UnicodeError:
            return s
        # Reject round-trips that produce control characters — those
        # usually mean the original wasn't mojibaked UTF-8 after all.
        if any(ord(c) < 0x20 and c not in "\t\n" for c in cand):
            return s
        if cand == s:
            return s
        s = cand
    return s


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
    # CNR (Compagnie Nationale du Rhône) cells covering Lyon → Mediterranean
    # — the gap that the VNF "RHONE_LYON_EDITION_1" bundle does NOT close.
    # Includes variant-edition cells like 3T5RHO01_2 (revision overlay).
    if re.match(r"^3T5RHO\d{2}(_\d+)?$", name):
        return "Rhône"
    if re.match(r"^(4V5|4V6)GA\d{3}$", name):
        return "Garonne (tidal)"
    if re.match(r"^1W7RH\d{3}$", name):
        return "Rhine"
    # 1W7SR is the SAAR (German Saarland), not the Saône — confirmed when
    # the 2022 European IENC bundle revealed the same prefix. Earlier
    # versions of this map labelled these cells "Saône (upper)" by
    # mistake; locks at Saarbrücken consequently failed the position
    # audit.  See FEATURES.md backlog note from 2026-04-24.
    if re.match(r"^1W7SR\d{3}$", name):
        return "Saar"
    if re.match(r"^1W7MO\d{3}$", name):
        return "Mosel"   # German Moselle (downstream of FR Apach border)
    if re.match(r"^1W7RRS\d{2}$", name):
        return "Canal du Rhône au Rhin"
    if name.startswith("7V7LEIE"):
        return "Leie"
    if name.startswith("7V7PLDU"):
        return "Canal Nieuwpoort–Dunkerque"
    if name.startswith("7V7ALB"):
        return "Albertkanaal"   # Albert Canal (Liège → Antwerp)
    # Generic catch-all for other Belgian cells (BE flemish-region 7V7
    # prefixes + the BE-prefix 06.2022 patch format like BE7GT017).
    if name.startswith("7V7") or re.match(r"^BE[A-Z0-9]+$", name):
        return "Belgium waterway"
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
        name = _safe_str(feat.GetField("OBJNAM")) or _safe_str(feat.GetField("NOBJNM")) or None
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
# Lock extraction (lokbsn layer — lock basins as polygons)
# ──────────────────────────────────────────────────────────────────────
def extract_locks_from_cell(cell_path: str, cell_name: str) -> list[dict]:
    """Return per-cell lock features. Uses IENC `lokbsn` (lock basin)
    polygons — one polygon per lock. Captures the most useful fields:

    - `horcll`  — lock usable length, metres
    - `horclw` / `HORWID` — lock usable width, metres
    - `OBJNAM` (English) / `NOBJNM` (French)
    - `INFORM` — often contains rise ("rise: 4.40m") or other notes
    """
    ds = ogr.Open(cell_path)
    if ds is None:
        return []
    lyr = ds.GetLayerByName("lokbsn")
    if lyr is None:
        return []
    out: list[dict] = []
    for feat in lyr:
        c = _feature_centroid(feat)
        if c is None:
            continue
        lon, lat = c
        # Prefer French name (NOBJNM) since the app is Francophone; fall back.
        name = _safe_str(feat.GetField("NOBJNM")) or _safe_str(feat.GetField("OBJNAM")) or None
        length = feat.GetField("horcll")
        width = feat.GetField("horclw") or feat.GetField("HORWID")
        inform = _safe_str(feat.GetField("INFORM")) or _safe_str(feat.GetField("NINFOM")) or None
        rise = None
        if inform:
            import re as _re
            m = _re.search(r"(\d+(?:\.\d+)?)\s*m", inform.lower().replace(",", "."))
            if m and "rise" in inform.lower() or (m and "chute" in inform.lower()):
                rise = float(m.group(1))
        out.append(
            {
                "name": name,
                "lat": round(lat, 6),
                "lon": round(lon, 6),
                "length_m": round(length, 2) if length and length > 0 else None,
                "width_m": round(width, 2) if width and width > 0 else None,
                "rise_m": rise,
                "inform": inform,
                "cell": cell_name,
                "waterway": _waterway_for_cell(cell_name),
            }
        )
    return out


def dedupe_locks(locks: list[dict]) -> list[dict]:
    """Collapse IENC locks that are the same physical basin across cells.
    Two locks within ~150 m with matching (normalised) name are merged;
    keep the one with the most field coverage."""
    def _norm(s: str | None) -> str:
        if not s:
            return ""
        s = s.lower()
        for pfx in ("ecluse de ", "lock of ", "écluse de ", "ecluse d'", "écluse d'"):
            if s.startswith(pfx):
                s = s[len(pfx):]
                break
        return s.strip()

    def _score(l: dict) -> int:
        return sum(1 for k in ("name", "length_m", "width_m", "rise_m") if l.get(k))

    by_key: dict[tuple, dict] = {}
    for l in locks:
        key = (_norm(l["name"]), round(l["lat"], 3), round(l["lon"], 3))
        cur = by_key.get(key)
        if cur is None or _score(l) > _score(cur):
            by_key[key] = l
    return list(by_key.values())


def locks_to_geojson(locks: list[dict]) -> dict:
    feats = []
    for l in locks:
        feats.append(
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [l["lon"], l["lat"]]},
                "properties": {
                    "name": l["name"],
                    "waterway": l["waterway"],
                    "length_m": l["length_m"],
                    "width_m": l["width_m"],
                    "rise_m": l["rise_m"],
                    "source": "VNF IENC (Licence Ouverte 2.0)",
                },
            }
        )
    return {"type": "FeatureCollection", "features": feats}


# ──────────────────────────────────────────────────────────────────────
# Mooring extraction (berths + PONTON — the useful moorings-for-visitors)
# ──────────────────────────────────────────────────────────────────────
def extract_moorings_from_cell(cell_path: str, cell_name: str) -> list[dict]:
    """Return mooring features from `berths` (wharfs/quays) and `PONTON`
    (pontoons). Excludes `MORFAC` because those are mainly navigation
    aids (dolphins/bollards) rather than places a boat can tie up for
    the night."""
    ds = ogr.Open(cell_path)
    if ds is None:
        return []
    out: list[dict] = []
    for layer_name, type_label in (("berths", "quay"), ("PONTON", "pontoon")):
        lyr = ds.GetLayerByName(layer_name)
        if lyr is None:
            continue
        for feat in lyr:
            c = _feature_centroid(feat)
            if c is None:
                continue
            lon, lat = c
            name = _safe_str(feat.GetField("NOBJNM")) or _safe_str(feat.GetField("OBJNAM")) or None
            inform = _safe_str(feat.GetField("NINFOM")) or _safe_str(feat.GetField("INFORM")) or None
            out.append(
                {
                    "type": type_label,
                    "name": name,
                    "lat": round(lat, 6),
                    "lon": round(lon, 6),
                    "inform": inform,
                    "cell": cell_name,
                    "waterway": _waterway_for_cell(cell_name),
                }
            )
    return out


def dedupe_moorings(moorings: list[dict]) -> list[dict]:
    """Collapse mooring features that are the same physical feature
    across cells / layers. Keys on (type, rounded coords) and keeps
    the one with a name over one without."""
    def _score(m: dict) -> int:
        return (1 if m.get("name") else 0) + (1 if m.get("inform") else 0)

    by_key: dict[tuple, dict] = {}
    for m in moorings:
        key = (m["type"], round(m["lat"], 4), round(m["lon"], 4))
        cur = by_key.get(key)
        if cur is None or _score(m) > _score(cur):
            by_key[key] = m
    return list(by_key.values())


# ──────────────────────────────────────────────────────────────────────
# Channel-axis extraction (wtwaxs — official dredged-channel centerline)
# ──────────────────────────────────────────────────────────────────────
def extract_channel_axis_from_cell(cell_path: str, cell_name: str) -> list[dict]:
    """Return per-cell channel-axis LineStrings. The `wtwaxs` layer holds
    the official *dredged navigation axis* (one LineString per pound /
    bief), which on meandering rivers like the Moselle or lower Seine
    differs materially from the OSM river geometry."""
    ds = ogr.Open(cell_path)
    if ds is None:
        return []
    lyr = ds.GetLayerByName("wtwaxs")
    if lyr is None:
        return []
    out: list[dict] = []
    for feat in lyr:
        geom = feat.GetGeometryRef()
        if not geom or geom.GetGeometryName() != "LINESTRING":
            continue
        n = geom.GetPointCount()
        if n < 2:
            continue
        coords = [[round(geom.GetX(i), 6), round(geom.GetY(i), 6)] for i in range(n)]
        name = _safe_str(feat.GetField("OBJNAM")) or None
        # French is more useful to French-speaking cruisers; fall back to English.
        inform = _safe_str(feat.GetField("NINFOM")) or _safe_str(feat.GetField("INFORM")) or None
        out.append(
            {
                "name": name,
                "inform": inform,
                "coords": coords,
                "cell": cell_name,
                "waterway": _waterway_for_cell(cell_name),
            }
        )
    return out


def dedupe_channel_axis(segments: list[dict]) -> list[dict]:
    """Overlapping cells can produce identical channel-axis LineStrings
    (same source data). Dedup on a hash of (waterway, first-point-5dp,
    last-point-5dp, point-count) — exact duplicates only, structural
    variants stay separate."""
    by_key: dict[tuple, dict] = {}
    for s in segments:
        c = s["coords"]
        key = (
            s["waterway"],
            (round(c[0][0], 5), round(c[0][1], 5)),
            (round(c[-1][0], 5), round(c[-1][1], 5)),
            len(c),
        )
        cur = by_key.get(key)
        if cur is None or ((s.get("inform") or "") > (cur.get("inform") or "")):
            by_key[key] = s
    return list(by_key.values())


def channel_axis_to_geojson(segments: list[dict]) -> dict:
    feats = []
    for s in segments:
        feats.append(
            {
                "type": "Feature",
                "geometry": {"type": "LineString", "coordinates": s["coords"]},
                "properties": {
                    "name": s["name"],
                    "inform": s["inform"],
                    "waterway": s["waterway"],
                    "source": "VNF IENC (Licence Ouverte 2.0)",
                },
            }
        )
    return {"type": "FeatureCollection", "features": feats}


# ──────────────────────────────────────────────────────────────────────
# Obstructions (OBSTRN — rocks, shoals, wrecks, foul areas, islets)
# ──────────────────────────────────────────────────────────────────────
# S-57 CATOBS category codes
_CATOBS_LABELS = {
    1: "snag / stump",
    2: "wellhead",
    3: "diffuser",
    4: "crib",
    5: "fish haven",
    6: "foul area",
    7: "foul ground",
    8: "ice boom",
    9: "ground tackle",
    10: "boom",
}
# S-57 WATLEV water-level codes
_WATLEV_LABELS = {
    1: "partly submerged at high water",
    2: "always dry",
    3: "always underwater / submerged",
    4: "covers and uncovers",
    5: "awash",
    6: "subject to inundation or flooding",
    7: "floating",
}


def extract_obstructions_from_cell(cell_path: str, cell_name: str) -> list[dict]:
    """Return per-cell obstruction features. IENC stores OBSTRN as
    polygon hazard areas; we emit a POINT at the centroid with the key
    navigational attributes so a marker can be placed on the map."""
    ds = ogr.Open(cell_path)
    if ds is None:
        return []
    lyr = ds.GetLayerByName("OBSTRN")
    if lyr is None:
        return []
    out: list[dict] = []
    for feat in lyr:
        c = _feature_centroid(feat)
        if c is None:
            continue
        lon, lat = c
        catobs = feat.GetField("CATOBS")
        watlev = feat.GetField("WATLEV")
        valsou = feat.GetField("VALSOU")
        name = _safe_str(feat.GetField("OBJNAM")) or _safe_str(feat.GetField("NOBJNM")) or None
        inform = _safe_str(feat.GetField("NINFOM")) or _safe_str(feat.GetField("INFORM")) or None
        out.append(
            {
                "name": name,
                "lat": round(lat, 6),
                "lon": round(lon, 6),
                "catobs": catobs,
                "catobs_label": _CATOBS_LABELS.get(catobs) if catobs else None,
                "watlev": watlev,
                "watlev_label": _WATLEV_LABELS.get(watlev) if watlev else None,
                "valsou_m": round(valsou, 2) if isinstance(valsou, (int, float)) and valsou not in (0, None) else None,
                "inform": inform,
                "cell": cell_name,
                "waterway": _waterway_for_cell(cell_name),
            }
        )
    return out


def dedupe_obstructions(obs: list[dict]) -> list[dict]:
    """Dedup by (waterway, 4dp coords, CATOBS). Keeps the record with
    more populated fields if there's a tie."""
    def _score(o: dict) -> int:
        return sum(1 for k in ("name", "inform", "watlev", "valsou_m") if o.get(k))

    by_key: dict[tuple, dict] = {}
    for o in obs:
        key = (o["waterway"], round(o["lat"], 4), round(o["lon"], 4), o["catobs"])
        cur = by_key.get(key)
        if cur is None or _score(o) > _score(cur):
            by_key[key] = o
    return list(by_key.values())


def obstructions_to_geojson(obs: list[dict]) -> dict:
    feats = []
    for o in obs:
        feats.append(
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [o["lon"], o["lat"]]},
                "properties": {
                    "name": o["name"],
                    "waterway": o["waterway"],
                    "catobs": o["catobs"],
                    "catobs_label": o["catobs_label"],
                    "watlev": o["watlev"],
                    "watlev_label": o["watlev_label"],
                    "valsou_m": o["valsou_m"],
                    "inform": o["inform"],
                    "source": "VNF IENC (Licence Ouverte 2.0)",
                },
            }
        )
    return {"type": "FeatureCollection", "features": feats}


def moorings_to_geojson(moorings: list[dict]) -> dict:
    feats = []
    for m in moorings:
        feats.append(
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [m["lon"], m["lat"]]},
                "properties": {
                    "type": m["type"],
                    "name": m["name"],
                    "waterway": m["waterway"],
                    "inform": m["inform"],
                    "source": "VNF IENC (Licence Ouverte 2.0)",
                },
            }
        )
    return {"type": "FeatureCollection", "features": feats}


# ──────────────────────────────────────────────────────────────────────
# Reconciliation: IENC data vs. the app's curated WAYPOINTS / MOORINGS
# ──────────────────────────────────────────────────────────────────────
def _haversine_m(lat1, lon1, lat2, lon2) -> float:
    """Great-circle distance in metres."""
    from math import radians, sin, cos, asin, sqrt
    R = 6_371_000.0
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    return 2 * R * asin(sqrt(a))


def _parse_app_data(html_path: str) -> tuple[list[dict], list[dict]]:
    """Extract waypoints (lock subset) and moorings from
    `french_canals_map.html`. Uses json5 to handle the JS-literal syntax
    (unquoted keys, trailing commas, // line comments) directly."""
    import re as _re
    if not os.path.exists(html_path):
        return [], []
    try:
        import json5 as _json5
    except ImportError:
        print("WARN: json5 not installed — reconciliation disabled. "
              "Install with: pip install json5", file=sys.stderr)
        return [], []
    with open(html_path) as f:
        text = f.read()

    def _extract_array(const_name: str) -> list[dict]:
        m = _re.search(rf"const\s+{const_name}\s*=\s*\[", text)
        if not m:
            return []
        # Walk brackets to find the matching close. Must be aware of
        # JS string literals AND line comments (because `// ]` would
        # otherwise fool the bracket counter).
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
            # Skip // line comments
            if ch == "/" and i + 1 < L and text[i + 1] == "/":
                while i < L and text[i] != "\n":
                    i += 1
                continue
            # Skip /* */ block comments
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
        block = text[start:i]
        try:
            return _json5.loads(block)
        except Exception as e:
            print(f"WARN: failed to parse {const_name}: {e}", file=sys.stderr)
            return []

    waypoints = _extract_array("WAYPOINTS")
    moorings = _extract_array("MOORINGS")
    return waypoints, moorings


def reconcile_locks(ienc_locks: list[dict], app_waypoints: list[dict],
                    max_dist_m: float = 200.0) -> list[dict]:
    """For each IENC lock, find the nearest app lock-waypoint. Emit rows
    sorted by distance — close matches first (likely-same lock with a
    possible position correction), far ones last (likely missing from
    the app entirely)."""
    app_locks = [w for w in app_waypoints if w.get("is_lock")]
    out = []
    for il in ienc_locks:
        best = None
        best_d = float("inf")
        for aw in app_locks:
            try:
                d = _haversine_m(il["lat"], il["lon"], float(aw["lat"]), float(aw["lon"]))
            except (TypeError, KeyError):
                continue
            if d < best_d:
                best_d = d
                best = aw
        out.append(
            {
                "ienc_name": il["name"],
                "ienc_waterway": il["waterway"],
                "ienc_lat": il["lat"],
                "ienc_lon": il["lon"],
                "ienc_length_m": il["length_m"],
                "ienc_width_m": il["width_m"],
                "ienc_rise_m": il["rise_m"],
                "app_id": best["id"] if best else None,
                "app_name": best["name"] if best else None,
                "app_lat": best["lat"] if best else None,
                "app_lon": best["lon"] if best else None,
                "distance_m": round(best_d, 1) if best else None,
                "match_status": (
                    "no_app_locks" if not app_locks
                    else "match" if best_d <= max_dist_m
                    else "candidate" if best_d <= 1000
                    else "no_match"
                ),
            }
        )
    return sorted(out, key=lambda r: (r["distance_m"] if r["distance_m"] is not None else 9e9))


def reconcile_moorings(ienc_moorings: list[dict], app_moorings: list[dict],
                       max_dist_m: float = 200.0) -> list[dict]:
    out = []
    for im in ienc_moorings:
        best = None
        best_d = float("inf")
        for am in app_moorings:
            try:
                d = _haversine_m(im["lat"], im["lon"], float(am["lat"]), float(am["lon"]))
            except (TypeError, KeyError):
                continue
            if d < best_d:
                best_d = d
                best = am
        out.append(
            {
                "ienc_type": im["type"],
                "ienc_name": im["name"],
                "ienc_waterway": im["waterway"],
                "ienc_lat": im["lat"],
                "ienc_lon": im["lon"],
                "app_id": best["id"] if best else None,
                "app_name": best["name"] if best else None,
                "app_type": best.get("type") if best else None,
                "distance_m": round(best_d, 1) if best else None,
                "match_status": (
                    "no_app_moorings" if not app_moorings
                    else "match" if best_d <= max_dist_m
                    else "candidate" if best_d <= 1000
                    else "no_match"
                ),
            }
        )
    return sorted(out, key=lambda r: (r["distance_m"] if r["distance_m"] is not None else 9e9))


def _write_csv(path: str, rows: list[dict], columns: list[str]) -> None:
    import csv as _csv
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", newline="") as f:
        w = _csv.DictWriter(f, fieldnames=columns, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow(r)


# ──────────────────────────────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────────────────────────────
def main() -> int:
    ap = argparse.ArgumentParser(
        description="Extract VNF IENC data (bridges, locks, moorings) into GeoJSON."
    )
    ap.add_argument(
        "--zip",
        action="append",
        required=True,
        help="Path to an IENC zip (repeatable; later zips override cells in earlier ones).",
    )
    ap.add_argument("--out", required=True,
                    help="Output path for bridges GeoJSON (primary product).")
    ap.add_argument("--out-locks", default=None,
                    help="Also extract lock basins → this GeoJSON path.")
    ap.add_argument("--out-moorings", default=None,
                    help="Also extract quays/pontoons → this GeoJSON path.")
    ap.add_argument("--out-channel-axis", default=None,
                    help="Also extract the `wtwaxs` navigation axis → this GeoJSON path.")
    ap.add_argument("--out-obstructions", default=None,
                    help="Also extract OBSTRN hazard areas → this GeoJSON path.")
    ap.add_argument(
        "--reconcile",
        default=None,
        help=(
            "Reconcile extracted IENC data against the app's curated WAYPOINTS / "
            "MOORINGS in this HTML file (typically `french_canals_map.html`). "
            "Emits {out}_locks_reconciliation.csv and {out}_moorings_reconciliation.csv "
            "next to --out. Manual review only — never auto-applied."
        ),
    )
    args = ap.parse_args()

    all_raw_bridges: list[dict] = []
    all_raw_locks: list[dict] = []
    all_raw_moorings: list[dict] = []
    all_raw_axis: list[dict] = []
    all_raw_obs: list[dict] = []
    zip_stats: list[tuple[str, int, int, int, int, int, int]] = []
    # (zip, cells, bridges, locks, moorings, axis, obstructions)

    with tempfile.TemporaryDirectory(prefix="ienc_") as tmp:
        for zp in args.zip:
            if not os.path.exists(zp):
                print(f"WARN: zip not found, skipping: {zp}", file=sys.stderr)
                continue
            sub = os.path.join(tmp, re.sub(r"[^A-Za-z0-9]+", "_", os.path.basename(zp)))
            cells = unpack_zip(zp, sub)
            raw_b: list[dict] = []
            raw_l: list[dict] = []
            raw_m: list[dict] = []
            raw_a: list[dict] = []
            raw_o: list[dict] = []
            for cell_name, cell_path in cells:
                raw_b.extend(extract_bridges_from_cell(cell_path, cell_name))
                if args.out_locks or args.reconcile:
                    raw_l.extend(extract_locks_from_cell(cell_path, cell_name))
                if args.out_moorings or args.reconcile:
                    raw_m.extend(extract_moorings_from_cell(cell_path, cell_name))
                if args.out_channel_axis:
                    raw_a.extend(extract_channel_axis_from_cell(cell_path, cell_name))
                if args.out_obstructions:
                    raw_o.extend(extract_obstructions_from_cell(cell_path, cell_name))
            zip_stats.append((zp, len(cells), len(raw_b), len(raw_l), len(raw_m), len(raw_a), len(raw_o)))
            all_raw_bridges.extend(raw_b)
            all_raw_locks.extend(raw_l)
            all_raw_moorings.extend(raw_m)
            all_raw_axis.extend(raw_a)
            all_raw_obs.extend(raw_o)

    # ── Bridges (primary product) ─────────────────────────────────────
    aggregated = aggregate_bridges(all_raw_bridges)
    deduped = dedupe_across_zips(aggregated)
    gj = to_geojson(deduped)
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    tmp_out = args.out + ".tmp"
    with open(tmp_out, "w") as f:
        json.dump(gj, f, separators=(",", ":"))
    os.replace(tmp_out, args.out)

    # ── Report ────────────────────────────────────────────────────
    print("\n=== IENC extraction summary ===")
    hdr = f"  {'ZIP':45s} {'CELLS':>5s} {'BRIDGES':>7s}"
    if args.out_locks or args.reconcile:    hdr += f" {'LOCKS':>5s}"
    if args.out_moorings or args.reconcile: hdr += f" {'MOORS':>5s}"
    if args.out_channel_axis:               hdr += f" {'AXIS':>5s}"
    if args.out_obstructions:               hdr += f" {'OBSTR':>5s}"
    print(hdr)
    for zp, cells, rb, rl, rm, ra, ro in zip_stats:
        row = f"  {os.path.basename(zp):45s} {cells:5d} {rb:7d}"
        if args.out_locks or args.reconcile:    row += f" {rl:5d}"
        if args.out_moorings or args.reconcile: row += f" {rm:5d}"
        if args.out_channel_axis:               row += f" {ra:5d}"
        if args.out_obstructions:               row += f" {ro:5d}"
        print(row)
    print(f"\n  Raw bridge features (all zips): {len(all_raw_bridges)}")
    print(f"  After per-name aggregation:     {len(aggregated)}")
    print(f"  After cross-zip dedup:          {len(deduped)}")
    print(f"\n  Waterway breakdown (final):")
    ww_count: dict[str, int] = defaultdict(int)
    for b in deduped:
        ww_count[b["waterway"]] += 1
    for ww in sorted(ww_count, key=lambda w: -ww_count[w]):
        print(f"    {ww:30s} {ww_count[ww]:4d}")
    print(f"\n  Wrote {args.out} ({os.path.getsize(args.out) / 1024:.1f} KB)")

    # ── Locks (optional) ──────────────────────────────────────────────
    deduped_locks: list[dict] = []
    if args.out_locks or args.reconcile:
        deduped_locks = dedupe_locks(all_raw_locks)
        if args.out_locks:
            os.makedirs(os.path.dirname(args.out_locks) or ".", exist_ok=True)
            tmp_lk = args.out_locks + ".tmp"
            with open(tmp_lk, "w") as f:
                json.dump(locks_to_geojson(deduped_locks), f, separators=(",", ":"))
            os.replace(tmp_lk, args.out_locks)
            print(f"  Wrote {args.out_locks} "
                  f"({len(deduped_locks)} locks, "
                  f"{os.path.getsize(args.out_locks) / 1024:.1f} KB)")

    # ── Moorings (optional) ───────────────────────────────────────────
    deduped_moorings: list[dict] = []
    if args.out_moorings or args.reconcile:
        deduped_moorings = dedupe_moorings(all_raw_moorings)
        if args.out_moorings:
            os.makedirs(os.path.dirname(args.out_moorings) or ".", exist_ok=True)
            tmp_mo = args.out_moorings + ".tmp"
            with open(tmp_mo, "w") as f:
                json.dump(moorings_to_geojson(deduped_moorings), f, separators=(",", ":"))
            os.replace(tmp_mo, args.out_moorings)
            print(f"  Wrote {args.out_moorings} "
                  f"({len(deduped_moorings)} moorings, "
                  f"{os.path.getsize(args.out_moorings) / 1024:.1f} KB)")

    # ── Channel axis (optional) ───────────────────────────────────────
    if args.out_channel_axis:
        deduped_axis = dedupe_channel_axis(all_raw_axis)
        os.makedirs(os.path.dirname(args.out_channel_axis) or ".", exist_ok=True)
        tmp_ax = args.out_channel_axis + ".tmp"
        with open(tmp_ax, "w") as f:
            json.dump(channel_axis_to_geojson(deduped_axis), f, separators=(",", ":"))
        os.replace(tmp_ax, args.out_channel_axis)
        print(f"  Wrote {args.out_channel_axis} "
              f"({len(deduped_axis)} axis segments, "
              f"{os.path.getsize(args.out_channel_axis) / 1024:.1f} KB)")

    # ── Obstructions (optional) ───────────────────────────────────────
    if args.out_obstructions:
        deduped_obs = dedupe_obstructions(all_raw_obs)
        os.makedirs(os.path.dirname(args.out_obstructions) or ".", exist_ok=True)
        tmp_ob = args.out_obstructions + ".tmp"
        with open(tmp_ob, "w") as f:
            json.dump(obstructions_to_geojson(deduped_obs), f, separators=(",", ":"))
        os.replace(tmp_ob, args.out_obstructions)
        print(f"  Wrote {args.out_obstructions} "
              f"({len(deduped_obs)} obstructions, "
              f"{os.path.getsize(args.out_obstructions) / 1024:.1f} KB)")

    # ── Reconciliation (optional) ─────────────────────────────────────
    if args.reconcile:
        if not os.path.exists(args.reconcile):
            print(f"WARN: --reconcile target not found: {args.reconcile}", file=sys.stderr)
        else:
            app_wp, app_mo = _parse_app_data(args.reconcile)
            print(f"\n  Reconciling against {args.reconcile}:")
            print(f"    App WAYPOINTS: {len(app_wp)} "
                  f"({sum(1 for w in app_wp if w.get('is_lock'))} locks)")
            print(f"    App MOORINGS:  {len(app_mo)}")

            base = os.path.splitext(args.out)[0]
            locks_csv = base + "_locks_reconciliation.csv"
            moor_csv = base + "_moorings_reconciliation.csv"

            lock_rows = reconcile_locks(deduped_locks, app_wp)
            _write_csv(locks_csv, lock_rows, [
                "match_status", "distance_m",
                "ienc_name", "ienc_waterway", "ienc_lat", "ienc_lon",
                "ienc_length_m", "ienc_width_m", "ienc_rise_m",
                "app_id", "app_name", "app_lat", "app_lon",
            ])
            moor_rows = reconcile_moorings(deduped_moorings or all_raw_moorings, app_mo)
            _write_csv(moor_csv, moor_rows, [
                "match_status", "distance_m",
                "ienc_type", "ienc_name", "ienc_waterway", "ienc_lat", "ienc_lon",
                "app_id", "app_name", "app_type",
            ])
            print(f"    Wrote {locks_csv} ({len(lock_rows)} rows)")
            print(f"    Wrote {moor_csv}  ({len(moor_rows)} rows)")
            _print_reconcile_summary("Locks", lock_rows)
            _print_reconcile_summary("Moorings", moor_rows)
    return 0


def _print_reconcile_summary(label: str, rows: list[dict]) -> None:
    tally: dict[str, int] = defaultdict(int)
    for r in rows:
        tally[r["match_status"]] += 1
    print(f"    {label} status: " + ", ".join(f"{k}={v}" for k, v in sorted(tally.items())))


if __name__ == "__main__":
    sys.exit(main())
