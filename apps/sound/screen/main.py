"""RostrumSound's screen: Instruments, Timeline and Mix pages on one Sound document.

    python apps/sound/screen/main.py                                  # the last song, or a new untitled one
    python apps/sound/screen/main.py <song file or project folder>    # open that song
    python apps/sound/screen/main.py --new                            # a new untitled song
    python apps/sound/screen/main.py --sample                         # a small sample song (not saved)
    python apps/sound/screen/main.py --script my_song.py              # on what a script builds (not saved)
    python apps/sound/screen/main.py --doc <project folder> <item>    # open a saved document (made if missing)
    python apps/sound/screen/main.py --step "select melody.n9600" --step "drag-note melody.n9600 0.6 2" --shot out.png
Every song with a folder is saved after every change. Steps: see screensound/steps.py, plus the file steps here
(`file-new`, `file-open <path>`, `file-save-as <folder>`, `file-menu`, `settings`, `about`, `help`, `guide <file.md>`,
`add-track <kind>`). With --shot the window quits by
itself once the sound has rendered; a failed step, render or save exits nonzero. Offscreen screenshots:
QT_QPA_PLATFORM=offscreen QT_QPA_FONTDIR=C:/Windows/Fonts.
    python apps/sound/screen/main.py --check-layout <folder>          # the layout check: every screen state at every
                                                                      # real window size (rostrum_gui/layout_run.py)
"""
import argparse
import os
import sys
from pathlib import Path

from PySide6.QtCore import Q_ARG, QMetaObject, QTimer, QUrl
from PySide6.QtGui import QGuiApplication

from rostrum_core import Document, RostrumError
from rostrum_core.storage import paths
from rostrum_gui import guides, layout_run, start
from rostrum_sound import KIND, run_source
from rostrum_sound.opening import said
from screensound import projects
from screensound.adder import Adder
from screensound.bridge import SoundBridge
from screensound.instruments import InstrumentsPage
from screensound.keys_record import KeysRecording
from screensound.mixer import MixPage
from screensound.recording import Recording
from screensound.sample import SOURCE
from screensound.session import Songs
from screensound.settings_page import SettingsPage

GUIDES = guides.entries(Path(__file__).resolve().parents[1] / "guides", [
    ("first-song.md", "Making your first song"), ("recording.md", "Recording"), ("exporting.md", "Exporting"),
    ("settings.md", "Settings"), ("README.md", "All guides")])
from screensound.steps import do_step, wait_render

HERE = Path(__file__).resolve().parent
MAIN_QML = HERE / "qml" / "Main.qml"


def first_song(args) -> tuple[Document, str]:
    """(the first document, why the asked-for song was refused or ""). A song that can't be opened whole (a double-
    clicked damaged file, a last song saved by a newer version) is never shown half-read: a new untitled song opens
    instead and the screen says why, in words."""
    try:
        return first_doc(args), ""
    except RostrumError as e:
        if args.script or args.sample:
            raise
        print(f"FAIL: {e}", file=sys.stderr)
        return projects.new_song(), said(e)


def first_doc(args) -> Document:
    """What opens first: --doc / --script / --sample as asked, a path given, else the last song, else a new one."""
    if args.doc:
        folder, item = args.doc
        if paths(folder, item, KIND.ext)["doc"].is_file():
            return projects.open_song(folder, item)
        doc = Document.new(KIND, folder=folder, item=item)
        doc.run_script(*_script(args))
        doc.save()
        return doc
    if args.script or args.sample:
        doc = Document.new(KIND)
        doc.run_script(*_script(args))
        return doc
    if args.path:
        return projects.open_song(*projects.resolve(args.path))
    last = None if args.new else next(iter(projects.recent()), None)
    return projects.open_song(last["folder"], last["item"]) if last else projects.new_song()


def _script(args):
    if args.script:
        return Path(args.script).name, run_source(Path(args.script).read_text(encoding="utf-8"), Path(args.script).name)
    return "sample.py", run_source(SOURCE, "sample.py")


