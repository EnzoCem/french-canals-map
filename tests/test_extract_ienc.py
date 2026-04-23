"""Unit tests for extract_ienc.py

Run from project root:
    source venv/bin/activate
    python -m pytest tests/test_extract_ienc.py -v
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import extract_ienc as ei  # noqa: E402


# ── Pure-function tests (no GDAL) ─────────────────────────────────────

def test_waterway_for_cell_seine():
    assert ei._waterway_for_cell("4V7SEI10") == "Seine"
    assert ei._waterway_for_cell("4V7SEI01") == "Seine"
    assert ei._waterway_for_cell("4V7SEI17") == "Seine"
    assert ei._waterway_for_cell("4V7SEI18") == "Seine (Amont)"
    assert ei._waterway_for_cell("4V7SEI27") == "Seine (Amont)"


def test_waterway_for_cell_other_waterways():
    assert ei._waterway_for_cell("4V5MOS01") == "Moselle"
    assert ei._waterway_for_cell("4V5001DE") == "Canal Dunkerque–Escaut"
    assert ei._waterway_for_cell("4V5RHO00") == "Rhône"
    assert ei._waterway_for_cell("4V5SAO05") == "Saône"
    assert ei._waterway_for_cell("1W7RH160") == "Rhine"  # NOT Rhône — spike finding
    assert ei._waterway_for_cell("1W7SR080") == "Saône (upper)"
    assert ei._waterway_for_cell("4V7OIS03") == "Oise"
    assert ei._waterway_for_cell("4V5GA040") == "Garonne (tidal)"
    assert ei._waterway_for_cell("4V6GA070") == "Garonne (tidal)"
    assert ei._waterway_for_cell("7V7LEIE4") == "Leie"
    assert ei._waterway_for_cell("7V7PLDU4") == "Canal Nieuwpoort–Dunkerque"


def test_waterway_for_cell_lowercase_accepted():
    # Just in case a zip has lowercase cell filenames.
    assert ei._waterway_for_cell("4v7sei10") == "Seine"


def test_waterway_for_cell_unknown():
    assert ei._waterway_for_cell("XYZZY999") == "Unknown waterway"


def test_aggregate_bridges_drops_no_verclr():
    """A bridge with no VERCLR from any span should be dropped entirely."""
    raw = [
        {
            "name": "Pont X",
            "waterway": "Seine",
            "lat": 48.85,
            "lon": 2.35,
            "verclr_m": None,
            "horclr_m": 40,
            "catbrg": ["1"],
            "cell": "4V7SEI14",
        }
    ]
    assert ei.aggregate_bridges(raw) == []


def test_aggregate_bridges_takes_minimum_verclr():
    """Three spans of the same named bridge → one feature with the
    minimum VERCLR (worst-case for the vessel)."""
    raw = [
        {"name": "Pont A", "waterway": "Seine", "lat": 48.85, "lon": 2.35,
         "verclr_m": 10.35, "horclr_m": 23, "catbrg": ["1"], "cell": "X"},
        {"name": "Pont A", "waterway": "Seine", "lat": 48.85, "lon": 2.35,
         "verclr_m": 10.40, "horclr_m": 23, "catbrg": ["1"], "cell": "X"},
        {"name": "Pont A", "waterway": "Seine", "lat": 48.85, "lon": 2.35,
         "verclr_m": 8.02, "horclr_m": 25, "catbrg": ["1"], "cell": "X"},
    ]
    result = ei.aggregate_bridges(raw)
    assert len(result) == 1
    assert result[0]["verclr_m"] == 8.02
    assert result[0]["span_count"] == 3


def test_aggregate_bridges_unnamed_kept_when_verclr_present():
    raw = [
        {"name": None, "waterway": "Rhine", "lat": 48.0, "lon": 7.8,
         "verclr_m": 6.5, "horclr_m": 30, "catbrg": ["1"], "cell": "1W7RH250"},
    ]
    result = ei.aggregate_bridges(raw)
    assert len(result) == 1
    assert result[0]["name"] is None
    assert result[0]["verclr_m"] == 6.5


def test_aggregate_bridges_unnamed_dropped_if_no_verclr():
    raw = [
        {"name": None, "waterway": "Rhine", "lat": 48.0, "lon": 7.8,
         "verclr_m": None, "horclr_m": 30, "catbrg": ["1"], "cell": "1W7RH250"},
    ]
    assert ei.aggregate_bridges(raw) == []


def test_aggregate_bridges_same_name_different_waterway_not_merged():
    """Two 'Pont du Chemin de Fer' on different rivers should stay separate."""
    raw = [
        {"name": "Pont du Chemin de Fer", "waterway": "Seine", "lat": 48.9, "lon": 2.3,
         "verclr_m": 7.0, "horclr_m": 30, "catbrg": ["1"], "cell": "4V7SEI14"},
        {"name": "Pont du Chemin de Fer", "waterway": "Moselle", "lat": 49.1, "lon": 6.2,
         "verclr_m": 8.0, "horclr_m": 30, "catbrg": ["1"], "cell": "4V5MOS03"},
    ]
    result = ei.aggregate_bridges(raw)
    assert len(result) == 2


def test_dedupe_across_zips_picks_lowest_verclr():
    """When two zips provide the same bridge, keep the more conservative
    (lower) VERCLR — worst case for the boat."""
    bridges = [
        {"name": "Pont A", "waterway": "Seine", "lat": 48.85, "lon": 2.35,
         "verclr_m": 9.5, "horclr_m": 40, "span_count": 2, "cells": ["SEI14"]},
        {"name": "Pont A", "waterway": "Seine", "lat": 48.85, "lon": 2.35,
         "verclr_m": 8.9, "horclr_m": 40, "span_count": 3, "cells": ["SEI14"]},
    ]
    result = ei.dedupe_across_zips(bridges)
    assert len(result) == 1
    assert result[0]["verclr_m"] == 8.9


def test_to_geojson_shape():
    bridges = [
        {"name": "Pont de Pierre", "waterway": "Garonne (tidal)",
         "lat": 44.838, "lon": -0.572, "verclr_m": 5.6, "horclr_m": 45,
         "span_count": 1, "cells": ["4V5GA030"]},
    ]
    gj = ei.to_geojson(bridges)
    assert gj["type"] == "FeatureCollection"
    assert len(gj["features"]) == 1
    f = gj["features"][0]
    assert f["type"] == "Feature"
    assert f["geometry"] == {"type": "Point", "coordinates": [-0.572, 44.838]}
    assert f["properties"]["name"] == "Pont de Pierre"
    assert f["properties"]["verclr_m"] == 5.6
    assert "Licence Ouverte" in f["properties"]["source"]


# ── Integration test (requires GDAL + real zip) ───────────────────────

def test_integration_fr_zip_produces_bridges():
    """End-to-end: FR.zip's Moselle cells should produce known-good
    bridge clearance features."""
    import extract_ienc as ei  # re-import for clarity
    from osgeo import ogr  # noqa: F401 — ensures GDAL is importable

    zip_path = "ienc/FR.zip"
    if not os.path.exists(zip_path):
        import pytest
        pytest.skip(f"{zip_path} not available in test environment")

    import tempfile
    with tempfile.TemporaryDirectory(prefix="ienc_test_") as tmp:
        cells = ei.unpack_zip(zip_path, tmp)
        # Focus on just Moselle cells for speed + reliability
        moselle_cells = [(n, p) for (n, p) in cells if n.startswith("4V5MOS")]
        assert len(moselle_cells) >= 5, "Expected several Moselle cells in FR.zip"

        raw = []
        for n, p in moselle_cells:
            raw.extend(ei.extract_bridges_from_cell(p, n))

        # Sanity: at least some VERCLR values present, all in a
        # reasonable real-world range (1 m to 30 m for river bridges).
        with_vc = [b for b in raw if b["verclr_m"] is not None]
        assert len(with_vc) >= 10, f"Too few VERCLR bridges: {len(with_vc)}"
        for b in with_vc:
            assert 1.0 <= b["verclr_m"] <= 30.0, f"Out-of-range VERCLR: {b}"

        # All Moselle bridges classify as 'Moselle' waterway
        assert all(b["waterway"] == "Moselle" for b in raw)

        # Aggregate doesn't lose all features
        aggregated = ei.aggregate_bridges(raw)
        assert len(aggregated) > 0
        assert all(b["verclr_m"] is not None for b in aggregated)
