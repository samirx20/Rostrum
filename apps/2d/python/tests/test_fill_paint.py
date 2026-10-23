"""The fill as a paint (fill_paint.py, ops_fill_paint.py). Silent breakage guarded: an old file's gradient effect, moved
into the fill on open, must reach the engine drawing the same gradient (same look, keys and all), recorded as one change;
a re-run `layer.fill` must keep a stop's keys."""
import pytest
from rostrum_core import Document, RostrumError, Who
from rostrum_core.storage import save

from rostrum2d import KIND, scene

SAM = Who.person("sam")


def _old_file(tmp_path):
    d = Document(KIND, None, tmp_path, "film")
    d.apply([{"op": "comp.add", "args": {"id": "s"}},
             {"op": "layer.add", "target": "s", "args": {"type": "text", "id": "t"}},
             {"op": "effect.add", "target": "t", "args": {"type": "gradient", "id": "g"}},
             {"op": "gradient.set", "target": "g", "args": {"style": "conic", "angle": 30, "cx": 0.3, "color1": "#ff0000",
                                                            "middle": True, "color3": "#00ff00", "mid": 0.4}},
             {"op": "key.add", "target": "g", "args": {"prop": "color2", "t": 1.0, "c": "#0000ff"}},
             {"op": "key.add", "target": "g", "args": {"prop": "angle", "t": 2.0, "v": 90}}], SAM)
    return d


def _gradient_node(data):
    """The gradient the engine draws, as (geometry, geometry keys, stops with their keys): an old effect's color1 /
    color3 at mid / color2 and a fill's `stops` children (E8) read the same."""
    node = scene.describe(data)["comp"]["layers"][0]["effects"][0]
    props, anim = node["props"], node.get("anim", {})
    geometry = {k: props[k] for k in ("style", "angle", "cx", "cy")}
    if node.get("stops"):
        stops = [(s["props"]["at"], s["props"]["color"], s["props"]["opacity"], s.get("anim", {})) for s in node["stops"]]
    else:
        ends = [(0.0, "color1", None), *([(props["mid"], "color3", "mid")] if props["middle"] else []), (1.0, "color2", None)]
        stops = [(at, props[c], 1.0, {**({"color": anim[c]} if c in anim else {}), **({"at": anim[a]} if a in anim else {})})
                 for at, c, a in ends]
    return geometry, {k: v for k, v in anim.items() if k in geometry}, stops


def test_old_gradient_effect_opens_as_the_fill_looking_the_same(tmp_path):
    old = _old_file(tmp_path)
    before = _gradient_node(old.data)
    save(old)
    d = Document.open(tmp_path, "film", KIND)
    t = d.item("t")
    assert t["fillType"] == "angular" and len(t["stops"]) == 3 and not t["effects"]
    assert _gradient_node(d.data) == before
    assert d.history.changes[-1].label == "Gradient effect moved into the fill"


def test_rerun_fill_keeps_stop_keys(tmp_path):
    d = Document.new(KIND)
    run = [{"op": "comp.add", "args": {"id": "s"}},
           {"op": "layer.add", "target": "s", "args": {"type": "shape", "id": "a"}},
           {"op": "layer.fill", "target": "a", "args": {"type": "linear", "stops": ["#ff0000 0", "#0000ff 100"]}}]
    d.apply(run, SAM)
    stop = d.item("a")["stops"][1]["id"]
    d.apply([{"op": "key.add", "target": stop, "args": {"prop": "color", "t": 1.0, "c": "#00ff00"}}], SAM)
    d.apply([run[2]], SAM)
    assert d.item(stop)["keys"]


