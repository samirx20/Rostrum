"""Only in this shot + collections (PR1): what would break silently is a change meant for one shot showing in another,
an undo that leaves it behind, a save that drops it, or an agent's re-run wiping it."""
from rostrum_core import Document, Who

from rostrum3d import KIND, run_source
from rostrum3d.compile import describe

SAM = Who.person()
SRC = '''
material("chrome", baseColor="#cccccc", metallic=1)
ball = mesh("ball", shape="sphere", radius=0.2, material="chrome")
mesh("cup", shape="cylinder", radius=0.1, height=0.2, x=0.6, material="chrome")
mesh("box", shape="box", x=-0.6)
lamp = light("lamp", kind="rect", intensity=2, y=2)
lamp.key("intensity", {0: 2, 1: 4})
wide = camera("wide", z=4).aim(ball)
close = camera("close", z=1).aim(ball)
shot("wide_01", camera=wide, end=1)
shot("close_02", camera=close, end=1)
'''


def _doc(folder=None):
    d = Document.new(KIND, folder, "scene" if folder else None)
    d.run_script("scene.py", run_source(SRC, "scene.py", d))
    return d


def _node(scene, id_):
    stack = list(scene["items"])
    while stack:
        n = stack.pop()
        if n["id"] == id_:
            return n
        stack += n.get("children", [])


def test_an_override_shows_only_in_its_shot_and_holds_over_keys():
    d = _doc()
    d.apply({"op": "light.set_in_shot", "target": ["lamp"], "args": {"shot": "close_02", "intensity": 9, "x": 1.5}}, SAM)
    d.apply({"op": "mesh.set_in_shot", "target": ["box"], "args": {"shot": "close_02", "visible": False}}, SAM)
    close, wide = describe(d.data, "close_02"), describe(d.data, "wide_01")
    lamp = _node(close, "lamp")
    assert lamp["props"]["intensity"] == 9 and "intensity" not in lamp.get("anim", {}) and lamp["props"]["x"] == 1.5
    assert _node(close, "box")["props"]["visible"] is False
    assert _node(wide, "lamp")["anim"]["intensity"][0] == 2 and _node(wide, "box")["props"]["visible"] is True
    assert d.item("lamp")["x"] == 0 and d.item("box")["visible"] is True        # the document's own values untouched


def test_undo_redo_and_use_all_shots_value():
    d = _doc()
    d.apply({"op": "light.set_in_shot", "target": ["lamp"], "args": {"shot": "close_02", "intensity": 9}}, SAM)
    d.undo(SAM)
    assert "overrides" not in d.item("close_02")
    d.redo(SAM)
    assert d.item("close_02")["overrides"] == {"lamp": {"intensity": 9}}
    d.apply({"op": "shot.clear_override", "target": ["close_02"], "args": {"item": "lamp", "fields": ["intensity"]}}, SAM)
    assert "overrides" not in d.item("close_02")                             # reads as an old shot again
    d.undo(SAM)
    assert d.item("close_02")["overrides"]["lamp"]["intensity"] == 9


def test_save_load_keeps_overrides_and_collections(tmp_path):
    d = _doc(tmp_path)
    d.apply([{"op": "material.set_in_shot", "target": ["chrome"], "args": {"shot": "close_02", "roughness": 0.6}},
             {"op": "collection.add", "args": {"id": "props", "name": "Props", "items": ["box"], "material": "chrome"}}], SAM)
    d.save()
    e = Document.open(tmp_path, "scene", KIND)
    assert e.item("close_02")["overrides"] == {"chrome": {"roughness": 0.6}}
    assert e.item("props")["items"] == ["box"]
    mats = {m["id"]: m for m in describe(e.data, "close_02")["materials"]}
    assert abs(mats["chrome"]["props"]["roughness"] - 0.6) < 1e-9


def test_an_agents_rerun_never_wipes_a_persons_override():
    d = _doc()
    d.apply({"op": "light.set_in_shot", "target": ["lamp"], "args": {"shot": "close_02", "intensity": 9}}, SAM)
    report = d.run_script("scene.py", run_source(SRC.replace("intensity=2", "intensity=3"), "scene.py", d))
    assert d.item("close_02")["overrides"] == {"lamp": {"intensity": 9}} and not report.held
    assert d.item("lamp")["intensity"] == 3


def test_collection_targets_lights_materials_and_hide_in_one_shot():
    d = _doc()
    d.apply([{"op": "collection.add", "args": {"id": "props", "material": "chrome"}},
             {"op": "light.set", "target": ["lamp"], "args": {"lightsOnly": "props"}}], SAM)
    assert sorted(_node(describe(d.data, "wide_01"), "lamp")["props"]["lightsOnly"].split()) == ["ball", "cup"]
    d.apply({"op": "collection.show", "target": ["props"], "args": {"visible": False, "shot": "close_02"}}, SAM)
    assert _node(describe(d.data, "close_02"), "cup")["props"]["visible"] is False
    assert _node(describe(d.data, "wide_01"), "cup")["props"]["visible"] is True
    d.apply({"op": "collection.set", "target": ["props"], "args": {"include": ["box"]}}, SAM)
    d.apply({"op": "collection.material", "target": ["props"], "args": {"material": ""}}, SAM)
    assert d.item("box")["material"] == "" and d.item("ball")["material"] == ""
