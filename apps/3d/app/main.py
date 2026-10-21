"""Rostrum3D's screen: the scene, the live viewport, the inspector and the shot's timeline on one 3D document.

    python apps/3d/app/main.py                                   # the window, on a small sample document
    python apps/3d/app/main.py --script my_set.py                # on what a script builds
    python apps/3d/app/main.py --doc <project folder> <item>     # open a saved document (made if missing),
                                                                 # saved again after every change
    python apps/3d/app/main.py --step "select cam" --step "frame 24" --step "orbit 40 0" --shot out.png
Steps: see screen3d/steps.py. With --shot the window quits by itself once the viewport has drawn; a failed step,
picture or save exits nonzero. Offscreen screenshots: QT_QPA_PLATFORM=offscreen QT_QPA_FONTDIR=C:/Windows/Fonts.
"""
import argparse
import os
import sys
from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtGui import QGuiApplication

from rostrum_core import Document
from rostrum_core.storage import paths
from rostrum3d import KIND
from rostrum3d.script import run_source
from rostrum_gui import start
from screen3d.bridge3d import Bridge3D
from screen3d.sample import SOURCE
from screen3d.steps import do_step

HERE = Path(__file__).resolve().parent


def load_doc(args) -> Document:
    source, name = SOURCE, "sample.py"
    if args.script:
        source, name = Path(args.script).read_text(encoding="utf-8"), Path(args.script).name
    if args.doc:
        folder, item = args.doc
        if paths(folder, item, KIND.ext)["doc"].is_file():
            return Document.open(folder, item, KIND)
        doc = Document.new(KIND, folder=folder, item=item)
    else:
        doc = Document.new(KIND)
    doc.run_script(name, run_source(source, name))
    if args.doc:
        doc.save()
    return doc


def main():
    a = argparse.ArgumentParser()
    a.add_argument("--doc", nargs=2, metavar=("FOLDER", "ITEM"))
    a.add_argument("--script")
    a.add_argument("--shot-id", help="Which shot (default: the first)")
    a.add_argument("--step", action="append", default=[])
    a.add_argument("--shot", help="Save a screenshot here and quit")
    args = a.parse_args()

    os.environ.setdefault("QT_ENABLE_HIGHDPI_SCALING", "0")
    app = QGuiApplication.instance() or QGuiApplication(sys.argv)
    bridge = Bridge3D(load_doc(args), args.shot_id, autosave=bool(args.doc))
    _, engine, win = start(HERE / "qml" / "Main.qml", {"backend": bridge, "viewport": bridge.viewport}, (1600, 960),
                           providers={"view": bridge.viewport.provider})
    code = [0]

    def guarded(fn):
        try:
            fn()
        except Exception as e:  # noqa: BLE001  fail loudly, whatever it was
            print(f"FAIL: {e}", file=sys.stderr)
            code[0] = 3
            app.exit(3)

    def run_steps():
        before = bridge.viewport.serial     # read before the steps: a step that blocks (render) may see its view land
        for s in args.step:
            do_step(bridge, win, s)
        if args.shot:
            wait_view(before)

    def wait_view(before):   # a picture newer than the steps' start has landed, then the 160 ms reveals have finished
        if bridge.viewport.serial > before or (before == 0 and bridge.viewport.serial > 0):
            QTimer.singleShot(600, lambda: guarded(shoot))
        elif bridge.viewport.status.startswith("Error"):
            guarded(shoot)                       # shoot() fails loudly on the viewport's error
        else:
            QTimer.singleShot(100, lambda: guarded(lambda: wait_view(before)))

    def shoot():
        for status in (bridge.status, bridge.viewport.status):
            if status.startswith("Error"):
                raise RuntimeError(status)
        img = win.grabWindow()
        if img.isNull() or not img.save(args.shot):
            raise RuntimeError(f"could not save {args.shot}")
        print(f"saved {args.shot} {img.width()}x{img.height()}  history={bridge.historyCount}  frame={bridge.frame}  "
              f"selected={bridge.selected}  shown={bridge.shown()}")
        app.quit()

    QTimer.singleShot(400, lambda: guarded(run_steps))
    if args.shot:
        QTimer.singleShot(30000 + (600000 if any(s.startswith("render") for s in args.step) else 0),
                          lambda: (print("FAIL: timeout", file=sys.stderr), app.exit(4)))
    app.exec()
    bridge.close()
    del engine
    sys.exit(code[0])


if __name__ == "__main__":
    main()
