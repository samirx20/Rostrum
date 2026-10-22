"""Opens one installed Rostrum app (what the Start-menu, desktop shortcuts and double-clicked files run):

    runtime\\python\\pythonw.exe runtime\\rostrum.pyw 2d|sound [<project>\\docs\\<item>.mtn|.trk] [app options, e.g. --shot x.png]
    runtime\\python\\pythonw.exe runtime\\rostrum.pyw 2d|sound --open-sample      (the Start menu's Samples entries)

No file: the app starts as it does on its own: the person's last file (its own Open recent list), else a new empty
one. --open-sample: the Lull sample, copied once to Documents\\Rostrum\\Samples so it can be saved
(rostrum_core.samples, the same helper as File › Open sample).

A problem never disappears silently. Everything the app writes goes to a log in %LOCALAPPDATA%\\Rostrum\\logs (the
newest 20 are kept), and the person is told in plain words, whichever way it went wrong:
- a Python error inside the running screen (a button's handler): a message box; the app stays open (`told`);
- a failed start, or the app stopping with an error: a message box naming the log;
- a hard crash (Qt or a native library) or the app ended from outside (Task Manager): the app runs in a second
  process (`--run`) watched by this one, which writes what happened at the end of the log and says so;
- this watcher ended too (a whole process tree ended, the computer stopped): its `<app>-<pid>.running` mark is still
  there on the next start, which writes that into the old log and says so.
Unsaved work is the app's own: its recovery copy (2D) or every-change save (Sound) is offered back on the next start.
"""
import ctypes
import datetime
import faulthandler
import json
import os
import runpy
import subprocess
import sys
import threading
import time
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]                # the install folder (mirrors the repo layout)
APPS = {"2d": ("Rostrum2D", ".mtn"), "sound": ("RostrumSound", ".trk")}
LOGS = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "Rostrum" / "logs"
ENDED = "--- ended normally, exit code "                  # the run's last line when Python itself finished
CRASHES = {0xC0000005: "a memory access fault", 0xC0000409: "a fatal error check", 0xC00000FD: "a stack overflow",
           0xC0000374: "damaged memory", 0xC000001D: "an instruction the processor can't run"}


def now():
    return f"{datetime.datetime.now():%Y-%m-%d %H:%M:%S}"


def message(title: str, text: str, wait=True):
    """A Windows message box; wait=False shows it beside the running app (its window keeps working)."""
    if os.environ.get("ROSTRUM_NO_MESSAGE_BOX"):           # set by automated checks, which read the log instead
        return
    box = lambda: ctypes.windll.user32.MessageBoxW(None, text, title, 0x30 | 0x10000)   # warning, in front  # noqa: E731
    box() if wait else threading.Thread(target=box, daemon=True).start()


def alive(pid: int) -> bool:
    k = ctypes.windll.kernel32
    h = k.OpenProcess(0x1000, False, pid)                  # PROCESS_QUERY_LIMITED_INFORMATION
    if not h:
        return False
    code = ctypes.c_ulong()
    k.GetExitCodeProcess(h, ctypes.byref(code))
    k.CloseHandle(h)
    return code.value == 259                               # STILL_ACTIVE


def append(log: Path, text: str):
    with open(log, "a", encoding="utf-8") as f:
        f.write(text if text.endswith("\n") else text + "\n")


def tail(log: Path, n=6) -> str:
    return "".join(open(log, encoding="utf-8", errors="replace").readlines()[-n:])


# ---- the watcher (the process the shortcut starts) ----------------------------------------------------------------

def new_log(app: str) -> Path:
    LOGS.mkdir(parents=True, exist_ok=True)
    for old in sorted(LOGS.glob(f"{app}-*.log"))[:-19]:
        old.unlink(missing_ok=True)
    path = LOGS / f"{app}-{datetime.datetime.now():%Y%m%d-%H%M%S}.log"
    append(path, f"{now()} {' '.join(sys.argv)}\nPython {sys.version}\ninstall {ROOT}")
    return path


