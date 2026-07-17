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
    assert ei._waterway_for_cell("1W7SR080") == "Saar"   # corrected 2026-04-25 — not Saône
    assert ei._waterway_for_cell("1W7MO050") == "Mosel"
    assert ei._waterway_for_cell("3T5RHO15") == "Rhône"   # CNR Rhône Lyon→Med
    assert ei._waterway_for_cell("7V7ALB10") == "Albertkanaal"
    assert ei._waterway_for_cell("7V7BEDIJ") == "Belgium waterway"
    assert ei._waterway_for_cell("BE7GT017") == "Belgium waterway"
    assert ei._waterway_for_cell("4V7OIS03") == "Oise"
    assert ei._waterway_for_cell("4V5GA040") == "Garonne (tidal)"
    assert ei._waterway_for_cell("4V6GA070") == "Garonne (tidal)"
    assert ei._waterway_for_cell("7V7LEIE4") == "Leie"
    assert ei._waterway_for_cell("7V7PLDU4") == "Canal Nieuwpoort–Dunkerque"


def test_waterway_for_cell_austria_donau():
    # viadonau IENC (Tier 2, Inland ENC Europe 05.2022 bundle):
    # 2W7D#### route cells + 2WBD* berthing/harbour detail cells.
    assert ei._waterway_for_cell("2W7D1870") == "Donau"
    assert ei._waterway_for_cell("2W7D2200") == "Donau"
    assert ei._waterway_for_cell("2WBD1905") == "Donau"
    assert ei._waterway_for_cell("2WBDHALB") == "Donau"
    assert ei._waterway_for_cell("2WBDK017") == "Donau"


def test_waterway_for_cell_slovakia_danube():
    # Dopravný úrad IENC (Danube Wave 1, Inland ENC Europe 05.2022 bundle):
    # 2D7D#### km-numbered route cells + 2D7DK### Gabčíkovo bypass cells.
    assert ei._waterway_for_cell("2D7D1709") == "Donau"
    assert ei._waterway_for_cell("2D7D1752") == "Donau"
    assert ei._waterway_for_cell("2D7D1872") == "Donau"
    assert ei._waterway_for_cell("2D7DK000") == "Dunajský Kanál"
    assert ei._waterway_for_cell("2D7DK012") == "Dunajský Kanál"
    assert ei._waterway_for_cell("2D7DK027") == "Dunajský Kanál"


def test_waterway_for_cell_hungary_danube():
    # OVF/RSOE IENC (Danube Wave 1, Inland ENC Europe 05.2022 bundle):
    # 1H7D#### km-numbered Danube cells + 1H7SZD Szentendrei-Duna side arm.
    assert ei._waterway_for_cell("1H7D1430") == "Donau"
    assert ei._waterway_for_cell("1H7D1650") == "Donau"
    assert ei._waterway_for_cell("1H7D1810") == "Donau"
    assert ei._waterway_for_cell("1H7SZD00") == "Szentendrei-Duna"
    # Tisza cells are deliberately unmapped (zip not fed in — no map geometry)
    assert ei._waterway_for_cell("1H7TI200") == "Unknown waterway"


def test_waterway_for_cell_danube_wave2():
    # HR/RS/RO/BG Danube (Danube Wave 2, Inland ENC Europe 05.2022 bundle).
    assert ei._waterway_for_cell("5C7D1306") == "Donau"   # Croatia (km 1306–1433)
    assert ei._waterway_for_cell("5C7D1433") == "Donau"
    assert ei._waterway_for_cell("2P7D0866") == "Donau"   # Serbia (km 866–1433)
    assert ei._waterway_for_cell("2P7D1433") == "Donau"
    assert ei._waterway_for_cell("3B7D0375") == "Donau"   # Bulgaria (km 375–610)
    assert ei._waterway_for_cell("3B7D0610") == "Donau"
    assert ei._waterway_for_cell("3R7D0000") == "Donau"   # Romania mm/km route cells
    assert ei._waterway_for_cell("3R7D1070") == "Donau"
    assert ei._waterway_for_cell("3R7D94HM") == "Donau"   # harbour cell
    assert ei._waterway_for_cell("3R7DBB01") == "Donau"   # Bala–Borcea side arm
    assert ei._waterway_for_cell("3RACOB01") == "Donau"   # bathymetric overlay cells
    assert ei._waterway_for_cell("3RABCT01") == "Donau"
    assert ei._waterway_for_cell("3RADOB01") == "Donau"


