"""Opens one installed Rostrum app (what the Start-menu, desktop shortcuts and double-clicked files run):

    runtime\\python\\pythonw.exe runtime\\rostrum.pyw 2d|sound [<project>\\docs\\<item>.mtn|.trk] [app options, e.g. --shot x.png]

No file: the Lull sample, copied once to Documents\\Rostrum\\Samples so it can be saved. Everything the app writes
goes to a log in %LOCALAPPDATA%\\Rostrum\\logs (the newest 20 are kept); a crash or a failed start shows a message
box naming that log, so a problem never disappears silently.
"""
import ctypes
import datetime
import faulthandler
import os
import runpy
import shutil
import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]                # the install folder (mirrors the repo layout)
APPS = {"2d": ("Rostrum2D", ".mtn", "film"), "sound": ("RostrumSound", ".trk", "score")}
LOGS = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "Rostrum" / "logs"
SAMPLE = Path.home() / "Documents" / "Rostrum" / "Samples" / "Lull"


def message(title: str, text: str):
    if not os.environ.get("ROSTRUM_NO_MESSAGE_BOX"):     # set by automated checks, which read the log instead
        ctypes.windll.user32.MessageBoxW(None, text, title, 0x30)


def open_log(app: str):
    LOGS.mkdir(parents=True, exist_ok=True)
    for old in sorted(LOGS.glob(f"{app}-*.log"))[:-19]:
        old.unlink(missing_ok=True)
    path = LOGS / f"{app}-{datetime.datetime.now():%Y%m%d-%H%M%S}.log"
    log = open(path, "w", encoding="utf-8", buffering=1)
    sys.stdout = sys.stderr = log                         # pythonw has no console: everything lands in the log
    faulthandler.enable(log)                              # a hard crash (Qt, a native library) still writes a trace
    print(f"{datetime.datetime.now():%Y-%m-%d %H:%M:%S} {' '.join(sys.argv)}\nPython {sys.version}\ninstall {ROOT}")
    return path


def doc_args(app: str, rest: list[str]) -> list[str]:
    """A project file -> --doc <project folder> <item>; nothing -> the sample; other options pass through."""
    name, ext, item = APPS[app]
    files = [a for a in rest if a.lower().endswith(ext)]
    others = [a for a in rest if a not in files]
    if files:
        doc = Path(files[0]).resolve()
        if doc.parent.name != "docs":
            raise SystemExit(f"{doc} is not inside a project's docs folder, so {name} can't tell which project it is.")
        return ["--doc", str(doc.parent.parent), doc.stem, *others]
    if "--doc" in others:
        return others
    if not SAMPLE.is_dir():
        shutil.copytree(ROOT / "runtime" / "samples" / "lull", SAMPLE)
    return ["--doc", str(SAMPLE), item, *others]


def main():
    app = sys.argv[1] if len(sys.argv) > 1 else ""
    if app not in APPS:
        message("Rostrum", f"Say which app to open: rostrum.pyw 2d or rostrum.pyw sound (got {app!r}).")
        return 2
    name = APPS[app][0]
    main_py = ROOT / "apps" / app / "screen" / "main.py"
    if not main_py.is_file():
        message(name, f"{name} is not installed in {ROOT}. Run the Rostrum installer again and tick {name}.")
        return 2
    log = open_log(app)
    os.environ["ROSTRUM_APP"] = app
    os.environ["ROSTRUM_NOTICES"] = str(ROOT / "apps" / app / "notices.json")
    code = 0
    try:
        sys.argv = [str(main_py), *doc_args(app, sys.argv[2:])]
        sys.path.insert(0, str(main_py.parent))
        runpy.run_path(str(main_py), run_name="__main__")
    except SystemExit as e:
        code = e.code if isinstance(e.code, int) else (0 if e.code is None else 1)
        if not isinstance(e.code, int) and e.code is not None:
            print(e.code)
    except BaseException:  # noqa: BLE001  whatever it was, it goes to the log and the person is told
        traceback.print_exc()
        code = 1
    if code:
        sys.stdout.flush()
        tail = "".join(open(log, encoding="utf-8").readlines()[-6:])
        message(name, f"{name} stopped with a problem. The last lines it wrote:\n\n{tail}\nFull log: {log}")
    return code


if __name__ == "__main__":
    sys.exit(main())
