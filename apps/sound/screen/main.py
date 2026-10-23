"""RostrumSound's screen: one workspace on one Sound document (the arrangement, the Editor / Mixer dock, the Sounds
panel, the settings panel; apps/sound/DESIGN.md §2).

    python apps/sound/screen/main.py                                  # the last song where it was left, else the start screen
    python apps/sound/screen/main.py <song file or project folder>    # open that song
    python apps/sound/screen/main.py --new                            # a new song ("Untitled song" in the projects folder)
    python apps/sound/screen/main.py --sample                         # a small sample song (in memory, not saved)
    python apps/sound/screen/main.py --script my_song.py              # on what a script builds (in memory, not saved)
    python apps/sound/screen/main.py --doc <project folder> <item>    # open a saved document (made if missing)
    python apps/sound/screen/main.py --step "select melody.n9600" --step "drag-note melody.n9600 0.6 2" --shot out.png
Every song with a folder is live: each change is on disk at once, shared with agents (shared/gui-kit/FILES.md).
Steps: see screensound/steps.py, plus the file steps here (`new [name]`, `openproject <path>`, `duplicate <name>`,
`version [name]`, `startscreen open|close`, `file-menu`, `settings`, `about`, `help`, `guide <file.md>`,
`add-track <sound>`, `library`, `export-open`, `file-in <path>`). With --shot the window quits by
itself once the sound has rendered; a failed step or render exits nonzero. Offscreen screenshots:
QT_QPA_PLATFORM=offscreen QT_QPA_FONTDIR=C:/Windows/Fonts.
    python apps/sound/screen/main.py --check-layout <folder>          # the layout check: every screen state at every
                                                                      # real window size (rostrum_gui/layout_run.py)
"""
import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
import checkout_paths  # noqa: E402  (this checkout's code first, before any Rostrum import)

checkout_paths.use_this_checkout()

from PySide6.QtCore import Q_ARG, QMetaObject, QTimer

from rostrum_core import Document, RostrumError
from rostrum_core import userhome
from rostrum_core.storage import paths
from rostrum_gui import guides, layout_run, qt_faults, start
from rostrum_gui.app import free, qt_app, stop
from rostrum_gui.settle import settle
from rostrum_sound import KIND, run_source
from rostrum_gui.project_files import ProjectFiles
from screensound.adder import Adder
from screensound.bridge import SoundBridge
from screensound.editor_side import EditorSide
from screensound.file_in import FileIn
from screensound.keys_record import KeysRecording
from screensound.library_panel import LibraryPanel
from screensound.mixer import MixPage
from screensound.recording import Recording
from screensound.sample import SOURCE
from screensound.files_sound import FILES_SOUND, title
from screensound.settings_page import SettingsPage
from screensound.song_panel import SongPanel

GUIDES = guides.entries(Path(__file__).resolve().parents[1] / "guides", [
    ("first-song.md", "Making your first song"), ("recording.md", "Recording"), ("exporting.md", "Exporting"),
    ("arranging-and-delivering.md", "Groups, versions and delivery"), ("settings.md", "Settings"),
    ("README.md", "All guides")])
from screensound.steps import do_step, wait_render

HERE = Path(__file__).resolve().parent
MAIN_QML = HERE / "qml" / "Main.qml"


def load_doc(args) -> Document | None:
    """--doc / --script / --sample as asked; None for a person's launch (`files.launch`: the song named, else the last
    one where it was left, else the start screen; a damaged one never stops the app: the screen says why)."""
    if args.doc:
        folder, item = args.doc
        if paths(folder, item, KIND.ext)["doc"].is_file():
            return FILES_SOUND.open(folder, item)
        doc = Document.new(KIND, folder=folder, item=item)
        doc.run_script(*_script(args))
        doc.save()
        return doc
    if args.script or args.sample:
        doc = Document.new(KIND)
        doc.run_script(*_script(args))
        return doc
    return None


def _script(args):
    if args.script:
        return Path(args.script).name, run_source(Path(args.script).read_text(encoding="utf-8"), Path(args.script).name)
    return "sample.py", run_source(SOURCE, "sample.py")