def test_waterway_for_cell_cdmn_before_generic_ro_danube():
    # CDMN cells must be checked BEFORE the generic 3R7D Romania rule.
    assert ei._waterway_for_cell("3R7DCC01") == "Canalul Dunăre-Marea Neagră"
    assert ei._waterway_for_cell("3R7DCC07") == "Canalul Dunăre-Marea Neagră"
    assert ei._waterway_for_cell("3RB4DCC3") == "Canalul Dunăre-Marea Neagră"
    assert ei._waterway_for_cell("3RB4DCC4") == "Canalul Dunăre-Marea Neagră"
    # Drava/Sava/Tisa and the Poarta Albă–Midia Năvodari branch are
    # deliberately unmapped (their zips are not fed in — no map geometry):
    assert ei._waterway_for_cell("2P7SA010") == "Unknown waterway"
    assert ei._waterway_for_cell("2P7TI010") == "Unknown waterway"
    assert ei._waterway_for_cell("3R7PAM01") == "Unknown waterway"


def test_safe_str_drops_surrogate_garbage():
    """SK/HU cells carry raw binary junk in some text attributes; GDAL
    surfaces it with surrogateescape codepoints. Not text — must become
    None rather than crash json/csv writers or render as mojibake."""
    garbage = "T\udcc4nitou" + "\udc80\udcff"
    assert ei._safe_str(garbage) is None
    # Normal strings (ASCII, mojibake-repairable, real Unicode) unaffected:
    assert ei._safe_str("Pont de Pierre") == "Pont de Pierre"
    assert ei._safe_str("Gabčíkovo") == "Gabčíkovo"


def test_unpack_zip_bare_cell_and_appledouble(tmp_path):
    """The Slovakia bundles ship bare `.000` cells at the zip root (no
    ENC_ROOT folder), and the ENC-SK.zip aggregate adds `__MACOSX/._*.000`
    AppleDouble junk. unpack_zip must find the former and skip the latter."""
    import zipfile
    zp = tmp_path / "2D7D1709.zip"
    with zipfile.ZipFile(zp, "w") as z:
        z.writestr("2D7D1709.000", b"not-a-real-cell")
        z.writestr("__MACOSX/._2D7D1709.000", b"appledouble-junk")
        z.writestr("ENC-SK/2D7D1723.000", b"also-not-real")
    dest = tmp_path / "out"
    cells = ei.unpack_zip(str(zp), str(dest))
    names = sorted(n for n, _ in cells)
    assert names == ["2D7D1709", "2D7D1723"]


def test_waterway_for_cell_switzerland_hochrhein():
    # Swiss ports authority Hochrhein cell (single-cell 2021 edition).
    assert ei._waterway_for_cell("4C7RH149") == "Hochrhein"


def test_waterway_for_cell_belgium_specific():
    # Flemish DVW mappack prefixes (Tier 2). Names align with
    # data/waterway_constraints.json keys where they exist.
    assert ei._waterway_for_cell("7V7BZS03") == "Boven-Zeeschelde"
    assert ei._waterway_for_cell("7V7BOSC2") == "Bovenschelde"
    assert ei._waterway_for_cell("7V7DEND1") == "Dender"
    assert ei._waterway_for_cell("7V7YZER4") == "IJzer"
    assert ei._waterway_for_cell("7V7RUP02") == "Rupel"
    assert ei._waterway_for_cell("7V7DURME") == "Durme"
    assert ei._waterway_for_cell("7V7GENO5") == "Kanaal Gent-Oostende"
    assert ei._waterway_for_cell("7V7ZEEK1") == "Zeekanaal Brussel-Schelde"
    assert ei._waterway_for_cell("7V7ZWV01") == "Zuid-Willemsvaart"
    assert ei._waterway_for_cell("7V7BOHE3") == "Kanaal Bocholt-Herentals"
    assert ei._waterway_for_cell("7V7DTS04") == "Kanaal Dessel-Turnhout-Schoten"
    assert ei._waterway_for_cell("7V7KBKO1") == "Kanaal Bossuit-Kortrijk"
    assert ei._waterway_for_cell("7V7KLEDI") == "Kanaal Leuven-Dijle"
    assert ei._waterway_for_cell("7V7KRLEI") == "Kanaal Roeselare-Leie"
    assert ei._waterway_for_cell("7V7RGENT") == "Ringvaart om Gent"
    assert ei._waterway_for_cell("7V7RGEN1") == "Ringvaart om Gent"
    assert ei._waterway_for_cell("8V8POA01") == "Port of Antwerp"
    # Small/ambiguous cells stay in the country catch-all:
    assert ei._waterway_for_cell("7V7SPIKA") == "Belgium waterway"
    assert ei._waterway_for_cell("7V7LOKAN") == "Belgium waterway"


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


