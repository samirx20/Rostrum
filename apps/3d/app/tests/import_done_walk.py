# Brief 29's done-line, tried in the real window (behind the person's work, never focused), by real input where a
# person's hand would be (bridge calls only read state to check it):
#   1. Import › FBX… (real clicks on the rail button and the entry) with a crate modelled in centimetres: it lands on
#      the plinth under the view's centre at 1/100, the status line says "Imported at 1/100: it was in centimetres" and
#      Keep original size shows. Then Ctrl+Z.
#   2. A .glb (a 22 cm bottle) dragged from Explorer and dropped on the plinth's top: it stands there at its own size
#      (scale 1), its base on the top, its two meshes listed as parts.
#   3. An Alembic file (a rippling sheet and a bobbing ball, 120 frames at 60 fps) dropped beside the plinth, then
#      Space plays the shot: frames advanced and engine milliseconds per frame are measured while it plays.
#   4. Import › Asset library: the sheet with every source off (nothing listed), then a real click on Poly Haven's
#      switch: its models are listed (this step uses the network).
# The files are the brief's test files (made with Blender 5.2 / by hand, CC0): pass --files <folder>.
# Not collected by pytest. Run:  heavy.ps1 run "hem: import done walk" gpu <venv python> apps\3d\app\tests\import_done_walk.py --files <dir> --out <dir>
import argparse
import json
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path

os.environ.setdefault("ROSTRUM_BACKGROUND_WINDOWS", "1")
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
import clay_walk as W  # noqa: E402  (puts this checkout's code first; its real-input helpers)
import import_walk as IW  # noqa: E402  (the drag from Explorer, the dialog's answer)

from PySide6.QtCore import QObject, Qt  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from rostrum_core import Document  # noqa: E402
from rostrum3d import KIND  # noqa: E402
from rostrum3d.script import run_source  # noqa: E402
from rostrum_gui.app import qt_app  # noqa: E402

import main as app3d  # noqa: E402

SCENE = '''
floor = material("floor", baseColor="#3a3d42", roughness=0.8)
stone = material("stone", baseColor="#bdb6aa", roughness=0.7)
mesh("ground", shape="plane", width=6, depth=6, material=floor)
mesh("plinth", shape="cylinder", radius=0.22, height=0.6, bevel=0.01, y=0.3, material=stone)
light("key", kind="rect", width=1.2, height=0.8, intensity=6, x=1.4, y=1.8, z=1.2).aim((0, 0.6, 0))
light("sky", kind="dome", color="#9fb2cc", intensity=0.3)
cam = camera("cam", focalLength=40, y=1.25, z=1.9).aim((0, 0.62, 0))
shot("hero", camera=cam, fps=60, start=0, end=2)
'''
TOP = 0.6                    # the plinth's top (y, metres)