class Screen:
    """The window and everything made for one song; `show` replaces them all for another song."""

    def __init__(self, size=(1600, 960)):
        self.size, self.engine, self.win, self.parts = size, None, None, None
        self.files = ProjectFiles(FILES_SOUND, self)      # ≡ menu, start screen, Open recent (kit; saving is automatic)
        self.unnamed = "Untitled song"                     # the name of a song with no folder (--script, --sample)
        self.settings = SettingsPage()

    def show(self, doc):
        """Open `doc` in a new window; the old window goes first, then the old song's bridge and parts are closed and
        freed (the kit's stop and free: nothing of a closed song stays alive or keeps listening)."""
        name = title(doc.folder, doc.item_id) if doc.folder else self.unnamed
        bridge = SoundBridge(doc, name)            # live when the song has a folder
        mixer, recorder, side = MixPage(bridge), Recording(bridge), EditorSide(bridge)
        keys, library = KeysRecording(bridge, recorder), LibraryPanel(bridge)
        context = {"backend": bridge, "workspace": bridge.workspace, "mixer": mixer, "recorder": recorder,
                   "keys": keys, "takeSetup": recorder.setup, "files": self.files, "settingsPage": self.settings,
                   "adder": Adder(bridge), "songPanel": SongPanel(bridge), "editorSide": side, "fileIn": FileIn(bridge),
                   "soundLibrary": library, "guides": GUIDES}
        self.ctx_adder, self.ctx_file_in = context["adder"], context["fileIn"]
        old = (self.engine, self.win, self.parts)
        _, self.engine, self.win = start(MAIN_QML, context, self.size)
        self.parts = {"bridge": bridge, "mixer": mixer, "recorder": recorder, "keys": keys, "side": side,
                      "library": library, "context": context}   # every object QML reads lives as long as the window
        if old[0] is not None:
            stop(old[0], old[1], then=lambda: self._close(old[2]))

    @staticmethod
    def _close(parts):
        """A song's parts closed (engines, watchers, clocks), then freed: the window reading them is already gone."""
        for k in ("keys", "recorder", "library", "side", "mixer", "bridge"):
            parts[k].close()
        ctx = parts["context"]
        free(*(v for k, v in ctx.items() if k not in ("files", "settingsPage", "guides")), parts["side"])

    @property
    def bridge(self):
        return self.parts["bridge"] if self.parts else None

    def close(self):
        """At quit: the window and its bindings go first (the kit's stop), then what they read."""
        stop(self.engine, self.win, then=(lambda p=self.parts: self._close(p)) if self.parts else None)
        self.engine = self.win = None
        self.files.close()


def file_step(screen, step) -> bool:
    """The steps that switch songs or open the song menu / Settings (they live here, beside the session)."""
    word, _, rest = step.partition(" ")
    files, ok = screen.files, True
    if word in ("new", "file-new"):           # new [name]: ≡ › New (the kit's ProjectFiles)
        ok = files.newProject(rest.replace("_", " "))
    elif word in ("openproject", "file-open"):    # openproject <song file or project folder>
        ok = files.openPath(rest)
    elif word in ("duplicate", "duplicateproject", "file-duplicate"):     # duplicate <name or folder>: a copy; the window stays
        ok = files.duplicate(rest.replace("_", " ") if "/" not in rest and "\\" not in rest else rest)
    elif word == "version":                   # version [name]: Save a version (the time when no name)
        ok = files.saveVersion(rest.replace("_", " "))
    elif word == "startscreen":               # startscreen open|close
        files.setStart(rest == "open")
    elif word == "file-menu":
        QMetaObject.invokeMethod(screen.win, "openFileMenu")
    elif word == "add-track":                 # add-track <sound key> (the Sounds panel: adder.py; old names still work)
        screen.ctx_adder.add(rest)
    elif word == "sounds" or step.strip() == "library":     # the Library, open (Ctrl+L); `library <chip>`: steps_select
        QMetaObject.invokeMethod(screen.win, "openLibrary")
    elif word in ("export-open", "deliver-open"):     # the Export sheet, open (Ctrl+E)
        screen.parts["mixer"].export.setDialogOpen(True)
    elif word == "grid-open":                 # the header strip's Grid ▾ menu, open
        QMetaObject.invokeMethod(screen.win, "openGrid")
    elif word == "file-in":                   # + Add › From a file… (a sound, a MIDI file or a video)
        screen.ctx_file_in.add(rest)
    elif word == "settings":
        QMetaObject.invokeMethod(screen.win, "openSettings")
    elif word in ("about", "help"):           # Help › About and licences / the Help menu, open
        QMetaObject.invokeMethod(screen.win, "openAbout" if word == "about" else "openHelp")
    elif word == "agents":                    # agents [agent id]: Help › Connect an AI agent (with an id: its by-hand text open)
        QMetaObject.invokeMethod(screen.win, "openConnectAgent", Q_ARG("QVariant", rest))
    elif word == "guide":                     # guide <file.md>: Help › that guide, in the guide viewer
        guides.open_named(screen.win, rest)
    else:
        return False
    if not ok:
        raise RuntimeError(f"{word}: {screen.bridge.status}")
    return True


