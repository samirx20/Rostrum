# View walk (3d-v1): the live view drawn inside the window, by real input, on a 300-object scene. A scratch project
# (the sample scene plus 300 small boxes) in a fresh background window; then, with QTest's real mouse and keys:
# a click picks the ball, a left drag on empty space orbits (120 moves at 60 a second), the ball's move arrow is
# dragged (60 moves), a right-click opens the item's menu and the Materials list opens over the view, and Shift+F shows
# the Final look (the engine program's progressive Cycles picture) and back.
# Each move's time to the screen: the move -> the frame that drew a view asked for after it -> that frame's swap
# (the window's own frame counters: ViewLink.drawn / .shown, steady clock = time.perf_counter on Windows).
#   heavy.ps1 run "priyam: view walk" gpu <venv python> apps\3d\tools\view_walk.py <out folder>
import json
import os
import statistics as st
import sys
import tempfile
import time
from pathlib import Path

os.environ.setdefault("ROSTRUM_BACKGROUND_WINDOWS", "1")
OUT = Path(sys.argv[1] if len(sys.argv) > 1 else r"C:\Users\Sam\.rostrum\waves\results\3d-v1\view-walk")
sys.argv = sys.argv[:2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
import clay_walk as W  # noqa: E402  (the walk's helpers: app, pump, find, check)

from PySide6.QtCore import QPoint, QPointF, Qt  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from rostrum_core import Document  # noqa: E402
from rostrum3d import KIND  # noqa: E402
from rostrum3d.script import run_source  # noqa: E402

BOXES = '''
for i in range(300):
    mesh(f"b{i}", shape="box", width=0.04, height=0.04, depth=0.04, x=-1.5 + (i % 20) * 0.15,
         y=0.02, z=-1.6 + (i // 20) * 0.1, material=clay)
'''


def now():
    return time.perf_counter() * 1000


class Frames:
    """The window's view: when each view was asked for, which frame drew it, when that frame was on screen."""

    def __init__(self, link):
        self.asks, self.drawn, self.shown = [], [], {}
        show = link.show

        def timed(req):
            self.asks.append(now())
            show(req)
        link.show = timed
        link.drawn.connect(lambda r: self.drawn.append(r))
        link.shown.connect(lambda f, t: self.shown.__setitem__(f, t))

    def latency(self, moves):
        """Per move: ms from the move to the swap of the first frame drawing a view asked for after it."""
        out = []
        for tm in moves:
            asked = [t for t in self.asks if t >= tm]
            if not asked:
                continue
            ta = asked[0]
            for r in self.drawn:
                if r.get("tRender0", 0) >= ta and r.get("frame") in self.shown:
                    out.append(self.shown[r["frame"]] - tm)
                    break
        return out


def stats(xs):
    xs = sorted(xs)
    if not xs:
        return None
    return {"median": round(st.median(xs), 1), "p90": round(xs[int(0.9 * (len(xs) - 1))], 1),
            "max": round(xs[-1], 1), "n": len(xs)}


GUI = []


def all_items(item):
    yield item
    for c in item.childItems():
        yield from all_items(c)


def drag(win, a, b, n, button=Qt.LeftButton):
    QTest.mouseMove(win, a)
    W.pump(0.3)
    QTest.mousePress(win, button, Qt.NoModifier, a)
    W.pump(0.1)
    moves, t = [], time.perf_counter()
    GUI.clear()
    for i in range(1, n + 1):
        p = QPoint(round(a.x() + (b.x() - a.x()) * i / n), round(a.y() + (b.y() - a.y()) * i / n))
        moves.append(now())
        QTest.mouseMove(win, p)
        GUI.append(now() - moves[-1])                     # the move's own work on the GUI thread
        t += 1 / 60
        W.pump(max(0.0, t - time.perf_counter()))
    QTest.mouseRelease(win, button, Qt.NoModifier, p)
    W.pump(1.0)
    return moves


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    project = Path(tempfile.mkdtemp(prefix="rostrum-viewwalk-"))
    app = W.qt_app()
    doc = Document.new(KIND, folder=project, item="scene")
    doc.run_script("sample.py", run_source(W.SOURCE + BOXES, "sample.py"))
    doc.save()
    screen = W.app3d.Screen(W.SIZE)
    report = {}
    try:
        screen.show(doc, autosave=True)
        win, v = screen.win, screen.bridge.viewport
        W.pump(90, screen.ready, "the first picture")
        W.check(v.inWindow or os.environ.get("ROSTRUM3D_VIEW") == "picture", f"the live view is drawn in the window ({v.link.item.property('glRenderer') if v.link else 'pictures'})")
        fr = Frames(v.link) if v.link is not None else None     # (ROSTRUM3D_VIEW=picture: the checks alone)
        loads, loaded = [], v._r._loaded

        def timed_load(out):                                      # each scene load in the window's view: its ms
            loads.append(out["tRender1"] - out["tRender0"] if isinstance(out, dict) else None)
            loaded(out)
        v._r._loaded = timed_load
        vp = W.find(win.contentItem(), "viewport3d")
        at = lambda fx, fy: vp.mapToScene(QPointF(vp.width() * fx, vp.height() * fy)).toPoint()  # noqa: E731
        win.grabWindow().save(str(OUT / "view-walk-start.png"))

        # pick: a click on empty sky selects nothing, a click on the ball selects it
        scene, cam = v.sent()
        from rostrum3d import aim, through
        from screen3d.gizmo import View
        view = View.of(cam, scene, screen.bridge.frame, cam["width"], cam["height"])
        bx, by, _ = view.project(aim.point(through.find_item(scene, "ball", screen.bridge.frame)[0], [0, 0, 0]))
        ball = at(bx / cam["width"], by / cam["height"])
        QTest.mouseClick(win, Qt.LeftButton, Qt.NoModifier, ball)
        W.pump(10, lambda: screen.bridge.selected == "ball", "the ball picked")
        W.check(screen.bridge.selected == "ball", f"a click on the ball picks it ({screen.bridge.selected!r})")

        # gizmo: drag the ball's first move arrow along itself
        W.pump(5, lambda: bool(v.gizmo.handles), "the gizmo's handles")
        h = next((x for x in v.gizmo.handles if x.get("id") == "move0"), None)
        W.check(h is not None, "the ball shows its move arrows")
        x0 = doc.item("ball").get("x", 0.0)
        a, b = h["a"], h["b"]
        on = [k / 40 for k in range(41) if v.gizmo.hitAt(a[0] + k / 40 * (b[0] - a[0]), a[1] + k / 40 * (b[1] - a[1])) == "move0"]
        W.check(bool(on), f"the move arrow answers the pointer somewhere along it ({len(on)} of 41 points)")
        k = on[len(on) // 2] if on else 0.9
        p0 = at(a[0] + k * (b[0] - a[0]), a[1] + k * (b[1] - a[1]))
        p1 = at(a[0] + (k + 1.0) * (b[0] - a[0]), a[1] + (k + 1.0) * (b[1] - a[1]))
        n_asks, n_drawn = (len(fr.asks), len(fr.drawn)) if fr else (0, 0)
        moves = drag(win, p0, p1, 60)
        if fr:
            # views asked / drawn during the drag (the viewport redraws a gizmo drag only when the pointer rests)
            report["gizmoAsksDrawn"] = [len(fr.asks) - n_asks, len(fr.drawn) - n_drawn]
        W.pump(5, lambda: v._r.idle(), "the gizmo's last picture")
        x1 = screen.bridge.doc.item("ball").get("x", 0.0)
        W.check(abs(x1 - x0) > 1e-3, f"dragging the move arrow moved the ball (x {x0:.3f} -> {x1:.3f})")
        report["gizmo"] = stats(fr.latency(moves)) if fr else None
        report["gizmoGuiMsPerMove"] = stats(GUI)
        report["gizmoSceneLoadMs"] = stats([x for x in loads if x is not None])
        win.grabWindow().save(str(OUT / "view-walk-gizmo.png"))

        # popups over the view: the right-click menu on the ball (picked through the view), the Materials list
        QTest.mouseClick(win, Qt.RightButton, Qt.NoModifier, ball)
        shown = lambda: any(c.property("text") == "Duplicate" and c.isVisible() for c in all_items(win.contentItem()))  # noqa: E731
        W.pump(5, shown, "the right-click menu")
        W.check(shown(), "a right-click on the ball opens its menu over the view")
        win.grabWindow().save(str(OUT / "view-walk-menu.png"))
        QTest.keyClick(win, Qt.Key_Escape)
        W.pump(0.5)
        chip = next((c for c in all_items(win.contentItem()) if c.property("text") == "Materials"), None)
        if chip is not None:
            W.click(win, chip)
            W.pump(1.0)
            win.grabWindow().save(str(OUT / "view-walk-materials.png"))
            QTest.keyClick(win, Qt.Key_Escape)
            W.pump(0.5)
        W.check(chip is not None, "the Materials button is there (its list: view-walk-materials.png)")

        # orbit: a left drag on empty space (Escape first: nothing selected, no gizmo in the way)
        QTest.keyClick(win, Qt.Key_Escape)
        W.pump(0.5)
        moves = drag(win, at(0.12, 0.2), at(0.45, 0.25), 120)
        report["orbit"] = stats(fr.latency(moves)) if fr else None
        report["orbitGuiMsPerMove"] = stats(GUI)
        win.grabWindow().save(str(OUT / "view-walk-orbit.png"))
        draws = [r for r in fr.drawn if r.get("timing")] if fr else []
        report["viewDrawMs"] = stats([r["tRender1"] - r["tRender0"] for r in draws])
        report["stormMs"] = stats([r["timing"].get("stormMs", 0) for r in draws])

        # Final look: the engine program's progressive Cycles picture, then back to the window's own view
        QTest.keyClick(win, Qt.Key_F, Qt.ShiftModifier)
        W.pump(120, lambda: v.final.fraction > 0.05 and v.serial > 0, "the Final look's first samples")
        W.check(v.look == "final" and v.final.fraction > 0, f"Shift+F: the Final look draws ({v.finalLine})")
        win.grabWindow().save(str(OUT / "view-walk-final.png"))
        QTest.keyClick(win, Qt.Key_F, Qt.ShiftModifier)
        n = v.serial
        W.pump(20, lambda: v.serial > n, "the quick look again")
        W.check(v.look == "quick" and v.serial > n, "Shift+F again: back to the quick look")
        win.grabWindow().save(str(OUT / "view-walk-quick-again.png"))
    finally:
        (OUT / "view_walk.json").write_text(json.dumps(report, indent=1), encoding="utf-8")
        screen.close()
        W.pump(1.0)
    print(json.dumps(report, indent=1))
    app.quit()
    sys.exit(1 if W.FAILS else 0)


if __name__ == "__main__":
    main()
