"""The fill as a paint (fill_paint.py, ops_fill_paint.py). Silent breakage guarded: an old file's gradient effect, moved
into the fill on open, must reach the engine exactly as before (same look, keys and all), recorded as one change;
a re-run `layer.fill` must keep a stop's keys."""
from rostrum_core import Document, Who
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
    node = scene.describe(data)["comp"]["layers"][0]["effects"][0]
    return {k: v for k, v in node.items() if k != "id"}


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
