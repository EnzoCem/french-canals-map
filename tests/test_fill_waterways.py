import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from fill_waterways import stitch_ways, build_features, merge_geojson


def test_two_ways_join_forward():
    # Two ways sharing an endpoint → merge into one chain
    ways = [
        [[0.0, 0.0], [1.0, 0.0]],
        [[1.0, 0.0], [2.0, 0.0]],
    ]
    result = stitch_ways(ways)
    assert len(result) == 1
    assert result[0][0] == [0.0, 0.0]
    assert result[0][-1] == [2.0, 0.0]
    assert len(result[0]) == 3  # [0,0] [1,0] [2,0]


def test_reverse_to_connect():
    # Second way's END matches first way's end — must reverse to connect
    ways = [
        [[0.0, 0.0], [1.0, 0.0]],
        [[2.0, 0.0], [1.0, 0.0]],  # tail matches, needs reversal
    ]
    result = stitch_ways(ways)
    assert len(result) == 1
    assert result[0][0] == [0.0, 0.0]
    assert result[0][-1] == [2.0, 0.0]


def test_three_way_chain():
    ways = [
        [[0.0, 0.0], [1.0, 0.0]],
        [[1.0, 0.0], [2.0, 0.0]],
        [[2.0, 0.0], [3.0, 0.0]],
    ]
    result = stitch_ways(ways)
    assert len(result) == 1
    assert result[0][-1] == [3.0, 0.0]


def test_disconnected_ways_stay_separate():
    ways = [
        [[0.0, 0.0], [1.0, 0.0]],
        [[5.0, 5.0], [6.0, 5.0]],
    ]
    result = stitch_ways(ways)
    assert len(result) == 2


def test_empty_input():
    assert stitch_ways([]) == []


# ── build_features ────────────────────────────────────────────────────────────

def test_build_features_returns_geojson_features():
    chains = [[[0.0, 0.0], [1.0, 0.0], [2.0, 0.0]]]
    features = build_features('Canal du Midi', chains, route_num=49)
    assert len(features) == 1
    f = features[0]
    assert f['type'] == 'Feature'
    assert f['geometry']['type'] == 'LineString'
    assert f['properties']['name'] == 'Canal du Midi'
    assert f['properties']['route'] == 49
    assert f['properties']['section'] == 1


def test_build_features_skips_short_chains():
    # A chain with only 1 coordinate is not a valid LineString
    chains = [[[0.0, 0.0]], [[1.0, 0.0], [2.0, 0.0]]]
    features = build_features('Test', chains, route_num=1)
    assert len(features) == 1  # the single-point chain is skipped


def test_build_features_applies_rdp():
    # A perfectly straight line — middle point should be removed by RDP
    chains = [[[0.0, 0.0], [0.5, 0.0], [1.0, 0.0]]]
    features = build_features('Test', chains, route_num=1)
    coords = features[0]['geometry']['coordinates']
    assert len(coords) == 2  # middle point removed


# ── merge_geojson ─────────────────────────────────────────────────────────────

def _make_geojson(names):
    return {
        'type': 'FeatureCollection',
        'features': [
            {'type': 'Feature', 'geometry': {'type': 'LineString', 'coordinates': []},
             'properties': {'name': n}}
            for n in names
        ]
    }


def test_merge_removes_named_features():
    old = _make_geojson(['Canal du Midi', 'River Seine', 'Some Other Canal'])
    new_feats = [
        {'type': 'Feature', 'geometry': {'type': 'LineString', 'coordinates': [[0.0, 0.0], [1.0, 0.0]]},
         'properties': {'name': 'Canal du Midi', 'route': 49, 'section': 1}}
    ]
    result = merge_geojson(old, new_feats, {'Canal du Midi', 'River Seine'})
    names = [f['properties']['name'] for f in result['features']]
    assert 'Canal du Midi' in names       # new feature present
    assert 'River Seine' not in names     # old feature removed (no replacement)
    assert 'Some Other Canal' in names    # untouched feature preserved
    assert len(result['features']) == 2


def test_merge_preserves_structure():
    old = _make_geojson(['Canal du Midi'])
    result = merge_geojson(old, [], {'Canal du Midi'})
    assert result['type'] == 'FeatureCollection'
    assert result['features'] == []


# ── bridge_chain_gaps (gap-fix wave, 2026-07) ────────────────────────────────

from fill_waterways import bridge_chain_gaps


def test_bridge_small_mutual_gap():
    a = [[7.70, 48.45], [7.701, 48.451]]
    b = [[7.701, 48.4515], [7.702, 48.4525]]
    out = bridge_chain_gaps([a, b], max_gap_m=150)
    assert len(out) == 1
    assert out[0][0] == a[0] and out[0][-1] == b[-1]


def test_bridge_ignores_large_gap():
    a = [[7.70, 48.45], [7.701, 48.451]]
    b = [[7.701, 48.46], [7.702, 48.47]]  # ~1 km away
    out = bridge_chain_gaps([a, b], max_gap_m=150)
    assert len(out) == 2


def test_bridge_preserves_points_at_junctions():
    m = [[7.70, 48.45], [7.71, 48.46]]
    s1 = [[7.7101, 48.4601], [7.72, 48.47]]
    s2 = [[7.7102, 48.4601], [7.73, 48.48]]
    out = bridge_chain_gaps([m, s1, s2], max_gap_m=150)
    assert sum(len(c) for c in out) == 6
    assert 1 <= len(out) <= 2


def test_bridge_orientation_head_head():
    a = [[7.701, 48.451], [7.70, 48.45]]
    b = [[7.7011, 48.4511], [7.702, 48.4525]]
    out = bridge_chain_gaps([a, b], max_gap_m=150)
    assert len(out) == 1
    assert sum(len(c) for c in out) == 4


def test_bridge_empty_and_single():
    assert bridge_chain_gaps([]) == []
    one = [[[7.7, 48.4], [7.8, 48.5]]]
    assert bridge_chain_gaps(one) == one