# ── Task 4: lock / mooring / reconciliation tests ─────────────────────

def test_haversine_m_zero_for_same_point():
    assert ei._haversine_m(48.85, 2.35, 48.85, 2.35) == 0.0


def test_haversine_m_approx_paris_london():
    # Paris (48.8566, 2.3522) → London (51.5074, -0.1278) ≈ 343 km
    d = ei._haversine_m(48.8566, 2.3522, 51.5074, -0.1278)
    assert 340_000 <= d <= 346_000, f"got {d:.0f}m"


def test_dedupe_locks_merges_close_same_name_keeps_richer():
    locks = [
        {"name": "Ecluse d'Apach", "lat": 49.399, "lon": 6.267,
         "length_m": None, "width_m": None, "rise_m": None,
         "inform": None, "cell": "4V5MOS01", "waterway": "Moselle"},
        {"name": "Ecluse d'Apach", "lat": 49.3992, "lon": 6.2672,
         "length_m": 176.36, "width_m": 12.0, "rise_m": 4.40,
         "inform": "rise: 4.40m", "cell": "4V5MOS01", "waterway": "Moselle"},
    ]
    result = ei.dedupe_locks(locks)
    assert len(result) == 1
    assert result[0]["length_m"] == 176.36  # richer record won


def test_dedupe_locks_keeps_same_name_different_waterway():
    locks = [
        {"name": "Ecluse du Moulin", "lat": 47.0, "lon": 4.0,
         "length_m": 40, "width_m": 5, "rise_m": 2, "inform": None,
         "cell": "X", "waterway": "Saône"},
        {"name": "Ecluse du Moulin", "lat": 49.0, "lon": 6.0,
         "length_m": 40, "width_m": 5, "rise_m": 2, "inform": None,
         "cell": "Y", "waterway": "Moselle"},
    ]
    assert len(ei.dedupe_locks(locks)) == 2


def test_reconcile_locks_finds_close_match_within_200m():
    ienc_locks = [
        {"name": "Ecluse d'Apach", "lat": 49.399, "lon": 6.267,
         "length_m": 176, "width_m": 12, "rise_m": 4.4,
         "inform": None, "cell": "X", "waterway": "Moselle"},
    ]
    app_waypoints = [
        {"id": "w_apach", "name": "Apach", "lat": 49.3993, "lon": 6.2668,
         "is_lock": True, "route": 30, "section": 5},  # ~25 m away
        {"id": "w_other", "name": "Nowhere", "lat": 48.0, "lon": 2.0,
         "is_lock": True, "route": 99, "section": 9},
    ]
    result = ei.reconcile_locks(ienc_locks, app_waypoints)
    assert len(result) == 1
    row = result[0]
    assert row["match_status"] == "match"
    assert row["app_id"] == "w_apach"
    assert row["distance_m"] < 100


def test_reconcile_locks_marks_no_match_when_all_far():
    ienc_locks = [
        {"name": "Ecluse X", "lat": 49.0, "lon": 6.0,
         "length_m": 40, "width_m": 5, "rise_m": 2,
         "inform": None, "cell": "X", "waterway": "Moselle"},
    ]
    app_waypoints = [
        {"id": "w_far", "name": "Far", "lat": 43.0, "lon": 1.0,
         "is_lock": True, "route": 1, "section": 1},
    ]
    result = ei.reconcile_locks(ienc_locks, app_waypoints)
    assert result[0]["match_status"] == "no_match"
    assert result[0]["distance_m"] > 1000


def test_reconcile_locks_ignores_non_lock_waypoints():
    ienc_locks = [
        {"name": "Ecluse X", "lat": 49.0, "lon": 6.0,
         "length_m": 40, "width_m": 5, "rise_m": 2,
         "inform": None, "cell": "X", "waterway": "Moselle"},
    ]
    # Waypoint is at the same spot but is_lock=False — must be ignored
    app_waypoints = [
        {"id": "w_town", "name": "Some Town", "lat": 49.0, "lon": 6.0,
         "is_lock": False, "route": 1, "section": 1},
    ]
    result = ei.reconcile_locks(ienc_locks, app_waypoints)
    assert result[0]["match_status"] == "no_app_locks"


