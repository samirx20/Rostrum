"""Look harness and layout check for the S36 panel pieces (Effects row, right-click Reset, Popover), long texts included.

    python shared/gui-kit/demo/panel_preview.py [out folder]        # every state at the four sizes: <out>/*.png,
                                                                    # faults.txt; nonzero exit on any fault
States: rows (the card's settings and "Effects (2) +", effects folded), effect-open (one effect's settings),
add-menu (the + list), reset (right-click on a changed field), none (a layer without effects: only the +),
popover (under a button, a long title), popover-edge (at the window's corner: it stays inside).
Steps: select <id> | set <param> <json> | open <effect id> | click <objectName> | rclick <objectName>.
Each state runs in its own process (layout_run.run_all).
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from PySide6.QtCore import QPoint, QPointF, Qt, QTimer  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402

import effects_demo  # noqa: E402
from rostrum_gui import DocBridge, effects, layout_run, start  # noqa: E402

HERE = Path(__file__).resolve().parent
OUT = r"C:\Users\Sam\.rostrum\waves\results\kit\s36\panel"
STATES = [
    ("rows", [], []),
    ("effect-open", [], ["open blur_1", "open glow_1"]),
    ("add-menu", [], ["click addEffect"]),
    ("reset", [], ["set radius 40", "rclick row:radius"]),
    ("none", [], ["select plain"]),
    ("popover", [], ["click underButton"]),
    ("popover-edge", [], ["click edgeButton"]),
]


def find(item, name):
    """The first item in the visual tree with this objectName (a Repeater's rows are not QObject children)."""
    if item.objectName() == name:
        return item
    return next(filter(None, (find(c, name) for c in item.childItems())), None)


def at(win, name, dx=None):
    obj = find(win.contentItem(), name)
    if obj is None:
        raise RuntimeError(f"no control named {name!r}")
    p = obj.mapToScene(QPointF(obj.width() / 2 if dx is None else dx, obj.height() / 2))
    return QPoint(int(p.x()), int(p.y()))


def do(bridge, part, win, step):
    word, *rest = step.split()
    if word == "select":
        bridge.select(rest[0])
    elif word == "set":
        bridge.setValue(rest[0], json.loads(" ".join(rest[1:])))
    elif word == "open":
        next(g for g in part.groups if g.id == rest[0]).toggle()
    elif word == "click":
        QTest.mouseClick(win, Qt.LeftButton, Qt.NoModifier, at(win, rest[0]))
    elif word == "rclick":
        QTest.mouseClick(win, Qt.RightButton, Qt.NoModifier, at(win, rest[0], 40))
    else:
        raise SystemExit(f"unknown step {step!r}")


def main():
    a = argparse.ArgumentParser()
    a.add_argument("out", nargs="?", default=OUT)
    a.add_argument("--step", action="append", default=[])
    a.add_argument("--check-layout")
    a.add_argument("--check-name")
    args = a.parse_args()
    if not args.check_name:
        sys.exit(layout_run.run_all(Path(__file__), STATES, args.check_layout or args.out))

    bridge = DocBridge(effects_demo.sample())
    bridge.select("card")
    part = effects.attach(bridge, effects_demo.SPEC)
    app, engine, win = start(HERE / "qml" / "PanelPreview.qml", {"backend": bridge}, layout_run.SIZES[0])

    def run():
        try:
            for s in args.step:
                do(bridge, part, win, s)
            if bridge.status.startswith("Error"):
                raise RuntimeError(bridge.status)
        except Exception as e:  # noqa: BLE001  a step that fails fails the state, loudly
            print(f"FAIL: {e}", file=sys.stderr)
            return app.exit(3)
        QTimer.singleShot(400, lambda: layout_run.sweep(app, win, args.check_layout, args.check_name, lambda: True))
    QTimer.singleShot(500, run)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
