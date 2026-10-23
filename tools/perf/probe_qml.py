"""What each window part costs to build (H65): 2D's real window is built, then each QML file is built once more on
its own in the same engine (context and cache warm) and timed, median of 3. Parts that refer to their parent's ids
warn and cost a little less than in place; the order is what matters.

    python tools/perf/probe_qml.py [name ...]      # default: every kit and 2D file
"""
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import measure_2d  # noqa: E402  (offscreen, this checkout)
from PySide6.QtCore import QUrl  # noqa: E402
from PySide6.QtQml import QQmlComponent  # noqa: E402

ROOT = measure_2d.ROOT
rig = measure_2d.Rig()
eng = rig.session.engine
files = sorted((ROOT / "shared/gui-kit/qml/RostrumKit").glob("*.qml")) + sorted((ROOT / "apps/2d/screen/qml").glob("*.qml"))
want = set(sys.argv[1:])
rows = []
import os  # noqa: E402
os.dup2(os.open(os.devnull, os.O_WRONLY), 2)           # the parts' own warnings (ids of their parent) are noise here
for f in files:
    if (want and f.stem not in want) or f.stem in ("Main", "AppShell"):
        continue
    ms = []
    for _ in range(3):
        t = time.perf_counter()
        c = QQmlComponent(eng, QUrl.fromLocalFile(str(f)))
        o = c.create(eng.rootContext())
        ms.append((time.perf_counter() - t) * 1000)
        if o is not None:
            o.deleteLater()
        rig.events()
    rows.append((statistics.median(ms), f.stem))
for ms, name in sorted(rows, reverse=True)[:30]:
    print(f"{ms:8.1f} ms  {name}", flush=True)
rig.close()
