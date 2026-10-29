"""A wrong name, call or argument in a 2D script names the closest real ones at its line, and nothing is applied."""
import pytest
from rostrum_core import RostrumError

from rostrum2d.script import run_source


def _error(source):
    with pytest.raises(RostrumError) as e:
        run_source('comp("c")\n' + source, "s1")
    return e.value.line()


def test_wrong_names_say_the_close_ones():
    assert 'line 3: TypeError: "att" isn\'t an argument of pivot(); did you mean at?' in _error('s = shape("a")\ns.pivot(1, 2, att=0)')
    assert '"layr" isn\'t a name the script knows; did you mean layer?' in _error('shape("a")\nlayr("a")')
    assert "did you mean label?" in _error('label = shape("a")\nlabl.x = 3')
    assert 'no field "kye". Did you mean key?' in _error('s = shape("a")\ns.kye("x", {0: 1})')
    assert "Accepted" not in _error('s = shape("a")\ns.pivot(1, 2, att=0)')       # names only, not the whole script list
