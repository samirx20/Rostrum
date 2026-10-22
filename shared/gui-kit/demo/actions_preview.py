"""Look harness for the kit's ContextBar, ActionMenu and Ctrl+K keys, on a FAKE hub (static data).

    python shared/gui-kit/demo/actions_preview.py [out folder]
Saves five PNGs (bar, bar narrowed, its ⋯ menu, right-click menu, Ctrl+K) and quits by itself.
"""
import os
import sys
from pathlib import Path

from PySide6.QtCore import Property, QMetaObject, QObject, QTimer, Signal, Slot

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from rostrum_gui import start  # noqa: E402

HERE = Path(__file__).resolve().parent
OUT = Path(sys.argv[1] if len(sys.argv) > 1 else r"C:\Users\Sam\.rostrum\waves\results\kit\s31\preview")

EDIT = [("copy", "Copy", "Ctrl C"), ("cut", "Cut", "Ctrl X"), ("paste", "Paste", "Ctrl V"),
        ("dup", "Duplicate", "Ctrl D"), ("rename", "Rename", "F2"), ("delete", "Delete", "Del")]


def e(value, label, keys="", group="do", **kw):
    return {"value": value, "label": label, "keys": keys, "group": group, **kw}


class FakeHub(QObject):
    barChanged = Signal()

    def __init__(self):
        super().__init__()
        self._bar = {
            "what": "3 layers",
            "items": [
                {"id": "group", "label": "Group", "keys": "Ctrl G", "menu": []},
                {"id": "mask", "label": "Mask", "keys": "", "menu": [e("mask.shape", "From shape", "Alt M"), e("mask.luma", "From brightness")]},
                {"id": "align", "label": "Align", "keys": "", "menu": [e("al.l", "Left"), e("al.c", "Centre", "Alt C"), e("al.r", "Right")]},
                {"id": "combine", "label": "Combine shapes", "keys": "Ctrl J", "menu": []},
                {"id": "ease", "label": "Ease", "keys": "", "menu": []},
            ],
            "more": [e("flip", "Flip sideways", "", "more"), e("lock", "Lock position", "Ctrl L", "more")],
        }

    @Property("QVariant", notify=barChanged)
    def bar(self):
        return self._bar

    @Slot(result="QVariant")
    def menu(self):
        return ([e("group", "Group", "Ctrl G"), e("mask", "Mask", "", sub=[e("mask.shape", "From shape", "Alt M"), e("mask.luma", "From brightness")]),
                 e("align", "Align", "", sub=[e("al.l", "Left"), e("al.c", "Centre", "Alt C"), e("al.r", "Right")]),
                 e("combine", "Combine these shapes into one outline with a very long name here", "Ctrl J")]
                + [e(v, l, k, "edit") for v, l, k in EDIT])

    @Slot(str, result="QVariant")
    def commands(self, query):
        rows = [{"key": "group", "label": "Group", "hint": "3 layers", "keys": "Ctrl G"},
                {"key": "mask", "label": "Mask with a shape", "hint": "3 layers", "keys": ""},
                {"key": "safe", "label": "Show safe margins", "hint": "View", "keys": "Ctrl '"},
                {"key": "export", "label": "Export", "hint": "File", "keys": "Ctrl E"}]
        return [r for r in rows if all(w in r["label"].lower() for w in query.lower().split())]

    @Slot(str)
    def run(self, key):
        print("run", key)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    hub = FakeHub()
    app, engine, win = start(HERE / "qml" / "ActionsPreview.qml", {"fakeHub": hub}, (1280, 720))
    shots = [("bar", lambda: None), ("bar-narrow", lambda: win.setProperty("barMax", 330)),
             ("bar-more", lambda: QMetaObject.invokeMethod(win, "showMore")),
             ("menu", lambda: (QMetaObject.invokeMethod(win, "closeAll"), win.setProperty("barMax", 10000), QMetaObject.invokeMethod(win, "showMenu"))),
             ("commands", lambda: (QMetaObject.invokeMethod(win, "closeAll"), QMetaObject.invokeMethod(win, "showCommands")))]
    state = {"i": 0}

    def step():
        name, prep = shots[state["i"]]
        prep()
        QTimer.singleShot(600, lambda: snap(name))

    def snap(name):
        img = win.grabWindow()
        if img.isNull() or not img.save(str(OUT / f"{name}.png")):
            print("FAIL: could not save", name, file=sys.stderr)
            app.exit(3)
            return
        print("saved", OUT / f"{name}.png")
        state["i"] += 1
        if state["i"] >= len(shots):
            app.quit()
        else:
            QTimer.singleShot(100, step)

    QTimer.singleShot(500, step)
    QTimer.singleShot(30000, lambda: (print("FAIL: timeout", file=sys.stderr), app.exit(4)))
    app.exec()
    del engine


if __name__ == "__main__":
    main()
