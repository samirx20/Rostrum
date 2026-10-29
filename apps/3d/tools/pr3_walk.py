# PR3 walk (copies along a path, field shapes) by real input in the real 3D window (behind the person's work, never focused):
# a scene with a 3D "HELLO" and a small dot. By real clicks and keys only (bridge calls only read state; an item is chosen
# by a click on its scene-list row):
#   1. right-click the dot › Make copies › Line; Layout › Path in the settings rows; Path › the text; Count typed ... "1-*"
#   2. right-click a copy › Change near › Hide; the effector's Shape › Plane; the handle dragged down by the gizmo: the
#      copies under the wall go, those above it stay ............................................................ "2-*"
#   3. the effector's Changes › Scale, Shape › Noise, Radius and Amount typed: patches of bigger copies ............. "3-*"
# Pictures to the out folder (1646 x 900). Run:
#   heavy.ps1 run "hem: pr3 walk" gpu <venv python> apps\3d\tools\pr3_walk.py <out folder>
# Exit 0 = every check passed.
import os
import shutil
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("ROSTRUM_BACKGROUND_WINDOWS", "1")
OUT = Path(sys.argv[1] if len(sys.argv) > 1 else r"C:\Users\Sam\.rostrum\waves\results\3d-pr2-finish-pr3\pr3")
sys.argv = sys.argv[:1]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "app" / "tests"))
import clay_walk as W  # noqa: E402
import copies_walk as CW  # noqa: E402

from rostrum_core import Document  # noqa: E402
from rostrum3d import KIND  # noqa: E402
from rostrum3d.compile import describe  # noqa: E402
from rostrum3d.script import run_source  # noqa: E402
from rostrum_gui.app import qt_app  # noqa: E402
from screen3d import outline  # noqa: E402
from screen3d.steps import _gizmo_drag  # noqa: E402

import main as app3d  # noqa: E402

DOT = (-0.75, 0.03, 0.4)
SCENE = f'''
clay = material("clay", baseColor="#5d6470", roughness=0.6)
dotm = material("orange", baseColor="#ff8a3d", roughness=0.4)
floor = material("floor", baseColor="#2a2d32", roughness=0.8)
mesh("ground", shape="plane", width=6, depth=6, material=floor)
mesh("word", shape="text", text="HELLO", size=0.3, depth=0.03, y=0.3, material=clay)
mesh("dot", shape="sphere", radius=0.012, x={DOT[0]}, y_world={DOT[1]}, z={DOT[2]}, material=dotm)
light("key", kind="rect", width=1.2, height=0.8, intensity=6, x=1.0, y=1.6, z=1.6).aim((0, 0.3, 0))
light("sky", kind="dome", color="#9fb2cc", intensity=0.4)
cam = camera("cam", focalLength=45, x=0, y=0.5, z=2.3).aim((0, 0.3, 0))
shot("hero", camera=cam, fps=24, start=0, end=2)
'''


def snap(w, name):
    w.settle(name)
    W.pump(0.5)
    path = OUT / f"pr3-{name}.png"
    w.win.grabWindow().save(str(path))
    print("picture", path)


def choice_of(row):
    stack = [row]
    while stack:
        it = stack.pop()
        if "ChoiceField" in it.metaObject().className() and it.isVisible():
            return it
        stack += it.childItems()
    return None


def texts(item):
    out, stack = [], [item]
    while stack:
        it = stack.pop()
        t = it.property("text")
        if isinstance(t, str) and t:
            out.append(t)
        stack += it.childItems()
    return out


def pick(w, field, label):
    """Open the row's choice by a click and click the option reading `label`."""
    box = choice_of(w.item(f"row:{field}"))
    W.check(box is not None, f"{field}: a choice on screen")
    W.click(w.win, box)
    W.pump(0.6)
    lst = W.find(w.win.contentItem(), "choiceList")
    W.check(lst is not None, f"{field}: its list opened")
    stack = [lst]
    while stack:
        opt = stack.pop()
        if opt.property("option") is not None and opt.property("detail") is not None and label in texts(opt):
            W.click(w.win, opt)
            W.pump(0.8)
            return
        stack += opt.childItems()
    W.check(False, f"{field}: an option '{label}' in the list")


