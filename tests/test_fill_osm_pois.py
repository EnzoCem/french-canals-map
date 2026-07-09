"""Unit tests for fill_osm_pois.py pure functions.

Network-dependent code is NOT tested here — see test_fill_osm_pois_integration.py
(out of scope for Wave 2)."""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fill_osm_pois import (
    norm_name, haversine_m, osm_tags_to_facilities, osm_tags_to_mooring_type,
    is_duplicate_of_curated, area_clause, moorings_ql, lock_gates_ql,
    riverside_towns_ql, prune_stale_osm, ALL_COUNTRIES,
)


# ── norm_name ────────────────────────────────────────────────────────────────

def test_norm_name_lowercases_and_strips():
    assert norm_name('Port de Plaisance Auxerre') == 'port de plaisance auxerre'

def test_norm_name_strips_diacritics():
    assert norm_name("L'Yonne") == "l'yonne"
    assert norm_name('Tübingen') == 'tubingen'

def test_norm_name_collapses_whitespace():
    assert norm_name('Le  Havre  ') == 'le havre'

def test_norm_name_handles_none():
    assert norm_name(None) == ''


# ── haversine_m ──────────────────────────────────────────────────────────────

def test_haversine_zero_distance():
    assert haversine_m(48.85, 2.35, 48.85, 2.35) == 0.0

def test_haversine_known_distance():
    # Paris (48.8566, 2.3522) → London (51.5074, -0.1278) ≈ 343 km
    d = haversine_m(48.8566, 2.3522, 51.5074, -0.1278)
    assert 340_000 < d < 346_000, f'expected ~343 km, got {d:.0f} m'

def test_haversine_short_distance():
    # 0.001 deg latitude ≈ 111 m at any longitude
    d = haversine_m(48.0, 2.0, 48.001, 2.0)
    assert 109 < d < 113, f'expected ~111 m, got {d:.0f} m'


# ── osm_tags_to_facilities ───────────────────────────────────────────────────

def test_facilities_all_amenities():
    tags = {'drinking_water': 'yes', 'electricity': 'yes', 'shower': 'yes', 'toilets': 'yes', 'waste_disposal': 'yes'}
    f = osm_tags_to_facilities(tags)
    # Order: W (water), E (electric), S (shower), T (toilet), P (pump-out)
    assert f == 'W/E/S/T/P'

def test_facilities_partial():
    tags = {'electricity': 'yes', 'drinking_water': 'yes'}
    assert osm_tags_to_facilities(tags) == 'W/E'

def test_facilities_no_amenities():
    assert osm_tags_to_facilities({'leisure': 'marina'}) == ''

def test_facilities_normalises_yes_only():
    # OSM uses 'yes', 'limited', 'no'. We treat anything non-'no' as present.
    tags = {'drinking_water': 'limited', 'electricity': 'no'}
    assert osm_tags_to_facilities(tags) == 'W'


# ── osm_tags_to_mooring_type ─────────────────────────────────────────────────

def test_mooring_type_marina_is_port():
    assert osm_tags_to_mooring_type({'leisure': 'marina'}) == 'port'

def test_mooring_type_mooring_yes_is_halte():
    assert osm_tags_to_mooring_type({'mooring': 'yes'}) == 'halte'
    assert osm_tags_to_mooring_type({'mooring': 'public'}) == 'halte'
    assert osm_tags_to_mooring_type({'mooring': 'guest'}) == 'halte'

def test_mooring_type_fuel_is_fuel():
    assert osm_tags_to_mooring_type({'waterway': 'fuel'}) == 'fuel'

def test_mooring_type_marina_beats_mooring():
    # Some marinas tag both — marina wins (it's the more specific facility)
    assert osm_tags_to_mooring_type({'leisure': 'marina', 'mooring': 'yes'}) == 'port'

def test_mooring_type_unknown_returns_halte():
    # Default fallback for any "moored boat" OSM tag we didn't anticipate
    assert osm_tags_to_mooring_type({'amenity': 'boat_storage'}) == 'halte'


# ── is_duplicate_of_curated ──────────────────────────────────────────────────