def test_locks_to_geojson_shape():
    locks = [
        {"name": "Ecluse X", "waterway": "Moselle", "lat": 49.0, "lon": 6.0,
         "length_m": 176.36, "width_m": 12.0, "rise_m": 4.4,
         "inform": "rise: 4.40m", "cell": "X"},
    ]
    gj = ei.locks_to_geojson(locks)
    assert gj["type"] == "FeatureCollection"
    assert len(gj["features"]) == 1
    p = gj["features"][0]["properties"]
    assert p["length_m"] == 176.36
    assert p["width_m"] == 12.0
    assert "Licence Ouverte" in p["source"]


# ── Channel axis tests ────────────────────────────────────────────────

def test_dedupe_channel_axis_exact_duplicates_collapse():
    seg = {
        "name": "Axe de navigation", "inform": "Reach of APACH",
        "waterway": "Moselle",
        "coords": [[6.267, 49.399], [6.270, 49.402], [6.273, 49.405]],
        "cell": "4V5MOS01",
    }
    duplicate = dict(seg)  # same object identity-wise but new dict
    result = ei.dedupe_channel_axis([seg, duplicate])
    assert len(result) == 1


def test_dedupe_channel_axis_different_waterways_kept():
    s1 = {"name": "Axe", "inform": None, "waterway": "Moselle",
          "coords": [[6.0, 49.0], [6.1, 49.1]], "cell": "X"}
    s2 = {"name": "Axe", "inform": None, "waterway": "Seine",
          "coords": [[6.0, 49.0], [6.1, 49.1]], "cell": "Y"}
    assert len(ei.dedupe_channel_axis([s1, s2])) == 2


def test_channel_axis_to_geojson_shape():
    segs = [{"name": "Axe", "inform": "info", "waterway": "Moselle",
             "coords": [[6.0, 49.0], [6.1, 49.1]], "cell": "X"}]
    gj = ei.channel_axis_to_geojson(segs)
    assert gj["type"] == "FeatureCollection"
    f = gj["features"][0]
    assert f["geometry"]["type"] == "LineString"
    assert f["geometry"]["coordinates"] == [[6.0, 49.0], [6.1, 49.1]]
    assert "Licence Ouverte" in f["properties"]["source"]


# ── Obstruction tests ─────────────────────────────────────────────────

def test_catobs_labels_known_codes():
    assert ei._CATOBS_LABELS[6] == "foul area"
    assert ei._CATOBS_LABELS[7] == "foul ground"


def test_watlev_labels_known_codes():
    assert ei._WATLEV_LABELS[1] == "partly submerged at high water"
    assert ei._WATLEV_LABELS[3] == "always underwater / submerged"


def test_dedupe_obstructions_keeps_richer_record():
    bare = {"name": None, "lat": 45.0, "lon": 4.0, "catobs": 7,
            "catobs_label": "foul ground", "watlev": None, "watlev_label": None,
            "valsou_m": None, "inform": None, "cell": "X", "waterway": "Saône"}
    rich = {"name": "îlot", "lat": 45.0, "lon": 4.0, "catobs": 7,
            "catobs_label": "foul ground", "watlev": 1, "watlev_label": "partly submerged",
            "valsou_m": None, "inform": "small island", "cell": "X", "waterway": "Saône"}
    result = ei.dedupe_obstructions([bare, rich])
    assert len(result) == 1
    assert result[0]["name"] == "îlot"


def test_dedupe_obstructions_different_catobs_kept():
    o1 = {"name": None, "lat": 45.0, "lon": 4.0, "catobs": 6,
          "catobs_label": "foul area", "watlev": None, "watlev_label": None,
          "valsou_m": None, "inform": None, "cell": "X", "waterway": "Saône"}
    o2 = dict(o1); o2["catobs"] = 7
    assert len(ei.dedupe_obstructions([o1, o2])) == 2


def test_obstructions_to_geojson_shape():
    obs = [{"name": "îlot", "lat": 45.0, "lon": 4.0, "catobs": 7,
            "catobs_label": "foul ground", "watlev": 1, "watlev_label": "partly submerged",
            "valsou_m": None, "inform": "small island", "cell": "X", "waterway": "Saône"}]
    gj = ei.obstructions_to_geojson(obs)
    assert gj["type"] == "FeatureCollection"
    p = gj["features"][0]["properties"]
    assert p["catobs_label"] == "foul ground"
    assert p["watlev_label"] == "partly submerged"
    assert "Licence Ouverte" in p["source"]


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
