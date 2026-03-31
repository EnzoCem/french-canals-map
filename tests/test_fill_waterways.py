import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from fill_waterways import stitch_ways


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