def last_time(app: str, name: str, log: Path):
    """A run whose watcher ended too left its mark: say so in its log, in this one, and to the person."""
    for mark in LOGS.glob(f"{app}-*.running"):
        try:
            was = json.loads(mark.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            mark.unlink(missing_ok=True)
            continue
        if alive(was["pid"]):                              # another window of the app, still open
            continue
        old = Path(was["log"])
        if old.is_file():
            append(old, f"--- {now()} (found on the next start): {name} did not close. It was ended from outside "
                   "together with its watcher (for example the whole app in Task Manager), or the computer stopped.")
        append(log, f"the previous run did not close: {old}")
        mark.unlink(missing_ok=True)
        message(name, f"{name} did not close properly last time ({was.get('started', '')}): it was ended from "
                f"outside, or the computer stopped.\n\nIf you had unsaved work, {name} offers it back when it opens."
                f"\n\nWhat it wrote last time: {old}", wait=False)


def watch(app: str, name: str, rest: list[str]) -> int:
    log = new_log(app)
    last_time(app, name, log)
    mark = LOGS / f"{app}-{os.getpid()}.running"
    mark.write_text(json.dumps({"pid": os.getpid(), "log": str(log), "started": now()}), encoding="utf-8")
    try:
        env = {**os.environ, "ROSTRUM_LOG": str(log)}
        code = subprocess.call([sys.executable, __file__, "--run", app, *rest], env=env)
        if ENDED not in tail(log, 1):                     # Python never reached its last line: it was stopped
            code &= 0xFFFFFFFF
            fatal = [line.strip() for line in open(log, encoding="utf-8", errors="replace")
                     if line.startswith(("Fatal Python error", "Windows fatal exception"))]   # faulthandler's trace
            why = (f"{name} crashed ({fatal[-1] if fatal else CRASHES.get(code, 'a Windows error')})"
                   if fatal or code >= 0xC0000000 else f"{name} was ended from outside (for example in Task Manager)")
            append(log, f"--- {now()}: {why}, exit code 0x{code:08X}. The lines above are the last it wrote.")
            message(name, f"{why}.\n\nIf you had unsaved work, {name} offers it back when you open it again."
                    f"\n\nWhat it was doing is written in:\n{log}")
        return code
    finally:
        mark.unlink(missing_ok=True)


# ---- the app itself (--run) ---------------------------------------------------------------------------------------

def doc_args(app: str, rest: list[str]) -> list[str]:
    """A project file -> --doc <project folder> <item>; --open-sample -> the person's copy of the Lull sample;
    nothing -> no document (the app opens its last file or a new one); other options pass through."""
    name, ext = APPS[app]
    files = [a for a in rest if a.lower().endswith(ext)]
    others = [a for a in rest if a not in files and a != "--open-sample"]
    if files:
        doc = Path(files[0]).resolve()
        if doc.parent.name != "docs":
            raise SystemExit(f"{doc} is not inside a project's docs folder, so {name} can't tell which project it is.")
        return ["--doc", str(doc.parent.parent), doc.stem, *others]
    if "--open-sample" in rest:
        from rostrum_core import samples
        folder, item = samples.open_copy("lull", app)
        return ["--doc", str(folder), item, *others]
    return others


def told(name: str, log: Path):
    """sys.excepthook and threading.excepthook: an error inside the running screen goes to the log and to the person
    (once a minute at most), and the app stays open."""
    last = [-1e9]

    def hook(kind, value, tb, where=""):
        print(f"{now()} error{where}:", file=sys.stderr)
        traceback.print_exception(kind, value, tb)
        sys.stderr.flush()
        if time.monotonic() - last[0] > 60:
            last[0] = time.monotonic()
            said = "".join(traceback.format_exception_only(kind, value)).strip()
            message(name, f"{name} ran into a problem, so the last thing you did may not have finished:\n\n{said}"
                    f"\n\n{name} is still open. Save your work now; if anything looks wrong, close {name} and open it "
                    f"again.\n\nFull log: {log}", wait=False)

    def in_thread(a):
        hook(a.exc_type, a.exc_value, a.exc_traceback, f" in thread {a.thread.name if a.thread else '?'}")
    return hook, in_thread


def run(app: str, rest: list[str]) -> int:
    name = APPS[app][0]
    log = Path(os.environ.pop("ROSTRUM_LOG"))
    out = open(log, "a", encoding="utf-8", buffering=1)
    sys.stdout = sys.stderr = out                         # pythonw has no console: everything lands in the log
    faulthandler.enable(out)                              # a hard crash (Qt, a native library) still writes a trace
    sys.excepthook, threading.excepthook = told(name, log)
    os.environ["ROSTRUM_APP"] = app
    os.environ["ROSTRUM_NOTICES"] = str(ROOT / "apps" / app / "notices.json")
    os.environ.setdefault("ROSTRUM_SAMPLES", str(ROOT / "runtime" / "samples"))   # rostrum_core.samples' originals
    main_py = ROOT / "apps" / app / "screen" / "main.py"
    code = 0
    try:
        sys.argv = [str(main_py), *doc_args(app, rest)]
        sys.path.insert(0, str(main_py.parent))
        runpy.run_path(str(main_py), run_name="__main__")
    except SystemExit as e:
        code = e.code if isinstance(e.code, int) else (0 if e.code is None else 1)
        if not isinstance(e.code, int) and e.code is not None:
            print(e.code)
    except BaseException:  # noqa: BLE001  whatever it was, it goes to the log and the person is told
        traceback.print_exc()
        code = 1
    sys.stdout.flush()
    if code:
        message(name, f"{name} stopped with a problem. The last lines it wrote:\n\n{tail(log)}\nFull log: {log}")
    print(f"{ENDED}{code}")
    return code


def main():
    child = sys.argv[1:2] == ["--run"]
    args = sys.argv[2:] if child else sys.argv[1:]
    app = args[0] if args else ""
    if app not in APPS:
        message("Rostrum", f"Say which app to open: rostrum.pyw 2d or rostrum.pyw sound (got {app!r}).")
        return 2
    name = APPS[app][0]
    if not (ROOT / "apps" / app / "screen" / "main.py").is_file():
        message(name, f"{name} is not installed in {ROOT}. Run the Rostrum installer again and tick {name}.")
        return 2
    return run(app, args[1:]) if child else watch(app, name, args[1:])


if __name__ == "__main__":
    sys.exit(main())
