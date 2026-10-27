# Simulated copies in the real window (a background window at 1646 x 900, never focused): twelve buds fall into a bowl,
# stored. Real clicks only; the document and the stored result are read, to CHECK:
#   1. at frame 60 a click where a bud FELL (its stored place, projected) picks that copy ("Copy n of Buds") ... "b1-pick"
#   2. the Count row's line ("n of 12 in Drop 03") at frames 0 and 60: the seen count is worked out per frame
#   3. Escape to the Scene panel, a click on Turn into keys: one undo step, the buds Off, every copy keyed; the same
#      click spot picks the same copy at frame 60 (the keyed fall stands where the fall was) ......... "b2-keys"
# (A nudge surviving a re-run and a keyed copy's drag are guarded by test_sim_copy_keys.py / test_copy_keys_drag.py.)
# Numbers to sim_copies_walk.json. The lead runs it:
#   heavy.ps1 run "sam: sim copies walk" gpu <venv python> apps\3d\tools\sim_copies_walk.py <out folder>
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("ROSTRUM_BACKGROUND_WINDOWS", "1")
OUT = Path(sys.argv[1] if len(sys.argv) > 1 else r"C:\Users\Sam\.rostrum\waves\results\3d-scrub-cloth")
sys.argv = sys.argv[:1]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "app" / "tests"))
import clay_walk as W  # noqa: E402
import copies_walk as CW  # noqa: E402
import scrub_profile as SP  # noqa: E402  (the buds scene, the ruler)

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from rostrum_core import Document  # noqa: E402
from rostrum_core.cache import CACHE  # noqa: E402
from rostrum3d import KIND  # noqa: E402
from rostrum3d.script import run_source  # noqa: E402
from rostrum3d.sim import inputs as SI  # noqa: E402
from rostrum3d.sim.result import read  # noqa: E402
from rostrum_gui.app import qt_app  # noqa: E402

import main as app3d  # noqa: E402

FRAME = 60
NUMBERS: dict = {}


def go_to(w, frame, fps, frames):
    ruler = SP.find_class(w.win.contentItem(), "TimeRuler")
    QTest.mouseClick(w.win, Qt.LeftButton, Qt.NoModifier, SP.ruler_x(ruler, frame, fps, frames))
    W.pump(5, lambda: abs(w.b.frame - frame) <= 1, f"the playhead at frame {frame}")
    W.pump(5, w.s.ready, "the picture")
    W.pump(0.5)


def snap(w, name):
    W.pump(0.4)
    path = OUT / f"simcopies-{name}.png"
    w.win.grabWindow().save(str(path))
    NUMBERS.setdefault("pictures", {})[name] = str(path)


def changes(doc):
    return len(doc.history.changes)


def click_at(w, at):
    QTest.mouseMove(w.win, at)
    QTest.mouseClick(w.win, Qt.LeftButton, Qt.NoModifier, at)
    W.pump(3, lambda: w.v.copies.copy is not None, "a copy picked")
    W.pump(0.3)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    project = Path(tempfile.mkdtemp(prefix="rostrum-simcopies-"))
    app = qt_app()
    doc = Document.new(KIND, folder=project, item="scene")
    doc.run_script("buds.py", run_source(SP.BUDS, "buds.py"))
    doc.save()
    screen = app3d.Screen(SP.SIZE)
    try:
        screen.show(doc, shot_id="drop03", autosave=True)
        w = CW.Walk(screen, OUT)
        b, sim = w.b, w.b.sim
        W.pump(90, screen.ready, "the first picture")
        SP.buds_prepare(w, doc)
        info = b.shot_info()
        fps, frames = info["fps"], info["end"] - info["start"] + 1
        key = SI.sim_inputs(doc.data, "drop03", project)[1]       # the result for the inputs as they are (stored)
        res = read(CACHE.get(SI.KIND, key))
        rows = res.rows_of("buds")
        buds = doc.item("buds")

        # 2. the seen line at frame 0 and at frame 60
        SP.select(w, "buds")
        go_to(w, 0, fps, frames)
        NUMBERS["seenAt0"] = b.copies_note("buds")
        go_to(w, FRAME, fps, frames)
        NUMBERS["seenAt60"] = b.copies_note("buds")

        # 1. click where a bud fell: the one nearest the middle of the picture
        def world(c):
            p, _ = res.sample(FRAME, rows[c])
            return [p[0] + buds.get("x", 0.0), p[1] + buds.get("y", 0.0), p[2] + buds.get("z", 0.0)]
        mid = w.vp.mapToScene(w.vp.boundingRect().center())
        spots = [(c, w.where(world(c))) for c in range(len(rows))]
        c, at = min(spots, key=lambda s: (s[1].x() - mid.x()) ** 2 + (s[1].y() - mid.y()) ** 2)
        laid = (buds.get("x", 0.0) + c * 0.07, buds.get("y", 0.0))
        NUMBERS["clicked"] = {"copy": c, "fellTo": [round(v, 3) for v in world(c)], "laidOutAt": laid, "at": [at.x(), at.y()]}
        click_at(w, at)
        got = w.v.copies.copy
        W.check(got is not None and got["item"] == "buds", f"a click where a bud fell picks a bud ({got})")
        if got is not None:
            NUMBERS["picked"] = got["index"]
        snap(w, "b1-pick")

        # 3. Turn into keys by a click in the Scene panel
        for _ in range(4):
            if b.selected == "":
                break
            QTest.keyClick(w.win, Qt.Key_Escape)
            W.pump(0.3)
        btn = w.item("sceneSimKeys")
        if btn is not None:
            n = changes(doc)
            W.click(w.win, btn)
            W.pump(5, lambda: doc.item("buds").get("simulate") == "off", "the buds Off after Turn into keys")
            W.check(changes(doc) == n + 1, f"Turn into keys: one undo step ({n} -> {changes(doc)})")
            ck = doc.item("buds").get("copyKeys") or []
            copies_keyed = {r[0] if isinstance(r, list) else r.get("copy") for r in ck}
            W.check(len(copies_keyed) == len(rows), f"every copy keyed ({len(copies_keyed)} of {len(rows)}, {len(ck)} rows)")
            NUMBERS["copyKeyRows"] = len(ck)
            W.pump(5, screen.ready, "the picture")
            go_to(w, FRAME, fps, frames)
            SP.select(w, "buds")
            click_at(w, at)
            again = w.v.copies.copy
            W.check(again is not None and got is not None and again["index"] == got["index"],
                    f"the keyed fall stands where the fall was: the same spot picks the same copy ({again})")
            snap(w, "b2-keys")
    finally:
        NUMBERS["fails"] = list(W.FAILS)
        (OUT / "sim_copies_walk.json").write_text(json.dumps(NUMBERS, indent=2), encoding="utf-8")
        screen.close()
        app.processEvents()
        shutil.rmtree(project, ignore_errors=True)
    print(json.dumps(NUMBERS, indent=1))
    print("FAILS:" if W.FAILS else "ALL PASSED", *W.FAILS, sep="\n  ")
    sys.exit(1 if W.FAILS else 0)


if __name__ == "__main__":
    main()
