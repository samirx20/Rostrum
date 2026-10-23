"""Look harness and layout check for the kit's ToolRail, filled with a small 3D-style list (what Rostrum3D will give it).

    python shared/gui-kit/demo/rail_preview.py [out folder]        # every state at the four sizes: <out>/*.png,
                                                                   # faults.txt; nonzero exit on any fault
States: rail (the plain rail), add-flyout (a group's flyout, a long name in it), after-pick (a flyout entry chosen: the
group's icon is that tool), render-flyout (acts, not tools), panel (a group that opens the app's own panel).
Steps: click <objectName> (rail_add, fly_sphere, …). Each state runs in its own process (run_states).
"""
import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from PySide6.QtCore import Qt, QTimer  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402

from panel_preview import at  # noqa: E402
from rostrum_gui import layout_run, start  # noqa: E402
from rostrum_gui.app import offscreen_env  # noqa: E402

HERE = Path(__file__).resolve().parent
OUT = r"C:\Users\Sam\.rostrum\waves\results\kit\k1\rail"
STATES = [
    ("rail", [], []),
    ("add-flyout", [], ["click rail_add"]),
    ("after-pick", [], ["click rail_add", "click fly_sphere"]),
    ("render-flyout", [], ["click rail_render"]),
    ("panel", [], ["click rail_paint"]),
]


def run_states(out: Path) -> int:
    """Each state in its own process (the sweep leaves a window used up); the faults of all of them, one list."""
    out.mkdir(parents=True, exist_ok=True)
    (out / "faults.json").unlink(missing_ok=True)
    env = {**offscreen_env(), **os.environ}
    bad = 0
    for name, _, steps in STATES:
        cmd = [sys.executable, __file__, "--check-layout", str(out), "--check-name", name]
        for s in steps:
            cmd += ["--step", s]
        r = subprocess.run(cmd, env=env, capture_output=True, text=True)
        if r.returncode not in (0, 5):
            print(f"FAIL: {name} did not run (exit {r.returncode}): {r.stderr[-600:]}", file=sys.stderr)
            bad += 1
    data = json.loads((out / "faults.json").read_text(encoding="utf-8")) if (out / "faults.json").is_file() else {}
    lines = [f"{n} {size}: {line}" for n, sizes in data.items() for size, ls in sizes.items() for line in ls]
    (out / "faults.txt").write_text(chr(10).join(lines) + chr(10), encoding="utf-8")
    print(f"rail check: {len(STATES)} states, {len(lines)} fault(s), {bad} failed -> {out / 'faults.txt'}")
    return 0 if not lines and not bad else 5


def main():
    a = argparse.ArgumentParser()
    a.add_argument("out", nargs="?", default=OUT)
    a.add_argument("--step", action="append", default=[])
    a.add_argument("--check-layout")
    a.add_argument("--check-name")
    args = a.parse_args()
    if not args.check_name:
        sys.exit(run_states(Path(args.check_layout or args.out)))

    app, engine, win = start(HERE / "qml" / "RailPreview.qml", {}, layout_run.SIZES[0])

    def run():
        try:
            for s in args.step:
                word, name = s.split()
                if word != "click":
                    raise SystemExit(f"unknown step {s!r}")
                QTest.mouseClick(win, Qt.LeftButton, Qt.NoModifier, at(win, name))
                QTest.qWait(200)
        except Exception as e:  # noqa: BLE001  a step that fails fails the state, loudly
            print(f"FAIL: {e}", file=sys.stderr)
            return app.exit(3)
        QTimer.singleShot(400, lambda: layout_run.sweep(app, win, args.check_layout, args.check_name, lambda: True))
    QTimer.singleShot(500, run)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
