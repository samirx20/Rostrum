# All curves walk (3d-people PR2 finish): the animation panel's "All curves" button clicked by real input in the real window,
# 1646 x 900, behind the person's work (never focused). The sample scene with keys on two items (its camera moves too);
# Alt+2 (Animate), a real click on the block's stretch between its two keys in the timeline (the settings panel becomes that
# animation, AnimPanel.qml), then a real click on its "All curves": the timeline's curve view is on, every animated item's curves.
#   <venv python> apps\3d\app\tests\all_curves_walk.py --out <folder>
# Exit 0 = every check passed.
import argparse
import os
import shutil
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("ROSTRUM_BACKGROUND_WINDOWS", "1")
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import clay_walk as W  # noqa: E402
import curves_walk as CV  # noqa: E402

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from rostrum_core import Document, Who  # noqa: E402
from rostrum_core.keys import keys_of  # noqa: E402
from rostrum3d import KIND  # noqa: E402
from rostrum3d.script import run_source  # noqa: E402
from rostrum_gui.app import qt_app  # noqa: E402
from screen3d.sample import SOURCE  # noqa: E402

import main as app3d  # noqa: E402


def main():
    a = argparse.ArgumentParser()
    a.add_argument("--out", default=r"C:\Users\Sam\.rostrum\waves\results\3d-pr2-finish-pr3\curves")
    out = Path(a.parse_args().out)
    out.mkdir(parents=True, exist_ok=True)
    project = Path(tempfile.mkdtemp(prefix="rostrum-allcurves-"))
    app = qt_app()  # noqa: F841
    doc = Document.new(KIND, folder=project, item="scene")
    doc.run_script("sample.py", run_source(SOURCE.replace("end=2)", "end=4)"), "sample.py"))
    doc.apply([{"op": "key.add", "target": [o], "args": {"prop": p, "t": t, "v": v}} for o, p, t, v in CV.KEYS], Who.person())
    doc.save()
    screen = app3d.Screen(CV.SIZE)
    try:
        screen.show(doc, autosave=True)
        w = CV.Walk(screen, out)
        b, win, cv = w.b, w.win, w.b.curves
        W.pump(60, screen.ready, "the first picture")
        QTest.keyClick(win, Qt.Key_2, Qt.AltModifier)
        W.pump(1.0)
        W.check(b.page == "animate", f"Alt+2: the Animate page ({b.page})")
        band = w.item("stretch:" + keys_of(doc.item("block"), "y")[0]["id"])
        if band is not None:
            W.click(win, band)
            W.pump(1.0)
        W.check(b._stretch.shown, "the stretch clicked: the settings panel is that animation")
        w.snap("1-stretch-picked")
        W.check(not (cv.on and cv.all), "before the click: not every curve shown")
        button = w.item("animAllCurves")
        if button is not None:
            W.click(win, button)
            W.pump(1.0)
        groups = {f["group"] for f in cv.fields}
        W.check(cv.on, "All curves clicked: the curve view is on")
        W.check(groups == {"block", "ball", "cam"}, f"every animated item's curves ({sorted(groups)}: {[f['id'] for f in cv.fields]})")
        w.snap("2-all-curves")
    finally:
        screen.close()
        W.pump(0.5)
        shutil.rmtree(project, ignore_errors=True)
    if W.FAILS:
        print("FAILED:\n  " + "\n  ".join(W.FAILS))
        sys.exit(1)
    print("all curves walk: every check passed")


if __name__ == "__main__":
    main()
