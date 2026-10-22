"""Songs as a person keeps them: a new song, opening one, Save As, the recent list and crash recovery.

A song is one Sound document in a project folder (`<folder>/docs/<item>.trk`, rostrum_core.storage); every change
is written there as it happens (the document is the single source of truth, and agents edit the same file), so
"saving" a named song is never needed. What a person still needs:

- **A new song** starts *untitled* in the untitled area (`untitled_root()`), saved on every change like any other,
  so nothing is lost; Save gives it a name and a place (Save As moves it, the untitled copy is removed).
- **Save As** copies the whole project folder (document, history, takes, renders) to a new folder and goes on there.
- **Recent songs**: the last 10 opened, in the settings folder; ones that are gone drop out when read.
- **Crash recovery**: while a song is open its folder holds `.rostrum/sound-open.json` (the process id). A lock
  left by a process that is no longer running means the app stopped unexpectedly: an untitled song left that way is
  offered back on the next start (its changes are all there); a named song needs nothing (it was saved per change).
"""
from __future__ import annotations

import json
import os
import shutil
import time
from pathlib import Path

from rostrum_core import Document, RostrumError, codes
from rostrum_core import project
from rostrum_core.storage import paths, write_atomic
from rostrum_sound import KIND, settings

ITEM = "song"                      # a new song's item id inside its project folder
LOCK = Path(".rostrum") / "sound-open.json"
RECENT_MAX = 10


def untitled_root() -> Path:
    return settings.settings_dir().parent / "untitled-songs"


def recent_file() -> Path:
    return settings.settings_dir() / "sound-recent.json"


# ---- making, finding ----------------------------------------------------------------------------------------
def new_song() -> Document:
    """A new, empty, untitled song (saved at once, so it survives a crash), with the person's defaults for new songs
    (Settings: sample rate, loudness target, true-peak ceiling)."""
    s = settings.load()
    folder = untitled_root() / time.strftime("untitled-%Y%m%d-%H%M%S")
    n = 1
    while folder.exists():
        n += 1
        folder = folder.with_name(f"{folder.name.split('~')[0]}~{n}")
    data = Document.new(KIND).data
    data["sampleRate"] = int(s["sampleRate"])
    master = data["master"][0]
    master["loudness"], master["truePeak"] = float(s["loudness"]), float(s["truePeak"])
    doc = Document(KIND, data, folder=folder, item=ITEM)
    doc.save()
    return doc


def is_untitled(folder) -> bool:
    try:
        Path(folder).resolve().relative_to(untitled_root().resolve())
        return True
    except ValueError:
        return False


def song_item(folder) -> str:
    """The Sound document in a project folder: the only one, else the one changed most recently."""
    found = project.items(folder, "sound")
    if not found:
        raise RostrumError(codes.NOT_FOUND, "open", str(folder), "has no RostrumSound song in it",
                           hint="Pick a song file (.trk) or a project folder that has one in its docs folder.")
    newest = lambda it: (Path(folder) / it["file"]).stat().st_mtime  # noqa: E731
    return max(found, key=newest)["id"]


def resolve(path) -> tuple[Path, str]:
    """A song file (`…/docs/<item>.trk`) or a project folder -> (project folder, item)."""
    p = Path(path)
    if p.is_file() and p.suffix == KIND.ext and p.parent.name == "docs":
        return p.parent.parent, p.stem
    if p.is_file():
        raise RostrumError(codes.BAD_ARGUMENT, "open", str(p), f"is not a RostrumSound song (a {KIND.ext} file "
                           "in a project's docs folder)")
    return p, song_item(p)


def open_song(folder, item) -> Document:
    if not paths(folder, item, KIND.ext)["doc"].is_file():
        raise RostrumError(codes.NOT_FOUND, "open", f"{folder} ({item})", "is not there any more")
    return Document.open(folder, item, KIND)