def select_row(w, item_id):
    """A real click on the item's scene-list row (SceneName.qml's `sceneRow:<id>`): the item is selected."""
    row = W.find(w.win.contentItem(), f"sceneRow:{item_id}")
    W.check(row is not None and row.isVisible(), f"the scene list shows {item_id}'s row")
    if row is not None:
        W.click(w.win, row)
        W.pump(0.5)
    W.check(w.b.selected == item_id, f"its row clicked: {item_id} is selected ({w.b.selected})")


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    project = Path(tempfile.mkdtemp(prefix="rostrum-pr3walk-"))
    app = qt_app()
    doc = Document.new(KIND, folder=project, item="scene")
    doc.run_script("scene.py", run_source(SCENE, "scene.py"))
    doc.save()
    screen = app3d.Screen(CW.SIZE)
    try:
        screen.show(doc, autosave=True)
        w = CW.Walk(screen, OUT)
        b, win, v = w.b, w.win, w.v
        W.pump(90, screen.ready, "the first picture")
        snap(w, "0-scene")

        # 1. copies of the dot, along the text
        w.right_click(w.where(DOT))
        W.check(b.selected == "dot", f"the right-click picked the dot ({b.selected})")
        w.choose("menu:Make copies", "copies:make:line")
        W.pump(5, lambda: CW.of_type(doc, "copies"), "the copies item")
        cid = b.selected
        W.check(doc.item(cid)["type"] == "copies", f"the copies item is selected ({cid})")
        snap(w, "1a-line")
        pick(w, "layout", "Path")
        W.check(doc.item(cid)["layout"] == "path", f"Layout is Path ({doc.item(cid)['layout']})")
        snap(w, "1b-layout-path-no-path-yet")
        pick(w, "path", outline.label_of(doc.item("word")))
        W.check(doc.item(cid)["path"] == "word", f"Path is the text ({doc.item(cid)['path']!r})")
        snap(w, "1c-on-the-text")
        w.type_into("count", 160)
        W.check(doc.item(cid)["count"] == 160, f"Count typed: 160 ({doc.item(cid)['count']})")
        w.settle("160 copies")
        W.check(v.copies.info.get(cid, {}).get("count") == 160, f"the engine laid out 160 ({v.copies.info.get(cid)})")
        snap(w, "1d-count-160")

        # 2. Change near › Hide, a plane, the handle swept down
        node = next(n for n in describe(doc.data, "hero")["items"] if n["id"] == cid)
        right = max((p for c in node["props"]["pathPoints"] for p in c), key=lambda p: p[0])   # the O's right edge
        at = [right[k] + doc.item(cid)["xyz"[k]] + (0.008 if k == 0 else 0.0) for k in range(3)]  # a copy's outer half
        w.right_click(w.where(at))
        W.check(b.selected == cid, f"the right-click on a copy picked the copies ({b.selected})")
        W.check("menu:Change near" in w.entries(), f"the menu has Change near ({w.entries()})")
        w.choose("menu:Change near", "copies:near:hide")
        W.pump(5, lambda: CW.of_type(doc, "effector"), "the effector")
        eff, handle = CW.of_type(doc, "effector")[0], b.selected
        W.check(doc.item(eff)["kind"] == "hide", f"the change hides ({doc.item(eff)['kind']})")
        snap(w, "2a-hide-sphere")
        select_row(w, eff)
        pick(w, "field", "Plane")
        W.check(doc.item(eff)["field"] == "plane", f"Shape is Plane ({doc.item(eff)['field']})")
        snap(w, "2b-plane-at-handle")
        select_row(w, handle)
        y0 = doc.item(handle)["y"]
        _gizmo_drag(b, win, "move1", 0, 120, False)
        W.pump(1.0)
        W.check(doc.item(handle)["y"] < y0, f"the handle went down ({y0:.3f} -> {doc.item(handle)['y']:.3f})")
        snap(w, "2c-plane-swept-down")
        _gizmo_drag(b, win, "move1", 0, 120, False)
        W.pump(1.0)
        snap(w, "2d-plane-swept-lower")

        # 3. noise with a scale
        select_row(w, eff)
        pick(w, "kind", "Scale")
        pick(w, "field", "Noise")
        w.type_into("radius", 0.12)
        w.type_into("amount", 1.5)
        e = doc.item(eff)
        W.check((e["kind"], e["field"]) == ("scale", "noise"), f"Scale in noise ({e['kind']}, {e['field']})")
        snap(w, "3a-noise-scale")
        W.check(not v.status.startswith("Error"), f"no viewport error ({v.status or '-'})")
    finally:
        screen.close()
        app.processEvents()
        shutil.rmtree(project, ignore_errors=True)
    if W.FAILS:
        print(f"\n{len(W.FAILS)} check(s) failed")
        sys.exit(1)
    print("\nevery check passed")


if __name__ == "__main__":
    main()
