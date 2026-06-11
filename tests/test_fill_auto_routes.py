"""Unit tests for fill_auto_routes.py pure functions."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fill_auto_routes import (
    haversine_km, polyline_length_km, group_features_by_name, count_locks_near_segments,
)


def test_haversine_km_paris_to_london():
    # Paris (48.8566, 2.3522) → London (51.5074, -0.1278) ≈ 344 km
    d = haversine_km(48.8566, 2.3522, 51.5074, -0.1278)
    assert 340 < d < 346, f'expected ~344 km, got {d:.1f}'


def test_polyline_length_km_simple():
    # 3-point line: 0,0 → 0.001,0 → 0.002,0 = 2 × 111 m ≈ 0.222 km
    line = [(0, 0), (0.001, 0), (0.002, 0)]
    L = polyline_length_km(line)
    assert 0.21 < L < 0.23, f'expected ~0.22 km, got {L:.3f}'


def test_group_features_by_name():
    features = [
        {'properties': {'name': 'Seine'}, 'geometry': {'type': 'LineString', 'coordinates': [[0,0],[0.001,0]]}},
        {'properties': {'name': 'Seine'}, 'geometry': {'type': 'LineString', 'coordinates': [[0.001,0],[0.002,0]]}},
        {'properties': {'name': 'Loire'}, 'geometry': {'type': 'LineString', 'coordinates': [[0,1],[0.001,1]]}},
    ]
    groups = group_features_by_name(features)
    assert set(groups.keys()) == {'Seine', 'Loire'}
    assert len(groups['Seine']) == 2
    assert len(groups['Loire']) == 1


def test_count_locks_near_segments():
    # Two waypoints: one ~11 m from the line, one ~5.5 km away
    line = [(2.0, 48.0), (2.001, 48.0)]   # short horizontal segment near Paris
    waypoints = [
        {'is_lock': True,  'lat': 48.0001, 'lon': 2.0005},   # ~11 m perpendicular
        {'is_lock': True,  'lat': 48.05,   'lon': 2.0},       # ~5.5 km away
        {'is_lock': False, 'lat': 48.0,    'lon': 2.0005},    # near, but not a lock
    ]
    n = count_locks_near_segments([line], waypoints, radius_m=200)
    assert n == 1, f'expected 1 lock within 200m, got {n}'
