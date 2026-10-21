"""Rostrum2D's screen: Design and Animate pages on one 2D document.

    python apps/2d/screen/main.py                                   # the window, on a small sample document
    python apps/2d/screen/main.py --script my_shot.py               # on what a script builds
    python apps/2d/screen/main.py --doc <project folder> <item>     # open a saved document (made if missing),
                                                                    # saved again after every change
    python apps/2d/screen/main.py --step "select title" --step "page animate" --step "time 1.2" --shot out.png
Steps: see screen2d/steps.py. With --shot the window quits by itself; a failed step, frame or save exits nonzero.
Offscreen screenshots: QT_QPA_PLATFORM=offscreen QT_QPA_FONTDIR=C:/Windows/Fonts.
"""
import argparse
import math
import os
import sys
from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtGui import QGuiApplication

from rostrum_core import Document
from rostrum_core.storage import paths
from rostrum2d import KIND, run_source
from rostrum2d.engine import EngineError
from rostrum2d.seen import first_seen
from rostrum_gui import start
from screen2d.bridge2d import Bridge2D
from screen2d.sample import SOURCE
from screen2d.steps import do_step

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


def opening_time(bridge) -> float:
    """Open on a frame worth seeing: the first moment something can be seen (rostrum2d.seen, the same rule as the
    Problems "never seen" check), on the frame at or after it; 0 when nothing is ever seen or a text can't be measured
    (the Problems list says why)."""
    try:
        t = first_seen(bridge.placed())
    except EngineError:
        return 0.0
    fps = bridge.comp()["fps"]
    return math.ceil((t or 0.0) * fps - 1e-6) / fps


def check_shot_path(shot: str):
    """Fail at once when the picture can't be saved: the folder must exist and be writable, the extension one Qt writes."""
    from PySide6.QtGui import QImageWriter
    path = Path(shot).resolve()
    ext = path.suffix.lstrip(".").lower().encode()
    if ext not in QImageWriter.supportedImageFormats():
        sys.exit(f"FAIL: --shot {shot}: Qt cannot write .{ext.decode() or '(no extension)'} files (use .png)")
    if not path.parent.is_dir():
        sys.exit(f"FAIL: --shot {shot}: the folder {path.parent} does not exist")
    if not os.access(path.parent, os.W_OK) or path.is_dir():
        sys.exit(f"FAIL: --shot {shot}: {path} is not writable")


def main():
    a = argparse.ArgumentParser()
    a.add_argument("--doc", nargs=2, metavar=("FOLDER", "ITEM"))
    a.add_argument("--script")
    a.add_argument("--comp")
    a.add_argument("--step", action="append", default=[])
    a.add_argument("--shot")
    args = a.parse_args()
    if args.shot:
        check_shot_path(args.shot)

    os.environ.setdefault("QT_ENABLE_HIGHDPI_SCALING", "0")
    app = QGuiApplication.instance() or QGuiApplication(sys.argv)
    bridge = Bridge2D(load_doc(args), args.comp, autosave=bool(args.doc))
    bridge.setTime(opening_time(bridge))
    _, engine, win = start(HERE / "qml" / "Main.qml", {"backend": bridge, "painter": bridge.painter}, (1600, 960),
                           providers={"frame": bridge.frames.provider, "onion": bridge.painter.provider})
    code = [0]

    def guarded(fn):
        try:
            fn()
        except Exception as e:  # noqa: BLE001  fail loudly, whatever it was
            print(f"FAIL: {e}", file=sys.stderr)
            code[0] = 3
            app.exit(3)

    def run_steps():
        for s in args.step:
            do_step(bridge, win, s)
        if args.shot:
            wait_frame(0)

    def wait_frame(n):       # the newest frame has landed, then the 160 ms reveals have finished
        if bridge.frames.idle() and bridge.frame > 0:
            QTimer.singleShot(600, lambda: guarded(shoot))
        else:
            QTimer.singleShot(100, lambda: guarded(lambda: wait_frame(n + 1)))

    def shoot():
        if bridge.status.startswith("Error"):
            raise RuntimeError(bridge.status)
        img = win.grabWindow()
        if img.isNull() or not img.save(args.shot):
            raise RuntimeError(f"could not save {args.shot}")
        print(f"saved {args.shot} {img.width()}x{img.height()}  history={bridge.historyCount}  "
              f"selected={bridge.selected}  shown={bridge.shown()}")
        app.quit()

    QTimer.singleShot(400, lambda: guarded(run_steps))
    if args.shot:
        QTimer.singleShot(30000, lambda: (print("FAIL: timeout", file=sys.stderr), app.exit(4)))
    app.exec()
    bridge.close()
    del engine
    sys.exit(code[0])


if __name__ == "__main__":
    main()
