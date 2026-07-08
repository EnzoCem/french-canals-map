"""Unit tests for fill_michelin.py pure functions."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_atomic_write_text(tmp_path):
    from fill_michelin import atomic_write_text
    target = tmp_path / 'page.html'
    atomic_write_text(target, '<html>é</html>')
    assert target.read_text(encoding='utf-8') == '<html>é</html>'
    assert list(tmp_path.iterdir()) == [target]
