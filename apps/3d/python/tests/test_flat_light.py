"""mcp/light_faults.py: flat_light fires on a subject whose lit and dark sides are close in the picture and not on one lit
from the side (3E round 8 canary, "soft key from the left": a flat dim cube passed as DONE); and a script light with no
strength given is lit as the start key (brightness=0), not left at intensity 1, ~4 stops under the sky's fill."""
from PIL import Image

from rostrum_core import Document

from rostrum3d import KIND, run_source
from rostrum3d.compile import shot_info
from rostrum3d.mcp import light_faults
from rostrum3d.motion_track import Track
from rostrum3d.start_scene import SOURCE

SRC = "cube = mesh('cube', shape='box', width=0.2, height=0.2, depth=0.2)\nshot('shot_1', frame=cube, fill=0.5)\n"


def _scene(src=SRC):
    doc = Document.new(KIND)
    doc.run_script("start.py", run_source(SOURCE, "start.py"))
    doc.run_script("s.py", run_source(src, "s.py", doc))
    return doc, shot_info(doc.data, "shot_1")


def _picture(path, info, data, sides):
    """A picture with the cube's projected box filled: `sides` = (left grey, right grey)."""
    tr = Track(data, info, range(0, 1))
    _, (x0, y0, x1, y1) = light_faults._subject(tr, 0)
    w, h = tr.cams[0].w, tr.cams[0].h
    im = Image.new("RGB", (w, h), (90, 90, 90))
    mid = int((x0 + x1) / 2)
    im.paste((sides[0],) * 3, (int(x0), int(y0), mid, int(y1)))
    im.paste((sides[1],) * 3, (mid, int(y0), int(x1), int(y1)))
    im.save(path)
    return path


def test_a_flat_subject_is_a_fault_and_a_side_lit_one_is_not(tmp_path):
    doc, info = _scene()
    flat = light_faults.flat(doc.data, info, 0, _picture(tmp_path / "flat.png", info, doc.data, (150, 140)))
    assert [f["id"] for f in flat] == ["flat_light:cube"] and "stops" in flat[0]["what"] and "fix" not in flat[0], flat
    assert light_faults.flat(doc.data, info, 0, _picture(tmp_path / "lit.png", info, doc.data, (200, 70))) == []


def test_a_light_with_no_strength_is_lit_as_the_start_key():
    doc, _ = _scene(SRC + "light('soft_key', kind='rect', x=-0.8, y=0.4, z=0.2, replace_start_lights=True).aim(cube)\n"
                          "light('dim', kind='rect', intensity=1, x=0.8, y=0.4).aim(cube)\n")
    lights = {it["id"]: it for it in doc.data["items"] if it["type"] == "light"}
    assert lights["soft_key"]["normalize"] is True and lights["soft_key"]["intensity"] > 1, lights["soft_key"]
    assert lights["dim"]["intensity"] == 1 and not lights["dim"]["normalize"]          # a strength given is kept
    assert "sky" in lights and "key_light" not in lights                              # the fill stays
