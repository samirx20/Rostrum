"""How fast the shared kit makes each app feel: start, the settings panel, one value change, memory.

    python tools/perf/measure_kit.py imports                   # Python import time of PySide6 / rostrum_core / rostrum_gui
    python tools/perf/measure_kit.py app 2d [--runs 3] [--live] [--profile out.prof]
    python tools/perf/measure_kit.py app sound ...

`app` starts the real window offscreen on the app's --sample document (`--live`: saved in a scratch project folder,
so every change goes to disk the way a person's project does), each run in a fresh process, and prints one line per
measurement: median / worst over runs (and over the repeats inside a run). Interaction times include drawing one
frame (grabWindow), so they are what a person waits for. `--profile` writes cProfile of the value changes.
"""
from __future__ import annotations

import json
import os
import statistics
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REPEAT = 8


def rss_mb() -> float:
    import ctypes
    from ctypes import wintypes

    class PMC(ctypes.Structure):
        _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD)] + [
            (n, ctypes.c_size_t) for n in ("Peak", "WorkingSetSize", "QPPP", "QPP", "QPNPP", "QNPP", "Pagefile", "PeakPagefile")]
    pmc = PMC()
    pmc.cb = ctypes.sizeof(PMC)
    k = ctypes.windll.kernel32
    k.GetCurrentProcess.restype = wintypes.HANDLE
    f = ctypes.windll.psapi.GetProcessMemoryInfo
    f.argtypes = [wintypes.HANDLE, ctypes.POINTER(PMC), wintypes.DWORD]
    f(k.GetCurrentProcess(), ctypes.byref(pmc), pmc.cb)
    return pmc.WorkingSetSize / 2**20


def child(app_name: str, live: bool, profile: str | None):
    t0 = time.perf_counter()
    os.environ.update({"QT_QPA_PLATFORM": "offscreen", "QT_QPA_FONTDIR": "C:/Windows/Fonts", "ROSTRUM_SCRIPTED_HOME": "1"})
    screen = ROOT / "apps" / app_name / "screen"
    sys.path[:0] = [str(screen), str(ROOT)]
    out = {}
    import main as m                                    # the app's own main.py: PySide6, the kit, the app
    out["import_s"] = time.perf_counter() - t0
    from argparse import Namespace
    from rostrum_gui.app import qt_app
    app = qt_app()
    t = time.perf_counter()
    if app_name == "2d":
        host = m.Session((1600, 960), None)
    else:
        host = m.Screen((1600, 960))
        host.unnamed = "Sample song"
    folder = tempfile.mkdtemp(prefix="rostrum-perf-") if live else None
    doc = m.load_doc(Namespace(doc=(folder, "perf") if live else None, script=None, sample=True, path=None))
    out["doc_s"] = time.perf_counter() - t
    t = time.perf_counter()
    host.files.put(doc)                                 # bridge + QML engine load + component compile
    out["window_s"] = time.perf_counter() - t
    t = time.perf_counter()
    host.win.grabWindow()                               # the first frame
    out["first_frame_s"] = time.perf_counter() - t
    out["start_s"] = time.perf_counter() - t0
    for _ in range(50):                                 # idle a moment: lazy loads, timers
        app.processEvents()
        time.sleep(0.01)
    out["rss_mb"] = rss_mb()
    b = host.bridge

    def timed(fn):
        t = time.perf_counter()
        fn()
        py = time.perf_counter() - t
        app.processEvents()
        host.win.grabWindow()
        return py, time.perf_counter() - t

    items = [i["id"] for i in b.items]
    kinds = {}
    for i in b.items:
        kinds.setdefault(i["kind"], []).append(i["id"])
    same = next((v[:2] for v in kinds.values() if len(v) > 1), items[:2])
    other = [items[0], next((i for i in items if b.doc.item(i)["type"] != b.doc.item(items[0])["type"]), items[1])]
    import cProfile
    prof = cProfile.Profile() if profile else None
    if prof:
        prof.enable()
    sel_same = [timed(lambda i=i: b.select(same[i % 2])) for i in range(REPEAT)]
    sel_kind = [timed(lambda i=i: b.select(other[i % 2])) for i in range(REPEAT)]
    if prof:
        prof.disable()
        prof.dump_stats(profile + ".select")
    out["select_same_kind_ms"] = [x[1] * 1000 for x in sel_same]
    out["select_other_kind_ms"] = [x[1] * 1000 for x in sel_kind]
    out["select_py_ms"] = [x[0] * 1000 for x in sel_same + sel_kind]
    num = None
    for sid in items:
        b.select(sid)
        num = next((r for r in b.model.rows if r["row"] == "param" and r["valid"] and r["type"] in ("number", "float", "int")
                    and r["expr"] == "" and isinstance(r["value"], (int, float))), None)
        if num:
            break
    out["value_param"] = f"{b.selected}.{num['id']}"
    base = num["value"]
    step = num["step"] or 1
    lo, hi = num["min"], num["max"]
    vals = [base + step * (1 + i % 2) if hi is None or base + 2 * step <= hi else base - step * (1 + i % 2) for i in range(REPEAT)]
    prof = cProfile.Profile() if profile else None
    if prof:
        prof.enable()
    val = [timed(lambda v=v: b.setValue(num["id"], v)) for v in vals]
    scrub = []
    b.beginScrub(num["id"])
    scrub = [timed(lambda v=v: b.scrub(num["id"], v)) for v in vals]
    b.endScrub()
    if prof:
        prof.disable()
        prof.dump_stats(profile + ".value")
    if b.status.startswith("Error"):
        raise RuntimeError(b.status)
    out["value_ms"] = [x[1] * 1000 for x in val]
    out["value_py_ms"] = [x[0] * 1000 for x in val]
    out["scrub_step_ms"] = [x[1] * 1000 for x in scrub]
    host.close()
    print("RESULT " + json.dumps(out))


