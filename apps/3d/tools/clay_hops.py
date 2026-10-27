# Clay hops (CL2b): where one dab's time goes in the real window, hop by hop, for Add, Pull and Smooth.
# A scratch project with the sample scene in a fresh background window; Q and a Lump click (real input) make a clay;
# then, per brush, a real drag of 200 pointer moves at a steady 60 a second across the clay. Every dab request is one
# record (screen3d/dab_trace.py): move -> sent -> engine thread -> engine (dab, Storm draw, finishing) -> picture
# copy -> GUI told -> first frame shown. With ROSTRUM3D_PERF=1 the engine adds Storm's own counters per picture.
# Python's garbage collections are logged too, to explain spikes.
#   heavy.ps1 run "priyam: clay hops" gpu <venv python> apps\3d\tools\clay_hops.py <out folder> [moves]
import json
import os
import statistics as st
import sys
import tempfile
import time
from pathlib import Path

os.environ.setdefault("ROSTRUM_BACKGROUND_WINDOWS", "1")
os.environ.setdefault("ROSTRUM3D_PERF", "1")
OUT = Path(sys.argv[1] if len(sys.argv) > 1 else r"C:\Users\Sam\.rostrum\waves\results\3d-cl2b")
MOVES = int(sys.argv[2]) if len(sys.argv) > 2 else 200
# (3d-v2) [grain m] [brush m] after the moves: set on the new clay by its own operation before the drags, e.g.
# 0.000625 0.012 is the proof's fine-grain case (a 12 mm brush at 0.625 mm)
GRAIN = float(sys.argv[3]) if len(sys.argv) > 3 else None
BRUSH = float(sys.argv[4]) if len(sys.argv) > 4 else None
sys.argv = sys.argv[:2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
import clay_walk as W  # noqa: E402  (the walk's helpers: app, pump, find, click, clay_on_screen)

from PySide6.QtCore import QPoint, QPointF, Qt  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from rostrum_core import Document  # noqa: E402
from rostrum3d import KIND  # noqa: E402
from rostrum3d.script import run_source  # noqa: E402
from screen3d import dab_trace  # noqa: E402

HOPS = [("before send", "tMove", "tSend"), ("wait for engine thread", "tSend", "tJob"),
        ("engine round trip", "tEng0", "tEng1"), ("  in window: to render thread", "tEng0", "tRender0"),
        ("  in window: dab + draw", "tRender0", "tRender1"), ("  in window: drawn -> on screen", "tRender1", "tSwap"),
        ("picture copy", "tCopy0", "tCopy1"),
        ("to GUI thread", "tCopy1", "tReady"), ("to screen", "tReady", "tSwap"), ("TOTAL move -> on screen", "tMove", "tSwap")]


def stats(xs):
    xs = sorted(x for x in xs if x is not None)
    if not xs:
        return None
    return {"median": round(st.median(xs), 1), "p90": round(xs[int(0.9 * (len(xs) - 1))], 1), "max": round(xs[-1], 1),
            "n": len(xs)}


def table(recs):
    rows = {name: stats([r[b] - r[a] for r in recs if a in r and b in r]) for name, a, b in HOPS}
    rows["  engine: dab"] = stats([r.get("dabMs") for r in recs])
    rows["    dab: apply the dabs"] = stats([r.get("applyMs") for r in recs])
    rows["    dab: mesh changed blocks"] = stats([r.get("meshMs") for r in recs])
    rows["    dab: write blocks to USD"] = stats([r.get("usdMs") for r in recs])
    rows["    dab: blocks changed"] = stats([r.get("blocks") for r in recs])
    rows["    dab: new dabs"] = stats([b.get("dabs", 0) - a.get("dabs", 0) for a, b in zip(recs, recs[1:])])
    rows["  engine: Storm draw (+mask)"] = stats([r.get("drawMs") for r in recs])
    rows["    draw: lights set up"] = stats([r.get("lightMs") for r in recs])
    rows["    draw: Storm render + GPU finish"] = stats([r.get("stormMs") for r in recs])
    rows["  engine: finishing + read back"] = stats([r["totalMs"] - r["drawMs"] for r in recs if r.get("totalMs") is not None])
    rows["  engine: pipe + JSON"] = stats([(r["tEng1"] - r["tEng0"]) - r["totalMs"] - (r.get("dabMs") or 0)
                                          for r in recs if r.get("totalMs") is not None and "tEng1" in r])
    return rows


def drag(win, at, radius, n):
    """A real drag: press, `n` moves at 60 a second in a zigzag across the clay, release."""
    start = QPoint(round(at.x() - radius), round(at.y()))
    QTest.mouseMove(win, start)
    W.pump(0.3)
    QTest.mousePress(win, Qt.LeftButton, Qt.NoModifier, start)
    W.pump(3, lambda: True)
    t = time.perf_counter()
    p = start
    for i in range(n):
        k = i % 48
        u = k / 24 if k < 24 else 2 - k / 24                          # back and forth
        p = QPoint(round(at.x() - radius + 2 * radius * u), round(at.y() + 0.3 * radius * ((i // 48) % 3 - 1)))
        QTest.mouseMove(win, p)
        t += 1 / 60
        W.pump(max(0.0, t - time.perf_counter()))
    QTest.mouseRelease(win, Qt.LeftButton, Qt.NoModifier, p)
    W.pump(5, lambda: False)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    project = Path(tempfile.mkdtemp(prefix="rostrum-clayhops-"))
    app = W.qt_app()
    doc = Document.new(KIND, folder=project, item="scene")
    doc.run_script("sample.py", run_source(W.SOURCE, "sample.py"))
    doc.save()
    screen = W.app3d.Screen(W.SIZE)
    report = {"moves": MOVES, "brushes": {}}
    try:
        screen.show(doc, autosave=True)
        win, v = screen.win, screen.bridge.viewport
        W.pump(60, screen.ready, "the first picture")
        vp = W.find(win.contentItem(), "viewport3d")
        QTest.keyClick(win, Qt.Key_Q)
        W.pump(0.5)
        ground = vp.mapToScene(QPointF(vp.width() * 0.5, vp.height() * 0.85)).toPoint()
        QTest.mouseMove(win, ground)
        QTest.mouseClick(win, Qt.LeftButton, Qt.NoModifier, ground)
        W.pump(20, lambda: v.clay.clayId != "", "the new clay")
        W.pump(3)
        clay = v.clay.clayId
        if GRAIN or BRUSH:
            args = {"detailMode": "fixed", "detail": GRAIN} if GRAIN else {}
            args.update({"brushSize": BRUSH} if BRUSH else {})
            screen.bridge._apply([{"op": "clay.set", "target": [clay], "args": args}], "Grain and brush for the hops")
            W.pump(30, lambda: False)                                   # the clay rebuilt at its grain
        report.update(grain=GRAIN, brush=BRUSH)
        at, radius = W.clay_on_screen(screen, clay, vp)
        win.frameSwapped.connect(lambda: dab_trace.swapped(v.serial))
        for brush in ("Add", "Pull", "Smooth"):
            tile = W.find(win.contentItem(), "clayBrush" + brush)
            W.click(win, tile)
            W.pump(0.5)
            dab_trace.start()
            drag(win, at, radius, MOVES)
            recs = dab_trace.stop()
            gcs = list(dab_trace.GCS)
            slow = sorted((r for r in recs if "tSwap" in r), key=lambda r: r["tMove"] - r["tSwap"])[:6]
            for r in slow:
                r["gcDuring"] = [g for g in gcs if r["tMove"] <= g["t"] <= r["tSwap"]]
            report["brushes"][brush] = {"requests": len(recs), "hops": table(recs), "gc": gcs, "slowest": slow}
            W.pump(1.0)
        win.grabWindow().save(str(OUT / "clay-hops-after.png"))
    finally:
        (OUT / "clay_hops.json").write_text(json.dumps(report, indent=1), encoding="utf-8")
        screen.close()
        W.pump(1.0)
    for brush, b in report["brushes"].items():
        print(f"== {brush}: {b['requests']} requests for {MOVES} moves; GCs {len(b['gc'])} "
              f"(longest {max([g['ms'] for g in b['gc']] or [0]):.1f} ms)")
        for name, s in b["hops"].items():
            print(f"  {name:32s} " + ("-" if s is None else f"median {s['median']:6.1f}  p90 {s['p90']:6.1f}  max {s['max']:6.1f}"))
    app.quit()


if __name__ == "__main__":
    main()