class Screen:
    """The window and everything made for one song; `show` replaces them all for another song."""

    def __init__(self, size=(1600, 960)):
        self.size, self.engine, self.win, self.parts = size, None, None, None
        self.songs = Songs(self.show)
        self.settings = SettingsPage()

    def show(self, doc, name, untitled=False):
        old_win, old_parts = self.win, self.parts
        if old_win is not None:
            old_win.close()
        if old_parts:
            self._close(old_parts)
        bridge = SoundBridge(doc, name, autosave=doc.folder is not None)
        instruments, mixer, recorder = InstrumentsPage(bridge), MixPage(bridge), Recording(bridge)
        keys = KeysRecording(bridge, recorder)
        context = {"backend": bridge, "instruments": instruments, "mixer": mixer, "recorder": recorder,
                   "keys": keys, "takeSetup": recorder.setup, "songs": self.songs, "settingsPage": self.settings,
                   "adder": Adder(bridge), "guides": GUIDES}
        self.ctx_adder = context["adder"]
        if self.engine is None:
            _, self.engine, self.win = start(MAIN_QML, context, self.size)
        else:
            ctx = self.engine.rootContext()
            for k, v in context.items():
                ctx.setContextProperty(k, v)
            self.engine.load(QUrl.fromLocalFile(str(MAIN_QML)))
            self.win = self.engine.rootObjects()[-1]
            self.win.resize(*self.size)
        if old_win is not None:
            old_win.deleteLater()
        self.parts = {"bridge": bridge, "instruments": instruments, "mixer": mixer, "recorder": recorder, "keys": keys}

    @staticmethod
    def _close(parts):
        for k in ("keys", "recorder", "mixer", "bridge"):
            parts[k].close()

    @property
    def bridge(self):
        return self.parts["bridge"]

    def close(self):
        if self.parts:
            self._close(self.parts)
        self.songs.close()


def file_step(screen, step) -> bool:
    """The steps that switch songs or open the song menu / Settings (they live here, beside the session)."""
    word, _, rest = step.partition(" ")
    if word == "file-new":
        screen.songs.newSong()
    elif word == "file-open":
        screen.songs.openPath(rest)
    elif word == "file-save-as":
        screen.songs.saveAs(rest)
    elif word == "file-menu":
        QMetaObject.invokeMethod(screen.win, "openFileMenu")
    elif word == "add-track":                 # add-track <piano|strings|…|audio> (the + Track menu)
        screen.ctx_adder.add(rest)
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
    if screen.songs.error:
        raise RuntimeError(f"{word}: {screen.songs.error}")
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
    args = a.parse_args()
    if args.check_layout and not args.check_name:
        from screensound.layout_states import states
        sys.exit(layout_run.run_all(Path(__file__), states(), args.check_layout))

    os.environ.setdefault("QT_ENABLE_HIGHDPI_SCALING", "0")
    app = QGuiApplication.instance() or QGuiApplication(sys.argv)
    screen = Screen(tuple(int(n) for n in args.size.lower().split("x")))
    doc, refused = first_song(args)
    if doc.folder is None:            # --script / --sample: shown as before, not a song on disk
        screen.show(doc, Path(args.script).stem if args.script else "Sample song")
    else:
        screen.songs.start(doc, refused)
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
            if not (layout_run.kit_step(screen.bridge, s) or file_step(screen, s)):
                do_step(screen.bridge, screen.win, s, screen.parts["recorder"])
        if args.check_layout:
            from screensound.layout_states import IGNORE
            layout_run.sweep(app, screen.win, args.check_layout, args.check_name,
                             lambda: not screen.bridge.transport.busy(), IGNORE)
        elif args.shot:
            wait_render(screen.bridge)
            QTimer.singleShot(600, lambda: guarded(shoot))     # the 160 ms reveals have finished

    def shoot():
        bridge = screen.bridge
        if bridge.status.startswith("Error"):
            raise RuntimeError(bridge.status)
        img = screen.win.grabWindow()
        if img.isNull() or not img.save(args.shot):
            raise RuntimeError(f"could not save {args.shot}")
        print(f"saved {args.shot} {img.width()}x{img.height()}  history={bridge.historyCount}  "
              f"selected={bridge.selected}  sound={bridge.soundState!r}  lufs={bridge.lastRender.get('lufs')}")
        app.exit(0)              # not quit(): that asks the window, and an untitled song with changes would ask back

    QTimer.singleShot(400, lambda: guarded(run_steps))
    if args.shot or args.check_layout:
        QTimer.singleShot(180000, lambda: (print("FAIL: timeout", file=sys.stderr), app.exit(4)))
    app.exec()
    screen.close()
    sys.exit(code[0])


if __name__ == "__main__":
    main()
