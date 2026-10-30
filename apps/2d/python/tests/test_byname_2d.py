"""Google Fonts and icons by name in the classic 2D document: a text naming a Google Fonts family is drawn in it (the
scene hands the engine the fetched file), offline and not fetched it is the placeholder saying so, and icon() makes a
group of path layers. The fetch itself is rostrum_core's (shared/core/tests/test_byname.py); here it is a stand-in."""
import pytest
from rostrum_core import Document
from rostrum_core.byname import FontNeedsInternet

from rostrum2d import KIND, missing_font, run_source, settings
from rostrum2d.scene import describe

SRC = 'comp("c", width=320, height=180, fps=10, duration=1)\ntext("t", body="Hi", font="Lobster", italic={italic})\n'


def _scene(italic=False):
    d = Document.new(KIND)
    d.run_script("s.py", run_source(SRC.format(italic=italic), "s.py"))        # set through the script: not refused
    return describe(d.data, span=(0.0, 1.0))


@pytest.fixture
def lobster(monkeypatch):
    file = str(settings.APP / "engine" / "fonts" / "Caveat.ttf")              # any real font file stands in
    monkeypatch.setattr(missing_font, "engine_font", lambda family: file)
    monkeypatch.setattr(missing_font, "faces", lambda family: [{"file": "Lobster-Regular.ttf", "italic": False}])
    return file


def test_a_google_family_reaches_the_engine_as_the_scenes_own_font(lobster):
    scene = _scene()
    assert scene["fonts"] == {"Lobster": lobster}
    assert scene["comp"]["layers"][-1]["type"] == "text" and "warnings" not in scene


def test_offline_and_not_fetched_is_the_placeholder_saying_so(monkeypatch):
    def offline(family):
        raise FontNeedsInternet("needs the internet")
    monkeypatch.setattr(missing_font, "engine_font", offline)
    scene = _scene()
    box = next(n for n in scene["comp"]["layers"] if n["id"] == "t")
    assert box["type"] == "group" and box["layers"][1]["props"]["body"] == "Lobster (needs the internet once)"


def test_an_italic_the_family_lacks_is_the_placeholder(lobster):
    box = next(n for n in _scene(italic=True)["comp"]["layers"] if n["id"] == "t")
    assert box["type"] == "group" and box["layers"][1]["props"]["body"] == "Lobster (no italic)"


def test_icon_makes_a_group_of_path_layers():
    tree = run_source('comp("c", width=320, height=180)\nicon("tabler:heart-filled", id="like", size=96, color="#e5484d", x=100)\n', "s.py")
    like = next(n for n in tree["comps"][0]["layers"] if n["id"] == "like")
    assert like["type"] == "group" and (like["w"], like["h"], like["x"]) == (96, 96, 100)
    inner = like["layers"][0]
    assert inner["scale"] == 4 and [p["type"] for p in inner["layers"]] == ["path"]
    assert inner["layers"][0]["fill"] == "#e5484d" and inner["layers"][0]["stroke"] is False
    with pytest.raises(Exception, match="nearest: arrow-right"):
        run_source('comp("c")\nicon("arow-rigth")\n', "s.py")
