"""The GUI kit demo: the app shell on rostrum_core.toy.sample(). Clicks are operations; Ctrl+Z undoes.

    python demo/main.py                                         # the window
    python demo/main.py --step "select cam_1" --step "set dof true" --shot out.png
    python demo/main.py --sheet --shot controls.png             # every control, in its states
Steps go through the same bridge calls a click makes:
    select <id> | set <param> <json value> | scrub <param> <v> <v> … | undo | redo | more
    commands [query …] (opens Ctrl+K with that text) | run <command key>
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

HERE = Path(__file__).resolve().parent


def value(text):
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return text            # a bare word is a string: set lightType Spot


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


def main():
    a = argparse.ArgumentParser()
    a.add_argument("--step", action="append", default=[])
    a.add_argument("--shot")
    a.add_argument("--sheet", action="store_true")
    a.add_argument("--hover", default="hovered", help="--sheet: the control to rest the pointer on")
    args = a.parse_args()

    doc = toy.sample()
    bridge = DocBridge(doc)
    qml = HERE / "qml" / ("ControlsSheet.qml" if args.sheet else "Main.qml")
    size = (1040, 860) if args.sheet else (1600, 960)
    app, engine, win = start(qml, {"backend": bridge}, size)
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
