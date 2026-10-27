"""The stylized blocks (brief 22): what would break silently. The compiled scene carries a material's Lines, Light to
colour and Halftone to the core (colours linear, as baseColor), and the live `material` request's values are the same;
Stylized is offered only while a material has Lines or Halftone on; each block is a group its switch turns on (one
click on its name in the row of names); a Stylized render asks for the stylized renderer with its supersampling."""
import types

import pytest
from rostrum_core import Document, Who
from rostrum_gui import sections

from rostrum3d import KIND, compile as C, fields as F
from rostrum3d.colors import linear
from rostrum3d.material_fields import any_stylized
from rostrum3d.material_scene import prop_out
from rostrum3d.render_fields import engine_fields, settings

SAM = Who.person()
INFO = {"width": 1920, "height": 1080, "start": 0, "end": 23, "fps": 24}


def _doc(**mat):
    d = Document.new(KIND)
    d.apply([{"op": "material.add", "args": {"id": "ink", **mat}},
             {"op": "mesh.add", "args": {"id": "case", "shape": "box", "material": "ink"}},
             {"op": "camera.add", "args": {"id": "cam", "z": 2}},
             {"op": "shot.add", "args": {"id": "hero", "camera": "cam", "start": 0, "end": 1}}], SAM)
    return d


def test_the_scene_carries_the_blocks_to_the_core():
    d = _doc(lines=True, linesWidth=3.5, linesColor="#ff8000", lightToColor=True, shadowColor="#336699",
             lightEdges="smooth", halftone=True, halftoneShape="lines")
    props = next(m for m in C.describe(d.data, "hero")["materials"] if m["id"] == "ink")["props"]
    assert props["lines"] is True and props["linesWidth"] == pytest.approx(3.5)
    assert props["linesColor"] == pytest.approx(linear("#ff8000"))
    assert props["shadowColor"] == pytest.approx(linear("#336699"))
    assert props["lightEdges"] == "smooth" and props["halftone"] is True and props["halftoneShape"] == "lines"
    assert props["litColor"] == pytest.approx(linear("#ffffff")) and props["linesCreaseAngle"] == pytest.approx(40)
    assert prop_out("linesColor", "#ff8000") == props["linesColor"]          # the live drag sends the scene's values


def test_stylized_is_offered_only_with_lines_or_halftone():
    assert not any_stylized(_doc(lightToColor=True).data)          # Light to colour alone shows in Final too
    assert any_stylized(_doc(lines=True).data) and any_stylized(_doc(halftone=True).data)
    assert not any_stylized(_doc().data)


@pytest.mark.parametrize("group,switch", [("Lines", "lines"), ("Light to colour", "lightToColor"), ("Halftone", "halftone")])
def test_each_block_is_turned_on_by_its_name(group, switch):
    rows = sections.layout(types.SimpleNamespace(params=F.FIELDS["material"]), "material")
    fold = next(r for r in rows if r.get("fold") == group)
    assert fold["switch"] == switch and fold["on"] is True


def test_a_stylized_render_asks_for_the_stylized_renderer():
    s = settings({"renderQuality": "stylized", "renderFormat": "both", "passMasks": True}, INFO)
    assert s["renderer"] == "stylized" and s["passes"] == []
    assert engine_fields(s) == {"stylized": {"supersample": 2}}
    assert engine_fields(settings({"renderQuality": "good"}, INFO)) == {"samples": 128, "denoise": True}


def test_render_tools_follow_the_shots_quality_unless_told():
    from rostrum3d.mcp.render import _renderer
    stylized, good = settings({"renderQuality": "stylized"}, INFO), settings({"renderQuality": "good"}, INFO)
    assert _renderer({}, stylized) == "stylized" and _renderer({}, good) == "cycles"
    assert _renderer({"quality": "final"}, stylized) == "cycles" and _renderer({"quality": "fast"}, stylized) == "storm"
    assert _renderer({"renderer": "stylized"}, good) == "stylized"