def main():
    a = argparse.ArgumentParser()
    a.add_argument("path", nargs="?", help="a song file (.trk) or a project folder")
    a.add_argument("--doc", nargs=2, metavar=("FOLDER", "ITEM"))
    a.add_argument("--script")
    a.add_argument("--sample", action="store_true")
    a.add_argument("--new", action="store_true")
    a.add_argument("--step", action="append", default=[])
    a.add_argument("--shot")
    a.add_argument("--size", default="1600x960", help="window size, WxH (for pictures; the layout check sets its own)")
    a.add_argument("--check-layout", metavar="FOLDER")
    a.add_argument("--check-name")
    a.add_argument("--check-only", help="with --check-layout: only these states (comma-separated), as the full run starts them")
    a.add_argument("--check-batch", metavar="STATES.JSON", help="with --check-layout: the states a parent run hands this process")
    a.add_argument("--quick", action="store_true", help="with --check-layout: the QUICK states, at 1646x900 only")
    args = a.parse_args()
    if args.check_layout and not (args.check_name or args.check_batch):
        from screensound.layout_states import states
        sys.exit(layout_run.run_all(Path(__file__), states(), args.check_layout, args.check_only, args.quick))

    os.environ.setdefault("QT_ENABLE_HIGHDPI_SCALING", "0")
    userhome.person_start()                        # a --shot / --step / --check-layout run is scripted anyway (userhome.scripted)
    app = qt_app()                                 # a picture or step run draws offscreen (rostrum_gui/app.py)
    screen = Screen(tuple(int(n) for n in args.size.lower().split("x")))
    code = [0]
    if args.check_batch:                           # several states in this one process (rostrum_gui/layout_batch.py)
        from rostrum_gui import layout_batch
        from screensound.layout_states import IGNORE

        def open_state(start):
            st = a.parse_args(start)
            screen.unnamed = (Path(st.script).stem if st.script else "Sample song") if (st.script or st.sample) else "Untitled song"
            doc = load_doc(st)
            screen.files.launch(st.path, st.new) if doc is None else screen.files.put(doc)

        layout_batch.batch(app, args.check_batch, args.check_layout, open_state,
                           lambda steps: [layout_run.kit_step(screen.bridge, s) or file_step(screen, s)
                                          or do_step(screen.bridge, screen.win, s, screen.parts["recorder"]) for s in steps],
                           lambda: screen.win, lambda: not screen.bridge.transport.busy(), IGNORE)
        code[0] = app.exec()
        screen.close()
        sys.exit(qt_faults.code(code[0]))
    if args.script or args.sample:
        screen.unnamed = Path(args.script).stem if args.script else "Sample song"
    doc = load_doc(args)
    if doc is None:
        screen.files.launch(args.path, args.new)
    else:
        screen.files.put(doc)

    def guarded(fn):
        try:
            fn()
        except Exception as e:  # noqa: BLE001  fail loudly, whatever it was
            print(f"FAIL: {e}", file=sys.stderr)
            code[0] = 3
            app.exit(3)

    def run_steps():
        for s in args.step:
            if not (layout_run.kit_step(screen.bridge, s) or file_step(screen, s)):
                do_step(screen.bridge, screen.win, s, screen.parts["recorder"])
        if args.check_layout:
            from screensound.layout_states import IGNORE
            layout_run.sweep(app, screen.win, args.check_layout, args.check_name,
                             lambda: not screen.bridge.transport.busy(), IGNORE)
        elif args.shot:
            wait_render(screen.bridge)
            settle(screen.win, lambda img: guarded(lambda: shoot(img)),      # frames until the screen holds still
                   lambda why: guarded(lambda: unsettled(why)))

    def unsettled(why):
        raise RuntimeError(why)

    def shoot(img):
        bridge = screen.bridge
        if bridge.status.startswith("Error"):
            raise RuntimeError(bridge.status)
        if not img.save(args.shot):
            raise RuntimeError(f"could not save {args.shot}")
        print(f"saved {args.shot} {img.width()}x{img.height()}  history={bridge.historyCount}  "
              f"selected={bridge.selected}  sound={bridge.soundState!r}  lufs={bridge.lastRender.get('lufs')}")
        app.exit(0)

    QTimer.singleShot(400, lambda: guarded(run_steps))
    if args.shot or args.check_layout:
        QTimer.singleShot(180000, lambda: (print("FAIL: timeout", file=sys.stderr), app.exit(4)))
    app.exec()
    screen.close()
    sys.exit(qt_faults.code(code[0]))    # a Qt fault fails a scripted run (rostrum_gui/qt_faults.py)


if __name__ == "__main__":
    main()
