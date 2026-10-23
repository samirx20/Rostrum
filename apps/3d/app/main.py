"""Rostrum3D's screen: the scene, the live viewport, the inspector and the shot's timeline on one 3D document.

    python apps/3d/app/main.py                                   # the window, on a small sample document
    python apps/3d/app/main.py --script my_set.py                # on what a script builds
    python apps/3d/app/main.py --doc <project folder> <item>     # open a saved document (made if missing),
                                                                 # saved again after every change
    python apps/3d/app/main.py --step "select cam" --step "frame 24" --step "orbit 40 0" --shot out.png
Steps: see screen3d/steps.py. With --shot the window quits by itself once the viewport has drawn; a failed step,
picture or save exits nonzero. Offscreen screenshots: QT_QPA_PLATFORM=offscreen QT_QPA_FONTDIR=C:/Windows/Fonts.
--size WxH sets the window (pictures). A scripted run (--shot / --step / --check-layout) never writes into a real
project: --doc opens a scratch copy of it (screen3d/scratch_doc.py). The layout check, as in 2D and Sound:
    python apps/3d/app/main.py --check-layout <folder> [--quick]    # every screen state at every real window size
"""
import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
import checkout_paths  # noqa: E402  (this checkout's code first, before any Rostrum import)

checkout_paths.use_this_checkout()

from PySide6.QtCore import QTimer  # noqa: E402

from rostrum_core import Document, userhome  # noqa: E402
from rostrum_core.storage import paths  # noqa: E402
from rostrum3d import KIND  # noqa: E402
from rostrum3d.script import run_source  # noqa: E402
from rostrum_gui import guides, layout_run, qt_faults, start  # noqa: E402
from rostrum_gui.app import free, qt_app, stop  # noqa: E402
from screen3d.bridge3d import Bridge3D  # noqa: E402
from screen3d.sample import SOURCE  # noqa: E402
from screen3d.scratch_doc import isolated  # noqa: E402
from screen3d.steps import do_step  # noqa: E402

HERE = Path(__file__).resolve().parent
GUIDES = guides.entries(HERE.parent / "python" / "rostrum3d" / "guides", [      # Help's guides (also the agents' guides)
    ("agents.md", "Working with an AI agent"), ("script.md", "Building a scene with a script"), ("materials.md", "Materials"),
    ("lighting.md", "Lighting"), ("camera-rigs.md", "Camera rigs")])


def load_doc(args) -> tuple[Document, bool]:
    """(the document, whether it saves after every change): --doc's project (a scratch copy in a scripted run), else a
    document in memory that --script or the small sample builds."""
    source, name = SOURCE, "sample.py"
    if args.script:
        source, name = Path(args.script).read_text(encoding="utf-8"), Path(args.script).name
    if args.doc:
        folder, item = isolated(args.doc[0], args.doc[1], KIND.ext), args.doc[1]
        if paths(folder, item, KIND.ext)["doc"].is_file():
            return Document.open(folder, item, KIND), True
        doc = Document.new(KIND, folder=folder, item=item)
    else:
        doc = Document.new(KIND)
    doc.run_script(name, run_source(source, name))
    if args.doc:
        doc.save()
    return doc, bool(args.doc)


class Screen:
    """The window and the bridge of the document shown; `show` replaces them (the layout check opens one state after another)."""

    def __init__(self, size):
        self.size, self.engine, self.win, self.bridge = size, None, None, None

    def show(self, doc, shot_id=None, autosave=False):
        old = (self.engine, self.win, self.bridge)
        self.bridge = bridge = Bridge3D(doc, shot_id, autosave=autosave)
        _, self.engine, self.win = start(HERE / "qml" / "Main.qml",
                                         {"backend": bridge, "viewport": bridge.viewport, "guides": GUIDES}, self.size,
                                         providers={"view": bridge.viewport.provider})
        if old[0] is not None:
            stop(old[0], old[1], then=lambda: self._free(old[2]))

    @staticmethod
    def _free(bridge):
        bridge.close()
        free(bridge)

    def ready(self) -> bool:
        """The newest viewport picture has landed (or failed: the check then reports it) and no render is running."""
        v = self.bridge.viewport
        return (v.serial > 0 or v.status.startswith("Error")) and not self.bridge.render.running()

    def close(self):
        stop(self.engine, self.win, then=(lambda b=self.bridge: self._free(b)) if self.bridge else None)
        self.engine = self.win = None


def main():
    a = argparse.ArgumentParser()
    a.add_argument("--doc", nargs=2, metavar=("FOLDER", "ITEM"))
    a.add_argument("--script")
    a.add_argument("--shot-id", help="Which shot (default: the first)")
    a.add_argument("--step", action="append", default=[])
    a.add_argument("--shot", help="Save a screenshot here and quit")
    a.add_argument("--size", default="1600x960", help="window size, WxH (for pictures; the layout check sets its own)")
    a.add_argument("--check-layout", metavar="FOLDER")
    a.add_argument("--check-name")
    a.add_argument("--check-only", help="with --check-layout: only these states (comma-separated), as the full run starts them")
    a.add_argument("--check-batch", metavar="STATES.JSON", help="with --check-layout: the states a parent run hands this process")
    a.add_argument("--quick", action="store_true", help="with --check-layout: the QUICK states, at 1646x900 only")
    args = a.parse_args()
    if args.check_layout and not (args.check_name or args.check_batch):
        from screen3d.layout_states import states
        sys.exit(layout_run.run_all(Path(__file__), states(), args.check_layout, args.check_only, args.quick))

    os.environ.setdefault("QT_ENABLE_HIGHDPI_SCALING", "0")
    userhome.person_start()                        # a --shot / --step / --check-layout run is scripted anyway (userhome.scripted)
    app = qt_app()                                 # a picture or step run draws offscreen (rostrum_gui/app.py)
    screen = Screen(tuple(int(n) for n in args.size.lower().split("x")))
    code = [0]

    def run_step(s):
        layout_run.kit_step(screen.bridge, s) or do_step(screen.bridge, screen.win, s)

    if args.check_batch:                           # several states in this one process (rostrum_gui/layout_batch.py)
        from rostrum_gui import layout_batch

        def open_state(start_args):
            st = a.parse_args(start_args)
            doc, autosave = load_doc(st)
            screen.show(doc, st.shot_id, autosave)

        layout_batch.batch(app, args.check_batch, args.check_layout, open_state,
                           lambda steps: [run_step(s) for s in steps], lambda: screen.win, screen.ready)
        code[0] = app.exec()
        screen.close()
        sys.exit(qt_faults.code(code[0]))
    doc, autosave = load_doc(args)
    screen.show(doc, args.shot_id, autosave)
    bridge, win = screen.bridge, screen.win

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
            run_step(s)
        if args.check_layout:
            layout_run.sweep(app, win, args.check_layout, args.check_name, screen.ready)
        elif args.shot:
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
    if args.shot or args.check_layout:
        QTimer.singleShot(30000 + (600000 if any(s.startswith("render") for s in args.step) else 0),
                          lambda: (print("FAIL: timeout", file=sys.stderr), app.exit(4)))
    app.exec()
    screen.close()
    sys.exit(qt_faults.code(code[0]))


if __name__ == "__main__":
    main()