def stat(xs):
    return f"{statistics.median(xs):8.1f} / {max(xs):8.1f}"


def parent(app_name: str, runs: int, live: bool, profile: str | None):
    res = []
    for r in range(runs):
        cmd = [sys.executable, __file__, "child", app_name] + (["--live"] if live else []) + (
            ["--profile", profile] if profile and r == 0 else [])
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        line = next((ln for ln in p.stdout.splitlines() if ln.startswith("RESULT ")), None)
        if line is None:
            sys.exit(f"FAIL: run {r}: exit {p.returncode}\n{p.stdout[-2000:]}\n{p.stderr[-4000:]}")
        res.append(json.loads(line[7:]))
    print(f"{app_name}{' live' if live else ''}: {runs} runs; value param {res[0]['value_param']}   (median / worst)")
    for k in ("import_s", "doc_s", "window_s", "first_frame_s", "start_s", "rss_mb"):
        print(f"  {k:22s} {stat([x[k] for x in res])}")
    for k in ("select_same_kind_ms", "select_other_kind_ms", "select_py_ms", "value_ms", "value_py_ms", "scrub_step_ms"):
        print(f"  {k:22s} {stat([v for x in res for v in x[k]])}")


def imports(runs: int):
    mods = ["PySide6.QtQml", "PySide6.QtQuick", "rostrum_core", "rostrum_gui.bridge", "rostrum_gui.app", "rostrum2d",
            "rostrum_sound"]
    env = dict(os.environ, PYTHONPATH=os.pathsep.join(str(ROOT / d) for d in (
        "shared/core", "shared/gui-kit", "shared/painting-kit", "shared/mcp", "apps/2d/python", "apps/sound/python")))
    cum = {m: [] for m in mods}
    for _ in range(runs):
        p = subprocess.run([sys.executable, "-X", "importtime", "-c", "; ".join(f"import {m}" for m in mods)],
                           capture_output=True, text=True, env=env)
        for ln in p.stderr.splitlines():
            parts = [s.strip() for s in ln.split("|")]
            if len(parts) == 3 and parts[2] in cum and parts[1].isdigit():
                cum[parts[2]].append(int(parts[1]) / 1000)
    print("cumulative import ms (first import in the process; later ones share what was loaded)  median / worst")
    for m in mods:
        print(f"  {m:22s} {stat(cum[m]) if cum[m] else '(not top-level)'}")


if __name__ == "__main__":
    a = sys.argv[1:]
    runs = int(a[a.index("--runs") + 1]) if "--runs" in a else 3
    prof = a[a.index("--profile") + 1] if "--profile" in a else None
    if a[0] == "imports":
        imports(runs)
    elif a[0] == "child":
        child(a[1], "--live" in a, prof)
    else:
        parent(a[1], runs, "--live" in a, prof)
