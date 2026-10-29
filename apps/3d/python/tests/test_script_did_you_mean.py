"""A wrong name, call or argument in a 3D script names the closest real ones at its line, and nothing is applied."""
import pytest
from rostrum_core import RostrumError

from rostrum3d.script import run_source


def _error(source):
    with pytest.raises(RostrumError) as e:
        run_source(source, "s1")
    return e.value.line()


def test_wrong_names_say_the_close_ones():
    assert '(line 2): AttributeError: "kye" isn\'t a field or call of a mesh; did you mean key?' in _error('m = mesh("a")\nm.kye("x", {0: 1})')
    assert '"mes" isn\'t a name the script knows; did you mean mesh?' in _error('mes("a")')
    assert '"rol" isn\'t an argument of aim(); did you mean roll?' in _error('m = mesh("a")\nm.aim("b", rol=3)')
    assert "Did you mean ease?" in _error('m = mesh("a")\nm.key("x", {0: 1}, eas="in")')
    shap = _error('mesh("a", shap="cube")')
    assert "(line 1)" in shap and shap.endswith("Did you mean shape?") and "Accepted: shape" in shap
    assert "Accepted" not in _error('mes("a")')                                     # names only, not the whole script list