def test_picker_edit_on_animated_stop_keys_it_at_the_playhead():
    """The Fill row's picker on an animated gradient: the change lands as a key at `at`, the other stops get no key."""
    d = Document.new(KIND)
    d.apply([{"op": "comp.add", "args": {"id": "s"}},
             {"op": "layer.add", "target": "s", "args": {"type": "shape", "id": "a"}},
             {"op": "layer.fill", "target": "a", "args": {"type": "linear", "stops": ["#ff0000 0", "#0000ff 100"]}}], SAM)
    first, last = (s["id"] for s in d.item("a")["stops"])
    d.apply([{"op": "key.add", "target": first, "args": {"prop": "color", "t": 0.0, "c": "#ff0000"}}], SAM)
    d.apply([{"op": "layer.fill", "target": "a", "args": {"type": "linear", "at": 1.0, "stops": ["#00ff00 0", "#0000ff 100"]}}], SAM)
    assert [(k["t"], k["c"]) for k in d.item(first)["keys"]] == [(0.0, "#ff0000"), (1.0, "#00ff00")]
    assert d.item(first)["color"] == "#ff0000" and not d.item(last)["keys"]


def test_any_stops_and_a_left_picture_reach_the_engine_as_set():
    """E8: five stops (one #rrggbbaa: its alpha becomes the stop's opacity) go as the gradient's stops; a picture chosen
    and then left for a gradient is kept in the document but not drawn."""
    d = Document.new(KIND)
    d.apply([{"op": "comp.add", "args": {"id": "s"}},
             {"op": "layer.add", "target": "s", "args": {"type": "shape", "id": "a"}},
             {"op": "shape.set", "target": "a", "args": {"shape": "star"}},
             {"op": "layer.fill", "target": "a", "args": {"type": "picture", "picture": "C:/pic.png", "fit": "tile"}},
             {"op": "layer.fill", "target": "a", "args": {"type": "linear", "stops": [
                 "#ff0000 0", "#ffff00 20", "#00ff0080 45", "#00ffff 70", "#0000ff 100"]}}], SAM)
    node = scene.describe(d.data)["comp"]["layers"][0]
    stops = node["effects"][0]["stops"]
    assert [s["props"]["at"] for s in stops] == [0.0, 0.2, 0.45, 0.7, 1.0]
    assert stops[2]["props"]["color"] == "#00ff00" and abs(stops[2]["props"]["opacity"] - 128 / 255) < 1e-3
    assert node["props"]["fillPicture"] == "" and d.item("a")["fillPicture"] == "C:/pic.png"


def test_a_gradient_with_fewer_than_two_stops_is_refused(tmp_path):
    """Setting the fill type to a gradient through the plain field must not leave a fill the export can only fail on;
    layer.fill (the picker's path) adds its two stops and passes."""
    import pytest
    from rostrum_core.errors import RostrumError
    d = Document(KIND, None, tmp_path, "film")
    d.apply([{"op": "comp.add", "args": {"id": "s"}}, {"op": "layer.add", "target": "s", "args": {"type": "shape", "id": "card"}}], SAM)
    with pytest.raises(RostrumError, match="at least 2 colour stops"):
        d.apply([{"op": "shape.set", "target": "card", "args": {"fillType": "linear"}}], SAM)
    d.apply([{"op": "layer.fill", "target": "card", "args": {"type": "linear"}}], SAM)
    assert len(d.item("card")["stops"]) == 2


def test_solid_fill_opacity_reaches_the_engine_and_a_re_run_keeps_its_keys():
    d = Document.new(KIND)
    d.apply([{"op": "comp.add", "args": {"id": "s"}}, {"op": "layer.add", "target": "s", "args": {"type": "shape", "id": "r"}}], SAM)
    sent = lambda: scene.describe(d.data)["comp"]["layers"][0]["props"]["fillOpacity"]   # noqa: E731
    assert sent() == 1.0                                          # an old file / a fresh layer: fully opaque
    d.apply({"op": "layer.fill", "target": "r", "args": {"type": "solid", "color": "#ff0000", "opacity": 0.4}}, SAM)
    assert sent() == 0.4
    d.apply({"op": "key.add", "target": "r", "args": {"prop": "fillOpacity", "t": 1.0, "v": 0.9}}, SAM)
    d.apply({"op": "layer.fill", "target": "r", "args": {"type": "solid", "opacity": 0.4}}, SAM)   # same value again: keys stay
    assert d.item("r")["keys"]
    with pytest.raises(RostrumError, match="solid fill"):
        d.apply({"op": "layer.fill", "target": "r", "args": {"type": "linear", "opacity": 0.5}}, SAM)
