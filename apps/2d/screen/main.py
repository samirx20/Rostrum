"""Rostrum2D's screen: Design and Animate pages on one 2D document.

    python apps/2d/screen/main.py                                   # a person's launch: the last project where it
                                                                    # was left, else the start screen
    python apps/2d/screen/main.py --sample                          # the window, on the small built-in screen sample
                                                                    # (in memory, never saved; for checks and pictures)
    python apps/2d/screen/main.py --script my_shot.py               # on what a script builds
    python apps/2d/screen/main.py --doc <project folder> <item>     # open a saved document (made if missing)
    python apps/2d/screen/main.py --open <doc file or project folder>   # open it the way ≡ › Open does
Every project window is live: each change is on disk at once, shared with agents (shared/gui-kit/FILES.md).
    python apps/2d/screen/main.py --sample --step "select title" --step "page animate" --step "time 1.2" --shot out.png
    python apps/2d/screen/main.py --check-layout <folder>             # the layout check: every screen state at every
                                                                    # real window size (rostrum_gui/layout_run.py)
Steps and --shot go with any start (no file named: the plain start, so a walk can check it). Steps: see screen2d/steps.py (file steps: screen2d/file_steps.py). With --shot the window quits by itself; a failed
step or frame exits nonzero.
A --shot / --step run draws offscreen by itself (rostrum_gui.app.qt_app); set QT_QPA_PLATFORM=windows to watch one.
"""
import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
import checkout_paths  # noqa: E402  (this checkout's code first, before any Rostrum import)

checkout_paths.use_this_checkout()

from PySide6.QtCore import QTimer
from rostrum_gui.app import qt_app

from rostrum_core import Document
from rostrum_core.storage import paths
from rostrum_gui import layout_run, qt_faults
from rostrum2d import KIND, run_source
from screen2d.sample import SOURCE
from screen2d.session import Session
from screen2d.steps import do_step
from screen2d import watchdog


def load_doc(args) -> Document | None:
    """--doc / --script / --sample as asked; None for a person's launch (`files.launch`: the project named by --open,
    else the last one where it was left, else the start screen)."""
    if not (args.doc or args.script or args.sample):
        return None
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
    a.add_argument("--size", default="1600x960", help="the window's size in logical px, WxH (screenshots at a person's screen size)")
    a.add_argument("--check-layout", metavar="FOLDER")
    a.add_argument("--check-name")
    args = a.parse_args()
    if args.check_layout and not args.check_name:
        from screen2d.layout_states import states
        sys.exit(layout_run.run_all(Path(__file__), states(), args.check_layout))
    if args.shot:
        check_shot_path(args.shot)

    watchdog.arm()                                 # a start that never shows its window says where it waits
    os.environ.setdefault("QT_ENABLE_HIGHDPI_SCALING", "0")
    app = qt_app()                                 # a picture or step run draws offscreen (rostrum_gui/app.py)
    session = Session(tuple(int(n) for n in args.size.lower().split("x")), args.comp)
    doc = load_doc(args)
    if doc is None:
        session.files.launch(args.open)
    else:
        session.files.put(doc)
    watchdog.shown_on(session.win)
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
            if not layout_run.kit_step(session.bridge, s):
                do_step(session.bridge, session.win, s)    # a file step may open another window
        if args.check_layout:
            from screen2d.layout_states import IGNORE
            bridge = session.bridge
            layout_run.sweep(app, session.win, args.check_layout, args.check_name,
                             lambda: bridge.frames.idle() and bridge.frame > 0, IGNORE)
        elif args.shot:          # the closing picture's own time limit counts from here: a step waits (and fails) on its own
            QTimer.singleShot(30000, lambda: (print("FAIL: timeout: the closing picture's frame never landed", file=sys.stderr),
                                              app.exit(4)))
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
        app.exit(code[0])

    QTimer.singleShot(400, lambda: guarded(run_steps))
    if args.shot or args.check_layout:      # a backstop for a step that hangs without a limit of its own
        QTimer.singleShot(120000 if args.check_layout else 1800000,
                          lambda: (print("FAIL: timeout: the run went on too long", file=sys.stderr), app.exit(4)))
    app.exec()
    session.close()
    sys.exit(qt_faults.code(code[0]))    # a Qt fault fails a scripted run (rostrum_gui/qt_faults.py)


if __name__ == "__main__":
    main()
