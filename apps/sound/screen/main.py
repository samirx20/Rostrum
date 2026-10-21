"""RostrumSound's screen: Instruments, Timeline and Mix pages on one Sound document.

    python apps/sound/screen/main.py                                  # the window, on a small sample song
    python apps/sound/screen/main.py --script my_song.py              # on what a script builds
    python apps/sound/screen/main.py --doc <project folder> <item>    # open a saved document (made if missing),
                                                                      # saved again after every change
    python apps/sound/screen/main.py --step "select melody.n9600" --step "drag-note melody.n9600 0.6 2" --shot out.png
Steps: see screensound/steps.py. With --shot the window quits by itself once the sound has rendered; a failed
step, render or save exits nonzero. Offscreen screenshots: QT_QPA_PLATFORM=offscreen QT_QPA_FONTDIR=C:/Windows/Fonts.
"""
import argparse
import os
import sys
from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtGui import QGuiApplication

from rostrum_core import Document
from rostrum_core.storage import paths
from rostrum_gui import start
from rostrum_sound import KIND, run_source
from screensound.bridge import SoundBridge
from screensound.instruments import InstrumentsPage
from screensound.mixer import MixPage
from screensound.sample import SOURCE
from screensound.steps import do_step, wait_render

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
    a.add_argument("--step", action="append", default=[])
    a.add_argument("--shot")
    args = a.parse_args()

    os.environ.setdefault("QT_ENABLE_HIGHDPI_SCALING", "0")
    app = QGuiApplication.instance() or QGuiApplication(sys.argv)
    name = args.doc[1] if args.doc else Path(args.script).stem if args.script else "Sample song"
    bridge = SoundBridge(load_doc(args), name, autosave=bool(args.doc))
    instruments, mixer = InstrumentsPage(bridge), MixPage(bridge)
    _, engine, win = start(HERE / "qml" / "Main.qml", {"backend": bridge, "instruments": instruments, "mixer": mixer},
                           (1600, 960))
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
            wait_render(bridge)
            QTimer.singleShot(600, lambda: guarded(shoot))     # the 160 ms reveals have finished

    def shoot():
        if bridge.status.startswith("Error"):
            raise RuntimeError(bridge.status)
        img = win.grabWindow()
        if img.isNull() or not img.save(args.shot):
            raise RuntimeError(f"could not save {args.shot}")
        print(f"saved {args.shot} {img.width()}x{img.height()}  history={bridge.historyCount}  "
              f"selected={bridge.selected}  sound={bridge.soundState!r}  lufs={bridge.lastRender.get('lufs')}")
        app.quit()

    QTimer.singleShot(400, lambda: guarded(run_steps))
    if args.shot:
        QTimer.singleShot(180000, lambda: (print("FAIL: timeout", file=sys.stderr), app.exit(4)))
    app.exec()
    mixer.close()
    bridge.close()
    del engine
    sys.exit(code[0])


if __name__ == "__main__":
    main()