def play(w, win, b, seconds=4.0):
    """Space, `seconds` of playback, Space: pictures the window got, distinct frames among them, engine ms per picture."""
    serials, mss, v = [], [], w.v
    on = lambda: (serials.append((time.perf_counter(), b.frame)), mss.append(v.ms))  # noqa: E731
    v.serialChanged.connect(on)
    QTest.keyClick(win, Qt.Key_Space)
    t0 = time.perf_counter()
    W.pump(seconds)
    QTest.keyClick(win, Qt.Key_Space)
    dt = time.perf_counter() - t0
    v.serialChanged.disconnect(on)
    shown = [s for s in serials if s[0] - t0 <= dt]
    ms = sorted(mss)
    W.pump(0.5)
    return {"seconds": round(dt, 2), "pictures": len(shown), "distinct_frames": len({f for _, f in shown}),
            "pictures_per_s": round(len(shown) / dt, 1),
            "engine_ms_median": round(ms[len(ms) // 2], 1) if ms else None,
            "engine_ms_p95": round(ms[int(len(ms) * 0.95)], 1) if ms else None}


def main():
    a = argparse.ArgumentParser()
    a.add_argument("--files", required=True)
    a.add_argument("--out", required=True)
    args = a.parse_args()
    files, out = Path(args.files), Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    report = {}
    project = Path(tempfile.mkdtemp(prefix="rostrum-importdone-"))
    app = qt_app()
    doc = Document.new(KIND, folder=project, item="scene")
    doc.run_script("scene.py", run_source(SCENE, "scene.py"))
    doc.save()
    screen = app3d.Screen(IW.SIZE)
    try:
        screen.show(doc, autosave=True)
        w = IW.Walk(screen, out)
        b, win = w.b, w.win
        W.pump(60, screen.ready, "the first picture")

        # 1. Import › FBX… with a crate in centimetres
        win.findChild(QObject, "importFiles").setProperty("useNative", False)
        W.click(win, w.item("rail_import"))
        W.pump(0.3)
        W.click(win, w.item("fly_import:FBX"))
        W.pump(0.5)
        dialog = win.findChild(QObject, "importDialog")
        W.check(list(dialog.property("nameFilters")) == ["FBX (*.fbx)"], "FBX… opens the dialog for FBX files")
        n0, before = IW.changes(doc), IW.imports(doc)
        IW.answer(dialog, b, files / "crate_cm.fbx")
        crate = w.landed("the FBX crate", n0, before)
        it = doc.item(crate) if crate else {}
        W.check(b.status == "Imported at 1/100: it was in centimetres", f"the unit message ({b.status!r})")
        W.check(abs(it.get("sy", 0) - 0.01) < 1e-9, f"the crate is scaled to metres (sy {it.get('sy')})")
        W.check(abs(it.get("y", -1) - TOP) < 0.01, f"the crate stands on the plinth (y {it.get('y')})")
        W.check(W.find(win.contentItem(), "importKeepSize") is not None, "Keep original size shows")
        w.snap("1-fbx-cm-message")
        report["fbx"] = {"status": b.status, "scale": it.get("sy"), "y": it.get("y")}
        QTest.keyClick(win, Qt.Key_Z, Qt.ControlModifier)
        W.pump(5, lambda: crate not in IW.imports(doc), "undo the crate")

        # 2. a .glb dropped on the plinth
        n0, before = IW.changes(doc), IW.imports(doc)
        W.check(w.drag(files / "bottle.glb", (0.5, 0.5)), "the landing ring shows while the bottle hovers")
        bottle = w.landed("the dropped bottle", n0, before)
        it = doc.item(bottle) if bottle else {}
        W.check(abs(it.get("sy", 0) - 1.0) < 1e-9 and it.get("fileUnit", 1.0) == 1.0, f"the bottle keeps its size (sy {it.get('sy')})")
        W.check(abs(it.get("y", -1) - TOP) < 0.01, f"the bottle's base is on the plinth's top (y {it.get('y')})")
        W.check(len(it.get("parts", [])) == 2, f"its two meshes are listed as parts ({[p['path'] for p in it.get('parts', [])]})")
        W.check(not b.status.startswith("Imported at"), f"no unit message for a file in metres ({b.status!r})")
        w.snap("2-glb-on-plinth")
        report["glb"] = {"scale": it.get("sy"), "y": it.get("y"), "parts": [p["path"] for p in it.get("parts", [])]}

        # 3. Alembic beside it, then play (first the same scene without it: what this window shows anyway)
        report["without_alembic"] = play(w, win, b)
        n0, before = IW.changes(doc), IW.imports(doc)
        w.drag(files / "wave.abc", (0.2, 0.86))
        wave = w.landed("the dropped Alembic", n0, before)
        w.snap("3-alembic-landed")
        report["alembic"] = play(w, win, b)
        distinct = report["alembic"]["distinct_frames"]
        W.check(distinct > 10, f"playing moves the Alembic frames ({report['alembic']})")
        w.snap("3-alembic-played")

        # 4. the asset library: off, then Poly Haven switched on by a real click
        W.click(win, w.item("rail_import"))
        W.pump(0.3)
        W.click(win, w.item("fly_import:library"))
        W.pump(0.6)
        W.check(not b.assets.models, "with every source off nothing is listed")
        W.check(W.find(win.contentItem(), "assetBrowse") is None, "no search while every source is off")
        w.snap("4-assets-off")
        W.click(win, w.item("assetSource_polyhaven"))
        W.pump(30, lambda: len(b.assets.models) > 0 or b.assets.line, "Poly Haven's list")
        W.check(len(b.assets.models) > 0, f"Poly Haven's models are listed once it is on ({len(b.assets.models)}; {b.assets.line!r})")
        W.pump(6, lambda: len(b.assets.thumbs) >= 6)
        w.snap("4-assets-on")
        report["assets"] = {"listed": len(b.assets.models), "thumbs": len(b.assets.thumbs)}
    finally:
        (out / "done-walk.json").write_text(json.dumps(report, indent=1), encoding="utf-8")
        print(json.dumps(report, indent=1))
        screen.close()
        app.processEvents()
        shutil.rmtree(project, ignore_errors=True)
    if W.FAILS:
        print(f"\n{len(W.FAILS)} check(s) failed")
        sys.exit(1)
    print("\nevery check passed")


if __name__ == "__main__":
    main()
