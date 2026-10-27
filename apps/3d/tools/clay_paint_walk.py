# Clay paint walk (3d-cl4, member D): painting on a clay tried by real input in the real window (a background window at
# 1646 x 900, never focused): the real mouse and keys on visible controls found by objectName, bridge calls never for a
# step itself (the document is only read, to CHECK). A scratch project (ground, two lights, the shot camera, one clay:
# a lump of fixed detail 1.5 mm, about half the view tall, made by script); then:
#   1. a click on the clay selects it; B: Paint is on and its panel shows for a clay ............. "1-paint-mode-clay"
#   2. a horizontal stripe dragged across the clay's front with the left button (many small moves): one stroke, kept as
#      `anchors` + `reach` on the clay's surface (no `points` needed) ................................ "2-stripe-quick"
#   3. B (leaves Paint), Q (Clay), the Add tile, a short stroke dragged just under the middle of the stripe so the
#      surface bulges there: the clay has one more step, the stroke in the document is unchanged; the picture comes back
#      with the paint on the new shape ................................................................ "3-reshaped-quick"
#   4. Q (leaves Clay), Shift+F (Final), waited for until Cycles has converged enough ................ "4-reshaped-final"; Shift+F: Quick
#   5. B, "+" adds a layer, Paints set to Relief (the dropdown, its entry clicked), two short wavy strokes on the upper
#      half, Final ..................................................................................... "5-relief-final"
# The time from the mouse-up to the picture settling (no new picture for a second) after steps 2 and 3 is measured.
# Every check and the numbers go to clay_paint_walk.json; the pictures (png) are in the out folder. The lead runs it:
#   heavy.ps1 run "sam: cl4 paint walk" gpu <venv python> apps\3d\tools\clay_paint_walk.py <out folder>
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
OUT = Path(sys.argv[1] if len(sys.argv) > 1 else r"C:\Users\Sam\.rostrum\waves\results\3d-cl4\walk")
sys.argv = sys.argv[:1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
import clay_walk as W  # noqa: E402  (puts this checkout's code first; its real-input helpers)

from PySide6.QtCore import QPoint, QPointF, Qt  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from rostrum_core import Document, Who  # noqa: E402
from rostrum3d import KIND  # noqa: E402
from rostrum3d.script import run_source  # noqa: E402
from rostrum_gui.app import qt_app  # noqa: E402
from screen3d.gizmo import View  # noqa: E402

AGENT = Who.agent("cl4-paint-walk") if hasattr(Who, "agent") else Who.person()
RADIUS = 0.1                    # the clay's radius, metres
SCENE = '''
clayc = material("clayc", baseColor="#4b3f38", roughness=0.6)
floor = material("floor", baseColor="#6a6d72", roughness=0.8)
mesh("ground", shape="plane", width=3, depth=3, material=floor)
light("key", kind="rect", width=0.6, height=0.4, intensity=30, x=-0.5, y=0.7, z=0.6).aim((0, 0.1, 0))
light("sky", kind="dome", color="#c8d2e0", intensity=0.5)
cam = camera("cam", focalLength=50, y=0.14, z=0.78).aim((0, 0.1, 0))
shot("s", camera=cam, fps=24, start=0, end=2)
'''
REPORT = {"steps": {}, "pictures": {}, "timesMs": {}}
CURRENT = ["setup"]


def chk(ok, line):
    """W.check, and kept under the current step in the report."""
    W.check(ok, line)
    REPORT["steps"].setdefault(CURRENT[0], []).append({"ok": bool(ok), "check": line})


def step(name):
    CURRENT[0] = name
    print(f"-- {name}", flush=True)


def settle(v, t0, quiet=1.0, timeout=90.0, what="the picture to settle"):
    """Wait until the engine is idle and no new picture came for `quiet` s; returns ms from `t0` to the last new picture
    (or to the moment of `t0` when none came)."""
    last, serial, end = max(t0, time.perf_counter()), v.serial, time.perf_counter() + timeout
    last = t0
    while time.perf_counter() < end:
        W.pump(0.02)
        now = time.perf_counter()
        if v.serial != serial:
            serial, last = v.serial, now
        if v._r.idle() and not v._next.isActive() and now - max(last, t0) > quiet:
            return (max(last, t0) - t0) * 1000
    W.FAILS.append(f"timed out waiting for {what}")
    return (time.perf_counter() - t0) * 1000


def shot(win, v, name, t0=None):
    """Pointer parked on the header, the picture settled, a grab named `name`."""
    QTest.mouseMove(win, QPoint(8, 8))
    ms = settle(v, t0 if t0 is not None else time.perf_counter(), what=f"{name}: the picture")
    path = OUT / f"{name}.png"
    win.grabWindow().save(str(path))
    REPORT["pictures"][name] = str(path)
    return ms


def white_share(win, box):
    """The share of pixels in `box` (window px: x0, y0, x1, y1) that are near white (the stripe's paint on the dark clay)."""
    img = win.grabWindow()
    dpr = img.width() / win.width()
    x0, y0, x1, y1 = (round(c * dpr) for c in box)
    n = white = 0
    for y in range(y0, y1 + 1):
        for x in range(x0, x1 + 1):
            c = img.pixelColor(x, y)
            n, white = n + 1, white + (min(c.red(), c.green(), c.blue()) > 190)
    return white / max(1, n)


def paint_back(win, boxes, t0, need, timeout=15.0):
    """Sample the near-white share of each box every 0.25 s until all are >= `need` (the paint is in the picture) or the
    timeout; returns (ms from t0 when they were, or None; the shares last seen; whether it was there at the first look)."""
    first, end = None, time.perf_counter() + timeout
    while True:
        shares = [white_share(win, b) for b in boxes]
        ok = min(shares) >= need
        first = ok if first is None else first
        if ok:
            return (time.perf_counter() - t0) * 1000, shares, first
        if time.perf_counter() > end:
            return None, shares, first
        W.pump(0.25)


def clay_on_screen(screen, clay_id, vp_item):
    """The window point of the clay's middle and its radius in window px."""
    v, frame = screen.bridge.viewport, screen.bridge.frame
    scene, cam = v.sent()
    view = View.of(cam, scene, frame, cam["width"], cam["height"])
    from rostrum3d import aim, through
    world = through.find_item(scene, clay_id, frame)[0]
    x, y, depth = view.project(aim.point(world, [0.0, 0.0, 0.0]))
    to_win = 1.0 / (v._scale * vp_item.window().devicePixelRatio())
    top = vp_item.mapToScene(QPointF(0, 0))
    return QPointF(top.x() + x * to_win, top.y() + y * to_win), RADIUS / view.units(depth) * to_win


def drag(win, pts, mods=Qt.NoModifier, pause=0.012):
    """One real drag through `pts` (window px): press on the first, many small moves, let go on the last. Returns the
    time of the mouse-up."""
    QTest.mouseMove(win, pts[0])
    W.pump(0.25)
    QTest.mousePress(win, Qt.LeftButton, mods, pts[0])
    for p in pts[1:]:
        QTest.mouseMove(win, p)
        W.pump(pause)
    t = time.perf_counter()
    QTest.mouseRelease(win, Qt.LeftButton, mods, pts[-1])
    return t


def line(a, b, n=48, wave=0.0, waves=2.0):
    """n+1 window points from a to b, with a sine wave across the line (`wave` px tall) when asked."""
    dx, dy = b[0] - a[0], b[1] - a[1]
    length = max(1e-6, math.hypot(dx, dy))
    nx, ny = -dy / length, dx / length
    out = []
    for i in range(n + 1):
        t = i / n
        w = wave * math.sin(2 * math.pi * waves * t)
        out.append(QPoint(round(a[0] + dx * t + nx * w), round(a[1] + dy * t + ny * w)))
    return out


def find_text(root, text):
    """The first visible item under `root` showing `text`."""
    for c in root.childItems():
        if not c.isVisible():
            continue
        if c.property("text") == text:
            return c
        hit = find_text(c, text)
        if hit is not None:
            return hit
    return None


def layers(doc, clay_id):
    return [doc.item(p["id"]) for p in doc.item(clay_id).get("paints", [])]


def final_look(win, v, name, what):
    """Shift+F, waited for until Cycles has converged enough, a picture; returns the seconds it took."""
    QTest.mouseMove(win, QPoint(8, 8))
    t0 = time.perf_counter()
    QTest.keyClick(win, Qt.Key_F, Qt.ShiftModifier)
    W.pump(240, lambda: v.look == "final" and (v.final.fraction >= 0.5 or v.finalLine.startswith("Final · done")),
           f"{what}: Final to converge")
    W.pump(0.5)
    secs = time.perf_counter() - t0
    chk(v.look == "final" and not v.status.startswith("Error"), f"{what}: the Final look draws ({v.finalLine})")
    path = OUT / f"{name}.png"
    win.grabWindow().save(str(path))
    REPORT["pictures"][name] = str(path)
    REPORT["timesMs"][f"{name}-final-converge"] = round(secs * 1000)
    return secs


def quick_again(win, v):
    n = v.serial
    QTest.keyClick(win, Qt.Key_F, Qt.ShiftModifier)
    W.pump(30, lambda: v.look == "quick" and v.serial > n, "the quick look again")
    chk(v.look == "quick", "Shift+F again: back to Quick")


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    project = Path(tempfile.mkdtemp(prefix="rostrum-claypaintwalk-"))
    app = qt_app()
    doc = Document.new(KIND, folder=project, item="scene")
    doc.run_script("scene.py", run_source(SCENE, "scene.py"))
    doc.apply([{"op": "clay.add", "args": {"id": "blob", "at": [0, 0.1, 0], "radius": RADIUS, "material": "clayc"}}], AGENT)
    doc.apply([{"op": "clay.set", "target": ["blob"], "args": {"detailMode": "fixed", "detail": 0.0015}}], AGENT)
    doc.save()
    screen = W.app3d.Screen(W.SIZE)
    try:
        screen.show(doc, autosave=True)
        win, v, b = screen.win, screen.bridge.viewport, screen.bridge
        W.pump(90, screen.ready, "the first picture")
        vp = W.find(win.contentItem(), "viewport3d")
        D = b.doc
        W.pump(30, lambda: v.sent()[0] is not None and v.serial > 0, "the first scene")
        settle(v, time.perf_counter(), what="the first settled picture")
        mid, rpx = clay_on_screen(screen, "blob", vp)
        cx, cy = mid.x(), mid.y()
        REPORT["clayOnScreen"] = {"centre": [round(cx), round(cy)], "radiusPx": round(rpx)}
        vp_h = vp.height() * 1.0
        chk(0.35 <= 2 * rpx / vp_h <= 0.75, f"the clay fills about half the view ({2 * rpx / vp_h:.0%} of its height)")

        # 1. select by a click, B
        step("1 paint mode")
        QTest.keyClick(win, Qt.Key_V)                                   # Select (the default; made sure of)
        W.pump(0.3)
        at = QPoint(round(cx), round(cy))
        QTest.mouseMove(win, at)
        QTest.mouseClick(win, Qt.LeftButton, Qt.NoModifier, at)
        W.pump(10, lambda: b.selected == "blob", "the clay selected by the click")
        chk(b.selected == "blob", f"a click on the clay selects it ({b.selected})")
        QTest.keyClick(win, Qt.Key_B)
        W.pump(2, lambda: v.paint.on, "Paint on")
        W.pump(0.5)
        chk(v.paint.on and v.paint.can, "B turns Paint on for the clay")
        chk(W.find(win.contentItem(), "paintAddLayer") is not None, "the Paint panel shows (its + for a layer is on screen)")
        shot(win, v, "1-paint-mode-clay")

        # 2. the stripe
        step("2 stripe")
        y_stripe = cy - 0.12 * rpx
        n0 = len(D.history.changes)
        t_up = drag(win, line((cx - 0.62 * rpx, y_stripe), (cx + 0.62 * rpx, y_stripe), n=60))
        W.pump(20, lambda: len(D.history.changes) > n0 or v.status.startswith("Error"), "the stripe's change")
        t_doc = (time.perf_counter() - t_up) * 1000
        ms = settle(v, t_up, what="the stripe's picture")
        REPORT["timesMs"]["stripe-doc-change"], REPORT["timesMs"]["stripe-picture-settled"] = round(t_doc), round(ms)
        chk(not v.status.startswith("Error"), f"no error after the stripe ({v.status or '-'})")
        chk(len(D.history.changes) == n0 + 1, f"the stripe is one undo step ({n0} -> {len(D.history.changes)})")
        ls = layers(D, "blob")
        strokes = ls[-1].get("strokes", []) if ls else []
        chk(len(ls) == 1 and len(strokes) == 1, f"one paint layer with one stroke ({len(ls)} layer(s), {len(strokes)} stroke(s))")
        s0 = strokes[0] if strokes else {}
        chk(len(s0.get("anchors", [])) > 8 and s0.get("reach", 0) > 0 and not s0.get("points"),
            f"the stroke is kept as anchors + reach, no points ({len(s0.get('anchors', []))} anchors, reach {s0.get('reach')}, "
            f"points {len(s0.get('points') or [])})")
        stripe_box = (cx - 0.4 * rpx, y_stripe - 0.03 * rpx, cx + 0.4 * rpx, y_stripe + 0.03 * rpx)
        QTest.mouseMove(win, QPoint(8, 8))                              # off the picture: no brush ring over the stripe
        W.pump(0.3)
        back, shares, first = paint_back(win, [stripe_box], t_up, 0.15)
        REPORT["timesMs"]["stripe-paint-in-picture"] = None if back is None else round(back)
        chk(back is not None, f"the stripe shows in the Quick picture ({shares[0]:.0%} of its row paint-white; in the picture "
            f"{'when it settled' if first else 'only ' + str(round(back or 0)) + ' ms after the mouse-up'})")
        shot(win, v, "2-stripe-quick")
        stripe_kept = json.dumps(strokes, sort_keys=True)
        layer_id = ls[-1]["id"] if ls else ""

        # 3. reshape under the stripe, with the Clay tool
        step("3 reshape")
        QTest.keyClick(win, Qt.Key_B)
        W.pump(2, lambda: not v.paint.on, "Paint off")
        QTest.keyClick(win, Qt.Key_Q)
        W.pump(2, lambda: v.clay.on, "Clay on")
        W.pump(0.5)
        chk(not v.paint.on and v.clay.on and v.clay.clayId == "blob", f"B leaves Paint, Q turns Clay on for the clay ({v.clay.clayId})")
        W.pick_tile(win, v.clay, "Add", "add")
        steps0 = len(D.item("blob").get("steps", []))
        y_add = y_stripe + 0.10 * rpx
        t_up = drag(win, line((cx - 0.22 * rpx, y_add), (cx + 0.22 * rpx, y_add), n=24))
        W.pump(20, lambda: not v.clay._ending and len(D.item("blob").get("steps", [])) > steps0, "the Add stroke's step")
        t_doc = (time.perf_counter() - t_up) * 1000
        ms = settle(v, t_up, what="the reshaped picture")
        REPORT["timesMs"]["reshape-doc-change"], REPORT["timesMs"]["reshape-picture-settled"] = round(t_doc), round(ms)
        steps1 = len(D.item("blob").get("steps", []))
        chk(steps1 == steps0 + 1, f"the clay has one more step ({steps0} -> {steps1})")
        chk(json.dumps(layers(D, "blob")[-1].get("strokes", []), sort_keys=True) == stripe_kept,
            "the paint stroke is unchanged in the document")
        chk(not v.status.startswith("Error"), f"no error after the reshape ({v.status or '-'})")
        ends = [(cx + a_ * rpx, y_stripe - 0.03 * rpx, cx + b_ * rpx, y_stripe + 0.03 * rpx)
                for a_, b_ in ((-0.55, -0.42), (0.42, 0.55))]      # the stripe's two ends (the bulge lifts its middle)
        QTest.mouseMove(win, QPoint(8, 8))                              # off the picture: no brush ring over the stripe
        W.pump(0.3)
        back, shares, first = paint_back(win, ends, t_up, 0.3)
        REPORT["timesMs"]["reshape-paint-in-picture"] = None if back is None else round(back)
        REPORT["reshapeEndShares"] = [round(x, 3) for x in shares]
        chk(back is not None, f"the stripe shows in the Quick picture after the reshape (its two ends {shares[0]:.0%}, "
            f"{shares[1]:.0%} paint-white; in the picture "
            f"{'when it settled' if first else 'only ' + str(round(back or 0)) + ' ms after the mouse-up'})")
        shot(win, v, "3-reshaped-quick")

        # 4. Final
        step("4 final")
        QTest.keyClick(win, Qt.Key_Q)                                   # Clay off (the clay stays selected)
        W.pump(2, lambda: not v.clay.on, "Clay off")
        QTest.keyClick(win, Qt.Key_Escape)                              # nothing selected: no handles over the picture
        W.pump(0.5)
        final_look(win, v, "4-reshaped-final", "after the reshape")
        quick_again(win, v)

        # 5. Relief
        step("5 relief")
        QTest.mouseMove(win, at)
        QTest.mouseClick(win, Qt.LeftButton, Qt.NoModifier, at)         # select the clay again by a click
        W.pump(10, lambda: b.selected == "blob", "the clay selected again")
        QTest.keyClick(win, Qt.Key_B)
        W.pump(2, lambda: v.paint.on, "Paint on again")
        W.pump(0.5)
        add = W.find(win.contentItem(), "paintAddLayer")
        chk(add is not None, "the + for a new layer is on screen")
        n_layers = len(layers(D, "blob"))
        if add is not None:
            W.click(win, add)
            W.pump(10, lambda: len(layers(D, "blob")) > n_layers, "the new layer")
        chk(len(layers(D, "blob")) == n_layers + 1, f"+ adds a layer ({n_layers} -> {len(layers(D, 'blob'))})")
        field = W.find(win.contentItem(), "paintChannel")
        chk(field is not None, "the Paints choice is on screen")
        if field is not None:
            W.click(win, field)
            W.pump(1.0)
            lst = W.find(win.contentItem(), "choiceList")
            opt = find_text(lst, "Relief") if lst is not None else None
            chk(opt is not None, "the Paints list is open and has Relief")
            if opt is not None:
                W.click(win, opt)
                W.pump(1.0)
        new = layers(D, "blob")[-1] if layers(D, "blob") else {}
        chk(new.get("channel") == "height", f"the new layer paints Relief (channel {new.get('channel')})")
        n0 = len(D.history.changes)
        for k, (yy, ph) in enumerate(((cy - 0.55 * rpx, 6.0), (cy - 0.30 * rpx, 6.0))):
            t_up = drag(win, line((cx - 0.5 * rpx, yy), (cx + 0.5 * rpx, yy), n=48, wave=0.05 * rpx, waves=2.5))
            W.pump(20, lambda: len(D.history.changes) > n0 + k, f"relief stroke {k + 1}'s change")
            settle(v, t_up, what=f"relief stroke {k + 1}'s picture")
        strokes = layers(D, "blob")[-1].get("strokes", []) if layers(D, "blob") else []
        chk(len(strokes) == 2 and all(s.get("anchors") and s.get("reach", 0) > 0 for s in strokes),
            f"the Relief layer has two strokes kept as anchors + reach ({len(strokes)})")
        chk(len(D.history.changes) == n0 + 2, f"two strokes are two undo steps ({n0} -> {len(D.history.changes)})")
        chk(json.dumps(layers(D, "blob")[0].get("strokes", []), sort_keys=True) == stripe_kept, "the stripe is still unchanged")
        QTest.keyClick(win, Qt.Key_B)                                   # Paint off: no cursor disc in the picture
        W.pump(2, lambda: not v.paint.on, "Paint off")
        final_look(win, v, "5-relief-final", "with Relief")
        quick_again(win, v)
    except Exception as e:  # noqa: BLE001  a crash is a failed walk, said with its reason
        W.FAILS.append(f"the walk stopped: {type(e).__name__}: {e}")
    finally:
        REPORT["fails"] = W.FAILS
        (OUT / "clay_paint_walk.json").write_text(json.dumps(REPORT, indent=1), encoding="utf-8")
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