def test_dedup_exact_match_within_radius():
    curated = [{'name': 'Port de Plaisance Auxerre', 'lat': 47.7980, 'lon': 3.5670}]
    # Same name, 50 m away — should be flagged as duplicate
    assert is_duplicate_of_curated('Port de Plaisance Auxerre', 47.7984, 3.5673, curated) is True

def test_dedup_name_match_too_far():
    curated = [{'name': 'Port de Plaisance Auxerre', 'lat': 47.7980, 'lon': 3.5670}]
    # Same name but 5 km away — not a duplicate (different place)
    assert is_duplicate_of_curated('Port de Plaisance Auxerre', 47.84, 3.62, curated) is False

def test_dedup_close_but_different_name():
    curated = [{'name': 'Port de Plaisance Auxerre', 'lat': 47.7980, 'lon': 3.5670}]
    # 50 m away, different name — probably a different mooring nearby, keep
    assert is_duplicate_of_curated('Quai du Maréchal Joffre', 47.7984, 3.5673, curated) is False

def test_dedup_diacritic_insensitive():
    curated = [{'name': 'Tübingen Hafen', 'lat': 48.520, 'lon': 9.057}]
    assert is_duplicate_of_curated('Tubingen Hafen', 48.5201, 9.0571, curated) is True

def test_dedup_empty_curated():
    assert is_duplicate_of_curated('Anything', 48.0, 2.0, []) is False


# ── area_clause (country attribution via OSM admin areas, not bbox) ──────────

def test_area_clause_uses_iso_code():
    assert 'area["ISO3166-1"="BE"][admin_level=2]' in area_clause('BE')

def test_area_clause_maps_uk_to_gb():
    # The app uses 'UK' but OSM's ISO3166-1 tag for the United Kingdom is 'GB'
    clause = area_clause('UK')
    assert '"GB"' in clause
    assert '"UK"' not in clause

def test_area_clause_ends_with_named_area():
    # Queries reference the area as (area.cc)
    assert area_clause('NL').rstrip().endswith('->.cc;')


# ── QL builders: every element selector must be country-area-scoped ──────────

def _selectors(ql):
    """Extract the node[...]/way[...] selector lines from a QL union block."""
    return [l.strip() for l in ql.splitlines()
            if l.strip().startswith(('node[', 'way['))]

def test_all_ql_builders_scope_every_selector_to_country_area():
    for cc in ALL_COUNTRIES:
        for build in (moorings_ql, lock_gates_ql, riverside_towns_ql):
            ql = build(cc)
            assert 'area["ISO3166-1"' in ql, f'{build.__name__}({cc}) missing area filter'
            sels = _selectors(ql)
            assert sels, f'{build.__name__}({cc}) has no selectors'
            for s in sels:
                assert '(area.cc)' in s, f'{build.__name__}({cc}) selector not area-scoped: {s}'

def test_ql_builders_keep_bbox_restriction():
    # bbox must be retained: it is what limits IT to the northern Po/Veneto area
    ql = moorings_ql('IT')
    assert '(44.0,6.5,46.6,13.6)' in ql


# ── prune_stale_osm ──────────────────────────────────────────────────────────

def test_prune_removes_osm_entries_not_seen_in_sweep():
    entries = [
        {'id': 'w_001', 'name': 'Montereau'},                                # curated, no source
        {'id': 'w_a60_gent', 'name': 'Gent', 'source': 'curated'},           # curated explicit
        {'id': 'w_osm_1', 'name': 'Kallosluis', 'source': 'osm', 'osm_id': 1},
        {'id': 'w_osm_2', 'name': 'French town, wrongly imported', 'source': 'osm', 'osm_id': 2},
    ]
    kept = prune_stale_osm(entries, seen_ids={'w_osm_1'})
    assert [e['id'] for e in kept] == ['w_001', 'w_a60_gent', 'w_osm_1']

def test_prune_keeps_everything_when_all_seen():
    entries = [{'id': 'w_osm_1', 'source': 'osm', 'osm_id': 1}]
    assert prune_stale_osm(entries, seen_ids={'w_osm_1'}) == entries
