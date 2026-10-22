"""The GUI kit demo: the app shell on rostrum_core.toy.sample(). Clicks are operations; Ctrl+Z undoes.

    python demo/main.py                                         # the window
    python demo/main.py --step "select cam_1" --step "set dof true" --shot out.png
    python demo/main.py --sheet --shot controls.png             # every control, in its states
Steps go through the same bridge calls a click makes:
    select <id> | set <param> <json value> | scrub <param> <v> <v> … | undo | redo | more
    commands [query …] (opens Ctrl+K with that text) | run <command key>
    and the layout check's kit steps (layout_run.kit_step): say <words> | agent-run <n> | agent-say <words> | history open
    undo-run (Undo all on that run) | version <name>; --size 1280x720 sets the window size.
With --shot the window quits by itself; a failed step or save exits nonzero.
"""
import argparse
import json
import sys
from pathlib import Path

from PySide6.QtCore import Q_ARG, QMetaObject, QObject, QPoint, QPointF, QTimer
from PySide6.QtTest import QTest

from rostrum_core import toy
from rostrum_gui import DocBridge, start
from rostrum_gui.layout_run import kit_step

HERE = Path(__file__).resolve().parent


def value(text):
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return text            # a bare word is a string: set lightType Spot


class DemoBridge(DocBridge):
    def agent_demo_calls(self, n):
        """The layout check's `agent-run n`: n harmless moves of the card."""
        return [[{"op": "layer.move", "target": ["card"], "args": {"x": 100 + 10 * i}}] for i in range(n)]


def do_step(bridge, win, step):
    word, *rest = step.split()
    if word == "select":
        bridge.select(rest[0])
    elif word == "set":
        bridge.setValue(rest[0], value(" ".join(rest[1:])))
    elif word == "scrub":
        bridge.beginScrub(rest[0])
        for v in rest[1:]:
            bridge.scrub(rest[0], value(v))
        bridge.endScrub()
    elif word in ("undo", "redo"):
        getattr(bridge, word)()
    elif word == "more":
        bridge.toggleMore()
    elif word == "commands":
        QMetaObject.invokeMethod(win, "openCommands", Q_ARG("QVariant", " ".join(rest)))
    elif word == "run":
        bridge.run(rest[0])
    elif word == "undo-run":                  # Undo all on the agent run the kit steps made
        bridge.undoRun("layout-check")
    elif word == "version":
        bridge.saveVersion(" ".join(rest))
    elif kit_step(bridge, step):
        pass
    else:
        raise ValueError(f"unknown step {step!r}")
    if bridge.status.startswith("Error"):
        raise RuntimeError(f"step {step!r}: {bridge.status}")


def stage_sheet(win, hover="hovered"):
    """Put the sheet's marked controls in their states: focused, list open, hovered."""
    def find(name):
        obj = win.findChild(QObject, name)
        if obj is None:
            raise RuntimeError(f"controls sheet: no control named {name!r}")
        return obj
    QMetaObject.invokeMethod(win, "stage")
    h = find(hover)
    p = h.mapToScene(QPointF(h.width() * 0.6, h.height() / 2))
    for dx in (-6, 0):     # two moves: hover needs a move, not just a position
        QTest.mouseMove(win, QPoint(int(p.x()) + dx, int(p.y())))
    print("hovered:", h.property("hovered"))


def demo_guides():
    """The guides drawer's list in the demo: Rostrum2D's guides (any real guides would do)."""
    from rostrum_gui.guides import entries
    folder = HERE.parents[2] / "apps" / "2d" / "guides"
    pages = sorted(folder.glob("*.md"))
    return entries(folder, [(p.name, p.read_text(encoding="utf-8").splitlines()[0].lstrip("# ").strip())
                            for p in pages if p.name != "README.md"])


def main():
    a = argparse.ArgumentParser()
    a.add_argument("--step", action="append", default=[])
    a.add_argument("--shot")
    a.add_argument("--sheet", action="store_true")
    a.add_argument("--size", help="window size, e.g. 1280x720")
    a.add_argument("--hover", default="hovered", help="--sheet: the control to rest the pointer on")
    args = a.parse_args()

    doc = toy.sample()
    bridge = DemoBridge(doc)
    qml = HERE / "qml" / ("ControlsSheet.qml" if args.sheet else "Main.qml")
    size = (1040, 860) if args.sheet else (1600, 960)
    if args.size:
        size = tuple(int(v) for v in args.size.split("x"))
    app, engine, win = start(qml, {"backend": bridge, "guides": demo_guides()}, size)
    code = [0]

    def guarded(fn):
        try:
            fn()
        except Exception as e:  # noqa: BLE001  fail loudly, whatever it was
            print(f"FAIL: {e}", file=sys.stderr)
            code[0] = 3
            app.exit(3)

    def run_steps():
        if args.sheet:
            stage_sheet(win, args.hover)
        for s in args.step:
            do_step(bridge, win, s)
        if args.shot:
            QTimer.singleShot(700, lambda: guarded(shoot))   # let the 160 ms reveals and popups finish

    def shoot():
        img = win.grabWindow()
        if img.isNull() or not img.save(args.shot):
            raise RuntimeError(f"could not save {args.shot}")
        print(f"saved {args.shot} {img.width()}x{img.height()}  history={bridge.historyCount}  shown={bridge.shown()}")
        app.quit()

    QTimer.singleShot(400, lambda: guarded(run_steps))
    if args.shot:
        QTimer.singleShot(30000, lambda: (print("FAIL: timeout", file=sys.stderr), app.exit(4)))
    app.exec()
    del engine
    sys.exit(code[0])


if __name__ == "__main__":
    main()
