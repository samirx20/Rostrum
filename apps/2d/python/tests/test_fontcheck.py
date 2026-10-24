"""A font setting the font can't do is refused when the document would take it, naming the layer by its id."""
import pytest

from rostrum_core import Document, RostrumError
from rostrum2d import KIND, run_source

SRC = 'comp("film", duration=3)\ntext("fc_time", body="0:12", font="Roboto Flex", figures="tabular lining")\n'


def test_run_script_refuses_a_feature_the_font_lacks_naming_the_layer():
    doc = Document(KIND)
    with pytest.raises(RostrumError) as e:
        doc.run_script("s.py", run_source(SRC, "s.py"))
    assert "fc_time.figures" in str(e.value) and "tnum" in str(e.value)
    assert not doc.data["comps"]                         # nothing was merged


def test_a_font_that_is_nowhere_is_refused_never_drawn_in_another():
    doc = Document(KIND)
    with pytest.raises(RostrumError) as e:
        doc.run_script("s.py", run_source('comp("film", duration=3)\ntext("t", body="Hi", font="No Such Sans")\n', "s.py"))
    assert 'font "No Such Sans" is not in the app or on this computer' in str(e.value) and "inspect_fonts" in str(e.value)
    assert not doc.data["comps"]
