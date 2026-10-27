# Clay preview shots (3d-v4): the coarse preview the engine shows WHILE a stroke is drawn on a fine clay, and the
# settle to full detail after pen-up, looked at by real input in a background window (never focused).
# The hops scene: the sample scene, Q, the Lump tile, a click on the ground -> a Lump at the camera's grain (~1 mm) with
# its own 25 mm brush (radius >= 16 grains, so the preview is on). Each stroke is a real drag: press, 40 moves at 60 a
# second across the clay, then, with the button STILL HELD, the pointer still, a picture once the view has stopped
# changing (the preview); release; wait until the view's serial has not changed for 0.5 s (at most 4 s) and the view is
# idle; a picture (full detail). Both pictures are cropped around the stroke; the crops, and a difference picture (abs
# difference per pixel, x4) are saved, the mean and the largest difference inside the crop (0-255) go in the JSON. The
# pointer stays where the stroke ended, so its ring is in both pictures and drops out of the difference.
#   1. Add, Pull, Smooth: one stroke each, pictures "<brush>-1-before" (settled, before), "-2-held", "-3-after", crops
#      and difference;
#   2. Ctrl+Z (the Smooth stroke goes: the picture must match the one before it), Ctrl+Shift+Z (it is back: the
#      picture must match the one after it), then Add again over the same place as the first Add: a picture after just
#      3 moves ("again-2-start": no old shape may pop in; its difference from "again-1-before" must be small), one held
#      after 40, one after release. This checks the kept preview copy is up to date after undo / redo;
#   3. Cancel: a real Esc while the button is held (Esc is Clay's way out: ClayTool.leave() calls the stroke's cancel(),
#      the engine puts the stroke back). Checks: no new step on the clay, no error, the picture settles to what it was
#      before. Then Q and the Add tile again.
# Checks: no error on the status line after each step; each stroke exactly one new step on the clay and one history
# change. Start it with ROSTRUM3D_CLAY_VERIFY=1 so the engine says "live stroke != replay" on stderr when a stroke
# differs from its replay (the lead reads stderr). Needs the engine with the preview; the lead runs it:
#   $env:ROSTRUM3D_CLAY_VERIFY = "1"
#   heavy.ps1 run "sam: clay preview shots" gpu <venv python> apps\3d\tools\clay_preview_shots.py <out folder>
# Exit 0 = every check passed; else the failed checks are printed and it exits 1.
import json
import math
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path

