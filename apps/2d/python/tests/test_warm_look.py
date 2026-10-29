"""Looks draw through one held engine and a kept description (mcp/warm.py, layoutbake's kept layouts): after a
script re-run that changed one section, the description equals a fresh scene.describe (anything else draws a stale
picture without a word), only the changed section is solved again, and the next look shows the change."""
import sys

import pytest
from rostrum_core import Who
from rostrum_core import markers as M
from rostrum_core.mcp import Runtime

from rostrum2d import layoutbake, settings
from rostrum2d.mcp import app_tools, make_app, warm
from rostrum2d.scene import describe

AGENT = Who.agent("tester")
needs_engine = pytest.mark.skipif(settings.engine_missing_reason() is not None or sys.platform != "win32",
                                  reason=settings.engine_missing_reason() or "the engine's pixels are Windows only")
SRC = '''
comp("main", width=320, height=180, fps=10, duration=4, background="#000000")
with group("one", start=0, end=2, layout="column", gap=8):
    for i in range(3):
        shape(f"a{i}", shape="rect", w=60, h=20, fill="#ffffff")
with group("two", start=2, end=4, layout="row", gap=8):
    for i in range(3):
        shape(f"b{i}", shape="rect", w=30, h=30, fill="COLOUR")
'''


def _run(rt, colour):
    reply, _ = rt.call("run_script", {"source": SRC.replace("COLOUR", colour), "name": "s.py"}, AGENT)
    assert reply["ok"], reply["summary"]


def test_a_re_run_describes_like_a_fresh_scene_and_solves_only_the_changed_section(tmp_path, monkeypatch):
    app = make_app(str(tmp_path), ["demo"])
    rt, doc = Runtime(app, app_tools()), next(iter(app.documents.values()))
    _run(rt, "#ff0000")
    warm.scene(doc, "main", 4)
    solved = []
    real = layoutbake._solve
    monkeypatch.setattr(layoutbake, "_solve", lambda comp, *a: solved.append(comp["layers"][0]["id"]) or real(comp, *a))
    _run(rt, "#00ff00")
    got = warm.scene(doc, "main", 4)
    assert solved == ["two"]
    layoutbake._KEPT.clear()
    assert got == describe(doc.data, "main", M.times(doc.folder), doc.folder, (0.0, 4))


@needs_engine
def test_the_look_after_an_edit_shows_the_edit(tmp_path):
    from PIL import Image
    app = make_app(str(tmp_path), ["demo"])
    rt = Runtime(app, app_tools())
    colours = []
    for colour in ("#ff0000", "#00ff00"):
        _run(rt, colour)
        reply, _ = rt.call("look_frame", {"time": 3, "width": 320}, AGENT)
        assert reply["ok"], reply["summary"]
        with Image.open(reply["files"][0]) as im:
            colours.append(im.convert("RGB").getpixel((160, 90)))
    assert colours[0][0] > 200 > colours[0][1] and colours[1][1] > 200 > colours[1][0]
