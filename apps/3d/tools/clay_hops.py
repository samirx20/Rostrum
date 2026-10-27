# Clay hops (CL2b, 3d-v4): where one dab's time goes in the real window, hop by hop, for Add, Pull and Smooth.
# A scratch project with the sample scene in a fresh background window; Q and a Lump click (real input) make a clay;
# then, per brush, real drags at a steady 60 moves a second across the clay: SHORT strokes of 40 moves (so the first dab
# of a stroke, the start-of-stroke spike, has several samples) and one long stroke of MOVES. Every dab request is one
# record (screen3d/dab_trace.py): move -> sent -> engine thread -> engine (dab, Storm draw, finishing) -> picture
# copy -> GUI told -> first frame shown. With ROSTRUM3D_PERF=1 the engine adds Storm's own counters per picture.
# Python's garbage collections are logged too, to explain spikes. The GUI thread's processor time over each stroke's
# moves is read with clay_walk.gui_cycles_ms (the same cycle-count helper as sound-fix-r9's drive.py `_cycles`; that
# file imports the whole Sound app at its top, so it is not imported here).
# GRAINS: one run measures several grains, each in a fresh window and its own subfolder of the out folder:
#   "auto" = the clay as the Lump click makes it (grain follows the camera, ~1 mm in the sample scene); a number is the
#   fixed grain in metres (0.002 = 2 mm). Default "auto,0.002".
#   heavy.ps1 run "sam: clay hops" gpu <venv python> apps\3d\tools\clay_hops.py <out folder> [--grains auto,0.002]
#       [--moves 200] [--short 5] [--short-moves 40] [--brush 0.012]
# Output per grain: <out>\grain-<label>\clay_hops.json (everything), summary.json and summary.md (the table
# "brush | typical | slowest 10 % | first dab (max)", ms, move -> on screen); <out>\summary.md has all grains.
# Typical and slowest 10 % are over every dab request of the brush; "first dab" is the slower of each stroke's first two requests (the press's begin and the dab after it).
import argparse
import json
import os
import shutil
import statistics as st
import sys
import tempfile
import time
from pathlib import Path