def title(folder, item) -> str:
    """The name a person sees: the project folder's name (its song item named too when there are several)."""
    if is_untitled(folder):
        return "Untitled song"
    many = len(project.items(folder, "sound")) > 1 if Path(folder, "docs").is_dir() else False
    return f"{Path(folder).name} · {item}" if many else Path(folder).name


# ---- Save As ------------------------------------------------------------------------------------------------
def save_as(folder, item, dest) -> Path:
    """Copy the project to `dest` (a new folder, or an empty one) and return it; an untitled source is then removed.
    Refuses to overwrite a folder that has anything in it."""
    src, dest = Path(folder).resolve(), Path(dest).resolve()
    if dest == src:
        return dest
    if dest.exists() and any(dest.iterdir()):
        raise RostrumError(codes.BAD_ARGUMENT, "save as", str(dest), "already has files in it",
                           hint="Pick a new name, or an empty folder.")
    if src in dest.parents:
        raise RostrumError(codes.BAD_ARGUMENT, "save as", str(dest), "is inside the song's own folder")
    shutil.copytree(src, dest, dirs_exist_ok=True, ignore=shutil.ignore_patterns("sound-open.json", "*.partial"))
    if is_untitled(src):
        unlock(src)
        shutil.rmtree(src, ignore_errors=True)
    return dest


# ---- recent ---------------------------------------------------------------------------------------------------
def recent() -> list[dict]:
    """[{folder, item, name}] newest first; songs that are gone (or untitled) are left out."""
    try:
        rows = json.loads(recent_file().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    return [r for r in rows if paths(r["folder"], r["item"], KIND.ext)["doc"].is_file() and not is_untitled(r["folder"])]


def remember(folder, item):
    if is_untitled(folder):
        return
    row = {"folder": str(Path(folder).resolve()), "item": item, "name": title(folder, item)}
    rows = [row] + [r for r in recent() if (r["folder"], r["item"]) != (row["folder"], item)]
    write_atomic(recent_file(), json.dumps(rows[:RECENT_MAX], indent=1, ensure_ascii=False))


# ---- open lock and recovery -------------------------------------------------------------------------------------
def lock(folder, pid: int | None = None):
    """Mark the song open by this process (`pid` 0: by none, i.e. left to be recovered)."""
    write_atomic(Path(folder) / LOCK, json.dumps({"pid": os.getpid() if pid is None else pid, "at": time.time()}))


def unlock(folder):
    (Path(folder) / LOCK).unlink(missing_ok=True)


def _alive(pid: int) -> bool:
    if pid <= 0:
        return False
    if pid == os.getpid():
        return True
    try:
        import psutil
        return psutil.pid_exists(pid)
    except ImportError:              # no psutil: Windows' own answer
        import subprocess
        out = subprocess.run(["tasklist", "/FI", f"PID eq {pid}", "/NH"], capture_output=True, text=True).stdout
        return str(pid) in out


def left_open(folder) -> bool:
    """The song's folder has a lock from a process that is not running: the app stopped while it was open."""
    try:
        pid = json.loads((Path(folder) / LOCK).read_text(encoding="utf-8"))["pid"]
    except (OSError, ValueError, KeyError):
        return False
    return not _alive(int(pid))


def to_recover() -> list[Path]:
    """Untitled songs left by an app that stopped unexpectedly, newest first."""
    root = untitled_root()
    found = [f for f in root.iterdir() if f.is_dir() and left_open(f)] if root.is_dir() else []
    return sorted(found, key=lambda f: f.stat().st_mtime, reverse=True)


def discard_untitled(folder):
    """An untitled song the person chose not to keep."""
    if not is_untitled(folder):
        raise RostrumError(codes.BAD_ARGUMENT, "discard", str(folder), "is a named song; only untitled songs are discarded")
    shutil.rmtree(folder, ignore_errors=True)


def changed(doc) -> bool:
    """Anything done in this song (an untitled one with no change can close without asking)."""
    return bool(doc.history.changes)
