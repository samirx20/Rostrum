"""The fill's own settings are found and kept (hand maker rows 17, 21, 22): Find a setting's "angle", "gradient" and
"direction" show the Fill row (its fields are in the picker, so the panel's rows no longer held them and the search found
nothing); a picker change still open when the window closes is kept; Alt+click on a fold arrow folds a whole level."""
import sys
from pathlib import Path

import pytest
from PySide6.QtGui import QGuiApplication

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from rostrum_core import Document  # noqa: E402
from rostrum2d import KIND, run_source, textsize  # noqa: E402
from screen2d import frames, outline  # noqa: E402
from screen2d.bridge2d import Bridge2D  # noqa: E402
from test_screen import FakeEngine  # noqa: E402

SRC = 'comp("c", duration=2, fps=25)\nshape("s", w=100, h=40, fill="#888888")\n'


@pytest.fixture
def doc_bridge(monkeypatch):
    QGuiApplication.instance() or QGuiApplication([])
    monkeypatch.setattr(frames, "open_engine", FakeEngine)
    monkeypatch.setattr(textsize, "open_engine", FakeEngine)
    monkeypatch.setattr(textsize, "_own", None)
    d = Document.new(KIND)
    d.run_script("a.py", run_source(SRC, "a.py"))
    b = Bridge2D(d)
    b.select("s")
    yield d, b
    b.close()


def _found(b):
    return [r["id"] for r in b.model.shown_rows if r["row"] == "param" and r["valid"]]


def test_find_a_setting_reaches_the_gradient_direction(doc_bridge):
    _, b = doc_bridge
    for word in ("angle", "gradient", "direction"):
        b.setSearch(word)
        assert not b.nothingFound and _found(b) == ["paint"], word
    b.setSearch("blur")
    assert "paint" not in _found(b)


def test_a_picker_change_still_open_at_the_close_is_kept(tmp_path, monkeypatch):
    QGuiApplication.instance() or QGuiApplication([])
    monkeypatch.setattr(frames, "open_engine", FakeEngine)
    monkeypatch.setattr(textsize, "open_engine", FakeEngine)
    monkeypatch.setattr(textsize, "_own", None)
    d = Document.new(KIND, folder=str(tmp_path), item="proj")
    d.run_script("a.py", run_source(SRC, "a.py"))
    b = Bridge2D(d)
    b.select("s")
    b.beginScrub("paint")
    b.scrub("paint", {"type": "linear", "stops": [{"at": 0, "color": "#ff0000", "opacity": 1},
                                                  {"at": 1, "color": "#0000ff", "opacity": 1}], "angle": 180})
    b.close()                                         # the window closed with the picker open
    again = Document.open(tmp_path, "proj", KIND).item("s")         # what the file holds
    assert again["fillType"] == "linear" and again["gradAngle"] == 180


def test_alt_click_folds_every_row_at_its_level_and_keeps_the_rest():
    def lay(i, inside=()):
        return {"id": i, "type": "group" if inside else "shape", "layers": list(inside)}
    comp = {"layers": [lay("a", [lay("a1"), lay("a2")]), lay("b", [lay("b1")]), lay("c")]}
    flipped, done = outline.fold_level(comp, "a", {"x"}, want_open=False)
    assert flipped == {"x", "a", "b"} and done == {"a", "b"}      # "c" has nothing to fold; "x" (folded elsewhere) stays
    flipped, _ = outline.fold_level(comp, "b", flipped, want_open=True)
    assert flipped == {"x"}