os.environ.setdefault("ROSTRUM_BACKGROUND_WINDOWS", "1")
os.environ.setdefault("ROSTRUM3D_PERF", "1")
_ap = argparse.ArgumentParser(description="Where one dab's time goes, per brush, per grain")
_ap.add_argument("out", nargs="?", default=r"C:\Users\Sam\.rostrum\waves\results\3d-v4\clay-hops")
_ap.add_argument("--grains", default="auto,0.002", help="comma list: auto (the camera's grain) or metres, e.g. 0.002")
_ap.add_argument("--moves", type=int, default=200, help="moves of the one long stroke per brush")
_ap.add_argument("--short", type=int, default=5, help="short strokes per brush (their first dabs are the start spike)")
_ap.add_argument("--short-moves", type=int, default=40)
_ap.add_argument("--brush", type=float, default=None, help="brush size in metres, set on the new clay (default: its own)")
ARGS = _ap.parse_args()
OUT, MOVES, BRUSH = Path(ARGS.out), ARGS.moves, ARGS.brush
GRAINS = [None if g.strip() == "auto" else float(g) for g in ARGS.grains.split(",") if g.strip()]
sys.argv = sys.argv[:1]
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
    """A real drag: press, `n` moves at 60 a second in a zigzag across the clay, release. Returns the GUI thread's
    processor time over the moves, summed (ms)."""
    start = QPoint(round(at.x() - radius), round(at.y()))
    QTest.mouseMove(win, start)
    W.pump(0.3)
    QTest.mousePress(win, Qt.LeftButton, Qt.NoModifier, start)
    W.pump(3, lambda: True)
    t = time.perf_counter()
    p, cpu = start, 0.0
    for i in range(n):
        k = i % 48
        u = k / 24 if k < 24 else 2 - k / 24                          # back and forth
        p = QPoint(round(at.x() - radius + 2 * radius * u), round(at.y() + 0.3 * radius * ((i // 48) % 3 - 1)))
        c0 = W.gui_cycles_ms()
        QTest.mouseMove(win, p)
        cpu += W.gui_cycles_ms() - c0
        t += 1 / 60
        W.pump(max(0.0, t - time.perf_counter()))
    QTest.mouseRelease(win, Qt.LeftButton, Qt.NoModifier, p)
    W.pump(5, lambda: False)
    return cpu


def total(r):
    return r["tSwap"] - r["tMove"] if "tSwap" in r and "tMove" in r else None


def summarise(recs_all, firsts):
    """Move -> on screen over every request of the brush (typical = median, slowest 10 % = p90), and the first dab of
    each stroke on its own."""
    rest = stats([total(r) for r in recs_all])
    f = stats(firsts)
    return {"typical": rest and rest["median"], "slowest10": rest and rest["p90"], "worst": rest and rest["max"],
            "firstMedian": f and f["median"], "firstMax": f and f["max"], "requests": len(recs_all),
            "strokes": len(firsts), "firsts": [round(x, 1) for x in firsts]}


def markdown(title, summary):
    fmt = lambda x: "-" if x is None else f"{x:.1f}"  # noqa: E731
    lines = [f"### {title}", "", "| brush | typical | slowest 10 % | first dab (max) |", "|---|---|---|---|"]
    for brush, s in summary.items():
        lines.append(f"| {brush} | {fmt(s['typical'])} | {fmt(s['slowest10'])} | {fmt(s['firstMax'])} |")
    return "\n".join(lines) + "\n"


def run_grain(label, grain):
    """One fresh window and clay at `grain` (None: the camera's own); every brush; numbers in OUT/grain-<label>."""
    out = OUT / f"grain-{label}"
    out.mkdir(parents=True, exist_ok=True)
    project = Path(tempfile.mkdtemp(prefix="rostrum-clayhops-"))
    doc = Document.new(KIND, folder=project, item="scene")
    doc.run_script("sample.py", run_source(W.SOURCE, "sample.py"))
    doc.save()
    screen = W.app3d.Screen(W.SIZE)
    report = {"moves": MOVES, "short": [ARGS.short, ARGS.short_moves], "grain": grain, "brush": BRUSH, "brushes": {}}
    summary = {}
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
        if grain or BRUSH:
            args = {"detailMode": "fixed", "detail": grain} if grain else {}
            args.update({"brushSize": BRUSH} if BRUSH else {})
            screen.bridge._apply([{"op": "clay.set", "target": [clay], "args": args}], "Grain and brush for the hops")
            W.pump(30, lambda: False)                                   # the clay rebuilt at its grain
        from rostrum3d import clay_detail                       # the grain the core really builds at
        it = screen.bridge.doc.item(clay)
        report.update(detail=clay_detail.detail(screen.bridge.doc.data, it, project), brushSize=it.get("brushSize"))
        print(f"[{label}] clay {clay}: grain {report['detail'] * 1000:.2f} mm, brush {report['brushSize'] * 1000:.1f} mm")
        at, radius = W.clay_on_screen(screen, clay, vp)
        win.frameSwapped.connect(lambda: dab_trace.swapped(v.serial))
        for brush in ("Add", "Pull", "Smooth"):
            W.click(win, W.find(win.contentItem(), "clayBrush" + brush))
            W.pump(0.5)
            recs_all, firsts, gcs, strokes, slow = [], [], [], [], []
            for k, n in enumerate([ARGS.short_moves] * ARGS.short + [MOVES]):
                spot = QPointF(at.x(), at.y() + 0.25 * radius * ((k % 5) - 2))     # each stroke starts somewhere new
                dab_trace.start()
                cpu = drag(win, spot, radius, n)
                recs = dab_trace.stop()
                gc = list(dab_trace.GCS)
                done = [r for r in recs if "tSwap" in r]
                # the start of the stroke: the press's request (begin) and the first dab after it, the slower one
                first = max(total(r) for r in done[:2]) if done else None
                if first is not None:
                    firsts.append(first)
                strokes.append({"moves": n, "requests": len(recs), "firstDabMs": first and round(first, 1),
                                "guiCpuMsPerMove": round(cpu / n, 2), "hops": table(recs)})
                for r in sorted(done, key=lambda r: r["tMove"] - r["tSwap"])[:3]:
                    r["gcDuring"] = [g for g in gc if r["tMove"] <= g["t"] <= r["tSwap"]]
                    slow.append(r)
                recs_all += recs
                gcs += gc
                W.pump(1.0)
            slow.sort(key=lambda r: r["tMove"] - r["tSwap"])
            summary[brush] = summarise(recs_all, firsts)
            report["brushes"][brush] = {"requests": len(recs_all), "hops": table(recs_all), "strokes": strokes,
                                        "gc": gcs, "slowest": slow[:6], "summary": summary[brush]}
        win.grabWindow().save(str(out / "clay-hops-after.png"))
    finally:
        (out / "clay_hops.json").write_text(json.dumps(report, indent=1), encoding="utf-8")
        screen.close()
        W.pump(1.0)
        shutil.rmtree(project, ignore_errors=True)
    mm = f" ({report['detail'] * 1000:.2f} mm)" if report.get("detail") else ""
    title = f"Grain {label}{mm}"
    (out / "summary.json").write_text(json.dumps({"grain": label, "detail": report.get("detail"), "brushes": summary},
                                                 indent=1), encoding="utf-8")
    (out / "summary.md").write_text(markdown(title, summary), encoding="utf-8")
    for brush, b in report["brushes"].items():
        print(f"== [{label}] {brush}: {b['requests']} requests; GCs {len(b['gc'])} "
              f"(longest {max([g['ms'] for g in b['gc']] or [0]):.1f} ms)")
        for name, s in b["hops"].items():
            print(f"  {name:32s} " + ("-" if s is None else f"median {s['median']:6.1f}  p90 {s['p90']:6.1f}  max {s['max']:6.1f}"))
    return title, summary


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    app = W.qt_app()
    parts = []
    for grain in GRAINS:
        label = "auto" if grain is None else f"{grain * 1000:g}mm"
        parts.append(markdown(*run_grain(label, grain)))
        (OUT / "summary.md").write_text("\n".join(parts), encoding="utf-8")        # after each grain: a crash keeps them
    print("\n" + "\n".join(parts))
    app.quit()


if __name__ == "__main__":
    main()
