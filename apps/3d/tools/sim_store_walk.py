# The fall from the shared result store, then a body moved (critic should-fix 6): project 1 simulates a fall (a real click
# on Simulate); project 2 has the same set-up, so its row reads Stored without computing. At frame 30 a picture; the bowl's
# X is typed (real mouse and keys); the row must read "Out of date" (striped) and the viewport must keep showing the old fall
# at frame 30 (the picture of the fall's bodies is the same, only the bowl may have moved).
#   heavy.ps1 run "hem-B2: sim store walk" gpu <venv python> apps\3d\tools\sim_store_walk.py [out folder]
import os
import shutil
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("ROSTRUM_BACKGROUND_WINDOWS", "1")
OUT = Path(sys.argv[1] if len(sys.argv) > 1 else r"C:\Users\Sam\.rostrum\waves\results\3d-leftovers2\sim-store")
sys.argv = sys.argv[:1]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "app" / "tests"))
import sim25_walk as S  # noqa: E402  (its helpers; puts this checkout's code first)
import clay_walk as W  # noqa: E402
import copies_walk as CW  # noqa: E402

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from rostrum_core import Document  # noqa: E402
from rostrum3d import KIND  # noqa: E402
from rostrum3d.script import run_source  # noqa: E402
from rostrum_gui.app import qt_app  # noqa: E402
import main as app3d  # noqa: E402

SCENE = (S.SCENE.replace('name="Bowl", material=bowlmat)', 'name="Bowl", material=bowlmat, simulate="still")')
         + 'copies("buds", source="bud", layout="line", count=12, spacingX=0.07, simulate="falls")\n')


def make(folder):
    doc = Document.new(KIND, folder=folder, item="scene")
    doc.run_script("drop03.py", run_source(SCENE, "drop03.py"))
    doc.save()
    return doc


def open_screen(doc):
    screen = app3d.Screen(S.SIZE)
    screen.show(doc, shot_id="drop03", autosave=True)
    w = CW.Walk(screen, OUT)
    W.pump(90, screen.ready, "the first picture")
    return screen, w


def crop(w, name):
    W.pump(30, lambda: w.s.ready(), name)
    W.pump(0.5)
    img = w.win.grabWindow()
    img.save(str(OUT / f"{name}.png"))
    vp = w.vp.mapToScene(w.vp.boundingRect().topLeft())
    return img.copy(int(vp.x()), int(vp.y()), int(w.vp.width()), int(w.vp.height()))


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    root = Path(tempfile.mkdtemp(prefix="rostrum-simstore-"))
    app = qt_app()
    try:
        doc1 = make(root / "one")
        screen, w = open_screen(doc1)
        info = w.b.shot_info()
        fps, frames = info["fps"], info["end"] - info["start"] + 1
        if w.b.sim.canRun:                      # (a set-up the store already holds shows Stored at once)
            S.simulate_click(w)
        W.check(w.b.sim.state == "stored", f"project 1: Stored ({w.b.sim.state!r})")
        screen.close()
        app.processEvents()

        doc2 = make(root / "two")
        screen, w = open_screen(doc2)
        b, sim = w.b, w.b.sim
        W.pump(5, lambda: sim.state == "stored", "project 2: the row reads Stored")
        W.check(sim.state == "stored", f"project 2: Stored from the store without a click ({sim.state!r}: {sim.label!r})")
        key0 = S.shot_of(doc2).get("simKey", "")
        S.go_to(w, 30, fps, frames)
        before = crop(w, "1-store-hit-frame30")
        at = w.where((0.3, 0.166, 0.0))        # a real click on the bowl's inner wall in the view (its row is below the list's fold)
        QTest.mouseMove(w.win, at)
        W.pump(0.2)
        QTest.mouseClick(w.win, Qt.LeftButton, Qt.NoModifier, at)
        W.pump(5, lambda: b.selected == "bowl", "the bowl selected")
        W.pump(5, lambda: W.find(w.win.contentItem(), "row:x") is not None, "the bowl's X row")
        w.type_into("x", 0.06)
        W.pump(3, lambda: sim.state == "out of date", "Out of date")
        W.check(sim.state == "out of date", f"project 2: moving the bowl reads Out of date ({sim.state!r})")
        W.check(w.item("simStripes") is not None, "the bar is striped")
        W.check(S.shot_of(doc2).get("simKey") == key0 and bool(key0), f"the shot keeps its result key ({key0!r})")
        W.check(abs(b.frame - 30) <= 1, f"still at frame 30 ({b.frame})")
        after = crop(w, "2-moved-frame30")
        S.go_to(w, 0, fps, frames)
        start = crop(w, "3-frame0-for-reference")

        def line_pixels(img):               # the buds' colour in the strip where frame 0 holds them (a row, high up)
            n = 0
            for y in range(int(img.height() * 0.08), int(img.height() * 0.2)):
                for x in range(0, img.width(), 2):
                    c = img.pixelColor(x, y)
                    n += c.red() > 150 and 80 < c.green() < 190 and c.blue() < 90
            return n
        a_, s_, b_ = line_pixels(after), line_pixels(start), line_pixels(before)
        print(f"buds' colour in the frame-0 strip: frame 0 {s_}, frame 30 before the move {b_}, after the move {a_}", flush=True)
        W.check(s_ > 200 and a_ < s_ * 0.4 and abs(a_ - b_) < s_ * 0.2,
                "after the move the view still shows the fall at frame 30 (the buds did not jump back to their start row)")
        screen.close()
        app.processEvents()
    finally:
        shutil.rmtree(root, ignore_errors=True)
    print("FAILS:" if W.FAILS else "ALL PASSED", *W.FAILS, sep="\n  ")
    sys.exit(1 if W.FAILS else 0)


if __name__ == "__main__":
    main()