os.environ.setdefault("ROSTRUM_BACKGROUND_WINDOWS", "1")
OUT = Path(sys.argv[1] if len(sys.argv) > 1 else r"C:\Users\Sam\.rostrum\waves\results\3d-v4\preview-shots")
sys.argv = sys.argv[:1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
import clay_walk as W  # noqa: E402  (the walk's helpers: pump, find, click, clay_on_screen, check)

from PySide6.QtCore import QPoint, QPointF, Qt  # noqa: E402
from PySide6.QtGui import QColor, QImage  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from rostrum_core import Document  # noqa: E402
from rostrum3d import KIND  # noqa: E402
from rostrum3d.script import run_source  # noqa: E402
from rostrum_gui.app import qt_app  # noqa: E402

MOVES = 40
SAME_MEAN = 3.0         # a picture "matches" another when its mean pixel difference in the crop is under this (of 255)
START_MEAN = 10.0       # the first moves of a stroke may add a little; a popped-in old shape would be far more


def settle(v, quiet=0.5, limit=4.0):
    """Pump until the view's serial has not changed for `quiet` s (at most `limit` s) and the view is idle."""
    end, last, seen = time.perf_counter() + limit, time.perf_counter(), v.serial
    while time.perf_counter() < end:
        W.pump(0.02)
        if v.serial != seen:
            seen, last = v.serial, time.perf_counter()
        elif time.perf_counter() - last >= quiet and v._r.idle() and not v._next.isActive():
            return True
    return False


def crop_box(at, radius, image, dpr):
    """The device-px box (x0, y0, x1, y1) around the stroke: 1.4 radii each side along it, 0.9 across."""
    x0, y0 = max(0, round((at.x() - 1.4 * radius) * dpr)), max(0, round((at.y() - 0.9 * radius) * dpr))
    x1, y1 = min(image.width(), round((at.x() + 1.4 * radius) * dpr)), min(image.height(), round((at.y() + 0.9 * radius) * dpr))
    return x0, y0, x1, y1


def compare(a, b, box):
    """(mean, max) of the largest per-channel difference over the box's pixels, and the difference picture (x4)."""
    x0, y0, x1, y1 = box
    diff = QImage(x1 - x0, y1 - y0, QImage.Format_RGB32)
    total, worst, n = 0, 0, 0
    for y in range(y0, y1):
        for x in range(x0, x1):
            pa, pb = a.pixelColor(x, y), b.pixelColor(x, y)
            d = max(abs(pa.red() - pb.red()), abs(pa.green() - pb.green()), abs(pa.blue() - pb.blue()))
            total, worst, n = total + d, max(worst, d), n + 1
            diff.setPixelColor(x - x0, y - y0, QColor(min(255, 4 * abs(pa.red() - pb.red())),
                                                      min(255, 4 * abs(pa.green() - pb.green())),
                                                      min(255, 4 * abs(pa.blue() - pb.blue()))))
    return round(total / max(1, n), 2), worst, diff


def shot(win, name):
    img = win.grabWindow()
    img.save(str(OUT / f"{name}.png"))
    return img


def save_crop(img, box, name):
    x0, y0, x1, y1 = box
    img.copy(x0, y0, x1 - x0, y1 - y0).save(str(OUT / f"{name}.png"))


def zigzag(at, radius, i, n, dy=0.0):
    """Move i of n: left to right across the clay, a little wave across the line."""
    return QPoint(round(at.x() - radius + 2 * radius * i / max(1, n - 1)),
                  round(at.y() + dy * radius + 0.12 * radius * math.sin(i / 3)))


def stroke(screen, win, name, at, radius, report, cancel=False, start_shot=False):
    """One real stroke with its pictures and numbers; see the top. Returns the settled picture (or None)."""
    v, doc = screen.bridge.viewport, screen.bridge.doc
    clay = v.clay.clayId
    steps0, changes0 = len(doc.item(clay)["steps"]), len(doc.history.changes)
    settle(v)
    before = shot(win, f"{name}-1-before")
    dpr = before.width() / win.width()
    box = crop_box(at, radius, before, dpr)
    first = zigzag(at, radius, 0, MOVES)
    QTest.mouseMove(win, first)
    W.pump(0.3)
    QTest.mousePress(win, Qt.LeftButton, Qt.NoModifier, first)
    W.pump(5, lambda: not v.clay._busy and v.clay._phase in ("sculpt", "orbit", ""), "the stroke's begin")
    W.check(v.clay._phase == "sculpt", f"{name}: the press began a stroke ({v.clay._phase})")
    t, p, rec = time.perf_counter(), first, {}
    for i in range(1, MOVES + 1):
        p = zigzag(at, radius, min(i, MOVES - 1), MOVES)
        QTest.mouseMove(win, p)
        t += 1 / 60
        W.pump(max(0.0, t - time.perf_counter()))
        if start_shot and i == 3:
            settle(v, quiet=0.3, limit=2.0)
            start = shot(win, f"{name}-2-start")
            m, mx, d = compare(before, start, box)
            d.save(str(OUT / f"{name}-2-start-difference.png"))
            rec["startVsBefore"] = {"mean": m, "max": mx}
            W.check(m < START_MEAN, f"{name}: after 3 moves nothing old has popped in (mean difference {m} of 255)")
            t = time.perf_counter()
    if cancel:
        W.pump(0.2)
        QTest.keyClick(win, Qt.Key_Escape)
        W.pump(0.5)
        rec["clayOnAfterEsc"] = bool(v.clay.on)
        QTest.mouseRelease(win, Qt.LeftButton, Qt.NoModifier, p)
        W.pump(1.0)
        settle(v)
        after = shot(win, f"{name}-3-after")
        m, mx, d = compare(before, after, box)
        d.save(str(OUT / f"{name}-3-difference.png"))
        rec["afterVsBefore"] = {"mean": m, "max": mx}
        W.check(len(doc.item(clay)["steps"]) == steps0, f"{name}: Esc kept no step on the clay")
        W.check(len(doc.history.changes) == changes0, f"{name}: Esc kept no history change")
        W.check(not v.status.startswith("Error"), f"{name}: no error ({v.status or '-'})")
        W.check(m < SAME_MEAN, f"{name}: the picture settles back to what it was (mean difference {m} of 255)")
        report[name] = rec
        return None
    settle(v, quiet=0.3, limit=2.0)                                     # the preview, button still held
    held = shot(win, f"{name}-2-held")
    t0 = time.perf_counter()
    QTest.mouseRelease(win, Qt.LeftButton, Qt.NoModifier, p)
    W.pump(10, lambda: not v.clay._ending and len(doc.item(clay)["steps"]) > steps0, "the stroke's step")
    rec["stepMs"] = round((time.perf_counter() - t0) * 1000)
    settled = settle(v, quiet=0.5, limit=4.0)
    rec["settledMs"] = round((time.perf_counter() - t0) * 1000)
    W.check(settled, f"{name}: the view settled after release ({rec['settledMs']} ms)")
    after = shot(win, f"{name}-3-after")
    for label, img in (("held", held), ("after", after)):
        save_crop(img, box, f"{name}-crop-{label}")
    m, mx, d = compare(held, after, box)
    d.save(str(OUT / f"{name}-crop-difference.png"))
    rec["heldVsAfter"] = {"mean": m, "max": mx}
    steps = len(doc.item(clay)["steps"])
    W.check(steps == steps0 + 1, f"{name}: one new step on the clay ({steps0} -> {steps})")
    W.check(len(doc.history.changes) == changes0 + 1, f"{name}: one history change ({changes0} -> {len(doc.history.changes)})")
    W.check(not v.status.startswith("Error"), f"{name}: no error ({v.status or '-'})")
    rec.update(box=list(box), before=before, after=after)
    report[name] = {k: x for k, x in rec.items() if k not in ("before", "after")}
    return rec


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    project = Path(tempfile.mkdtemp(prefix="rostrum-claypreview-"))
    app = qt_app()
    doc = Document.new(KIND, folder=project, item="scene")
    doc.run_script("sample.py", run_source(W.SOURCE, "sample.py"))
    doc.save()
    screen = W.app3d.Screen(W.SIZE)
    report = {"verify": os.environ.get("ROSTRUM3D_CLAY_VERIFY", ""), "pictures": str(OUT)}
    try:
        screen.show(doc, autosave=True)
        win, v = screen.win, screen.bridge.viewport
        W.pump(60, screen.ready, "the first picture")
        vp = W.find(win.contentItem(), "viewport3d")
        QTest.keyClick(win, Qt.Key_Q)
        W.pump(0.5)
        W.click(win, W.find(win.contentItem(), "clayMakeLump"))
        W.pump(0.5)
        ground = vp.mapToScene(QPointF(vp.width() * 0.5, vp.height() * 0.85)).toPoint()
        QTest.mouseMove(win, ground)
        QTest.mouseClick(win, Qt.LeftButton, Qt.NoModifier, ground)
        W.pump(20, lambda: v.clay.clayId != "", "the new clay")
        W.pump(3)
        clay = v.clay.clayId
        from rostrum3d import clay_detail
        it = screen.bridge.doc.item(clay)
        report.update(grain=clay_detail.detail(screen.bridge.doc.data, it, project), brushSize=it.get("brushSize"))
        print(f"clay {clay}: grain {report['grain'] * 1000:.2f} mm, brush {report['brushSize'] * 1000:.1f} mm")
        at, radius = W.clay_on_screen(screen, clay, vp)

        def pick(label):
            W.click(win, W.find(win.contentItem(), "clayBrush" + label))
            W.pump(0.5)

        first = {}
        for brush in ("Add", "Pull", "Smooth"):
            pick(brush)
            first[brush] = stroke(screen, win, brush.lower(), at, radius, report)
        smooth = first["Smooth"]
        if smooth is not None:
            box = tuple(smooth["box"])
            QTest.keyClick(win, Qt.Key_Z, Qt.ControlModifier)
            W.pump(0.5)
            settle(v)
            undone = shot(win, "undo-after-ctrl-z")
            m, mx, _ = compare(smooth["before"], undone, box)
            report["undo"] = {"vsBeforeSmooth": {"mean": m, "max": mx}}
            W.check(m < SAME_MEAN, f"Ctrl+Z: the picture is what it was before the Smooth stroke (mean difference {m} of 255)")
            QTest.keyClick(win, Qt.Key_Z, Qt.ControlModifier | Qt.ShiftModifier)
            W.pump(0.5)
            settle(v)
            redone = shot(win, "redo-after-ctrl-shift-z")
            m, mx, _ = compare(smooth["after"], redone, box)
            report["redo"] = {"vsAfterSmooth": {"mean": m, "max": mx}}
            W.check(m < SAME_MEAN, f"Ctrl+Shift+Z: the picture is what it was after the Smooth stroke (mean difference {m} of 255)")
        pick("Add")
        stroke(screen, win, "again", at, radius, report, start_shot=True)

        pick("Add")
        stroke(screen, win, "cancel", at, radius, report, cancel=True)
        if not v.clay.on:                                               # Esc left Clay: back in, Add chosen
            QTest.keyClick(win, Qt.Key_Q)
            W.pump(0.5)
            pick("Add")
            W.check(v.clay.on, "Q turns Clay on again after the Esc")
    except Exception as e:  # noqa: BLE001  a crash is a failed run, said with its reason
        W.FAILS.append(f"the run stopped: {type(e).__name__}: {e}")
    finally:
        report["fails"] = W.FAILS
        (OUT / "clay_preview_shots.json").write_text(json.dumps(report, indent=1), encoding="utf-8")
        screen.close()
        W.pump(1.0)
        shutil.rmtree(project, ignore_errors=True)
    print(f"{len(W.FAILS)} failed check(s); pictures and numbers in {OUT}")
    for f in W.FAILS:
        print("  " + f)
    app.quit()
    return 1 if W.FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
