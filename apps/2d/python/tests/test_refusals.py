"""A state the engine can't draw is refused when it is set (rostrum2d/refusals.py), so a saved file never fails to draw
later: a morph between shapes with different piece counts, and per-letter animation of a text wrapped in a box."""
import pytest
from rostrum_core import Document, Who
from rostrum_core.errors import RostrumError

from rostrum2d import KIND

ME = Who.person("sam")
ONE, TWO = "M 0 0 L 10 0 L 10 10 Z", "M 0 0 L 10 0 L 10 10 Z M 20 0 L 30 0 L 30 10 Z"


def _doc(tmp_path):
    d = Document(KIND, None, tmp_path, "film")
    d.apply([{"op": "comp.add", "args": {"id": "s"}},
             {"op": "layer.add", "target": "s", "args": {"type": "path", "id": "p"}},
             {"op": "path.set", "target": "p", "args": {"d": ONE}},
             {"op": "layer.add", "target": "s", "args": {"type": "text", "id": "t"}},
             {"op": "text.set", "target": "t", "args": {"body": "Hi"}}], ME)
    return d


def test_a_morph_between_different_piece_counts_is_refused_when_the_key_is_set(tmp_path):
    d = _doc(tmp_path)
    d.apply([{"op": "key.add", "target": "p", "args": {"prop": "d", "t": 0.0, "d": ONE}}], ME)
    with pytest.raises(RostrumError, match="same number of pieces"):
        d.apply([{"op": "key.add", "target": "p", "args": {"prop": "d", "t": 1.0, "d": TWO}}], ME)
    assert len(d.item("p")["keys"]) == 1                      # nothing half-applied


def test_letters_with_a_box_width_are_refused_when_set(tmp_path):
    d = _doc(tmp_path)
    d.apply([{"op": "text.set", "target": "t", "args": {"boxWidth": 300}}], ME)          # a wrapped text alone is fine
    with pytest.raises(RostrumError, match="letter by letter"):
        d.apply([{"op": "text.set", "target": "t", "args": {"letterDelay": 0.05}}], ME)
