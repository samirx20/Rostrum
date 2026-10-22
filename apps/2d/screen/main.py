"""Rostrum2D's screen: Design and Animate pages on one 2D document.

    python apps/2d/screen/main.py                                   # a person's launch: the last project opened,
                                                                    # else a new "Untitled N" project
    python apps/2d/screen/main.py --sample                          # the window, on the small built-in sample
                                                                    # (never saved; the only way it opens)
    python apps/2d/screen/main.py --script my_shot.py               # on what a script builds
    python apps/2d/screen/main.py --doc <project folder> <item>     # open a saved document (made if missing),
                                                                    # saved again after every change (launchers, agents)
    python apps/2d/screen/main.py --open <doc file or project folder>   # open it the way a person does: File > Save
                                                                    # saves, unsaved changes are kept in a recovery copy
    python apps/2d/screen/main.py --sample --step "select title" --step "page animate" --step "time 1.2" --shot out.png
Steps and --shot go with any start (no file named: the plain start, so a walk can check it). Steps: see screen2d/steps.py (file steps: screen2d/file_steps.py). With --shot the window quits by itself; a failed
step, frame or save exits nonzero.
Offscreen screenshots: QT_QPA_PLATFORM=offscreen QT_QPA_FONTDIR=C:/Windows/Fonts.
"""
import argparse
import os
import sys
from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtGui import QGuiApplication

from rostrum_core import Document, Who
from rostrum_core.storage import paths
from rostrum2d import KIND, run_source
from screen2d import projects, recent
from screen2d.projects import resolve
from screen2d.sample import SOURCE
from screen2d.session import Session
from screen2d.steps import do_step


def first_doc() -> Document:
    """What a plain launch opens: the newest project in Open recent still on disk, else a new Untitled project."""
    last = recent.rows()
    if last:
        return Document.open(last[0]["folder"], last[0]["item"], KIND)
    return projects.new_project(projects.untitled(), Who.person("sam"))


def load_doc(args) -> Document:
    if args.open:
        return Document.open(*resolve(args.open), KIND)
    if not (args.doc or args.script or args.sample):
        return first_doc()
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
    a.add_argument("--open", metavar="PATH")
    a.add_argument("--script")
    a.add_argument("--sample", action="store_true")
    a.add_argument("--comp")
    a.add_argument("--step", action="append", default=[])
    a.add_argument("--shot")
    args = a.parse_args()
    if args.shot:
        check_shot_path(args.shot)

    os.environ.setdefault("QT_ENABLE_HIGHDPI_SCALING", "0")
    app = QGuiApplication.instance() or QGuiApplication(sys.argv)
    session = Session((1600, 960))
    session.show(load_doc(args), live=bool(args.doc), comp_id=args.comp)
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
            do_step(session.bridge, session.win, s)        # a file step may open another window
        if args.shot:
            wait_frame(0)

    def wait_frame(n):       # the newest frame has landed, then the 160 ms reveals have finished
        bridge = session.bridge
        if bridge.frames.idle() and bridge.frame > 0:
            QTimer.singleShot(600, lambda: guarded(shoot))
        else:
            QTimer.singleShot(100, lambda: guarded(lambda: wait_frame(n + 1)))

    def shoot():
        bridge = session.bridge
        if bridge.status.startswith("Error"):
            raise RuntimeError(bridge.status)
        img = session.win.grabWindow()
        if img.isNull() or not img.save(args.shot):
            raise RuntimeError(f"could not save {args.shot}")
        print(f"saved {args.shot} {img.width()}x{img.height()}  history={bridge.historyCount}  "
              f"selected={bridge.selected}  shown={bridge.shown()}")
        app.exit(0)          # not quit(): that asks each window to close, and one with unsaved changes asks first

    QTimer.singleShot(400, lambda: guarded(run_steps))
    if args.shot:
        QTimer.singleShot(30000, lambda: (print("FAIL: timeout", file=sys.stderr), app.exit(4)))
    app.exec()
    session.close()
    sys.exit(code[0])


if __name__ == "__main__":
    main()
