"""The project's sound as another app hears it (Rostrum2D's soundtrack; AGENTS.md rule 9: one audio engine). No Qt.
Another app never compiles, mixes or plays a song itself: it asks here, and Sound's engine renders the mix.

    song = soundtrack.find(folder, "")          # {"id", "name", "file"} of the project's Sound item, or None
    root = soundtrack.read(folder, song["id"])  # the song's document, read whole (opening.py); never changed here
    wav = soundtrack.render(engine, folder, root)   # the mix: rendered once per content, then read from the cache
    soundtrack.grid(root, end)                  # {"bpm", "beatsPerBar", "changes", "beats": [s…], "bars": [s…]}
    soundtrack.stamp(folder, song["id"])        # changes whenever the song or the project's markers change
    soundtrack.facts(folder, "")                # what plays, for agents: item, name, seconds, bpm, bars, markers

Which song: the scene names one (`soundtrack`, a Sound item id); empty = the project's first Sound item by name.
A named item that is not a Sound item of the project is a loud error naming those that are.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from rostrum_core import RostrumError, codes
from rostrum_core import markers as shared
from rostrum_core import project
from rostrum_core.cache import put_file

from . import names, settings
from .compile import compile as compile_doc
from .doc import markers, tempo

KEEP = 6                     # mixes kept in the cache folder (each a few MB for a song)


def find(folder, item: str = "") -> dict | None:
    """The Sound item that plays: `item` when named, else the project's first; None when the project has none."""
    if not folder:
        return None
    songs = project.items(folder, "sound")
    if not item:
        return songs[0] if songs else None
    for s in songs:
        if s["id"] == item:
            return s
    raise RostrumError(codes.NOT_FOUND, "soundtrack", f'"{item}"', "is not a RostrumSound item of this project",
                       [s["id"] for s in songs], "Pick one of these, or leave Soundtrack empty for the project's sound.")


def read(folder, item: str) -> dict:
    from .opening import open_whole
    return open_whole(folder, item).data


def stamp(folder, item: str) -> tuple:
    """A cheap value that changes when the song's file or the project's markers change (a re-render is due)."""
    f = Path(folder) / project.item(folder, item)["file"]
    st = f.stat()
    return item, st.st_mtime_ns, st.st_size, shared.version(folder)


def _engine_id(engine) -> str:
    st = Path(engine.exe).stat()
    return f"{names.CONTRACT}|{st.st_size}|{st.st_mtime_ns}"


def cache() -> Path:
    d = settings.cache_dir() / "soundtrack"
    d.mkdir(parents=True, exist_ok=True)
    return d


def render(engine, folder, root: dict) -> Path:
    """The song's mix as Sound renders it (the same compile and engine as Sound's own export). Keyed by the schedule
    and the engine's version, so an unchanged song is never rendered twice; a failed render raises, loudly."""
    with markers.project(folder):
        schedule = compile_doc(root)
    key = hashlib.sha256((json.dumps(schedule, sort_keys=True, default=str) + _engine_id(engine)).encode()).hexdigest()
    out = cache() / f"{key[:24]}.wav"
    put_file(out, lambda tmp: engine.request("render", schedule=schedule, out=str(tmp)), "soundtrack")
    _trim()
    return out


def _trim():
    files = sorted(cache().glob("*.wav"), key=lambda p: p.stat().st_mtime, reverse=True)
    for p in files[KEEP:]:
        try:
            p.unlink()
        except OSError:
            pass                            # still open in a player: the next trim takes it


def grid(root: dict, end: float) -> dict:
    """The song's tempo map as times: every beat and every bar start from 0 to `end` seconds (doc/tempo.py)."""
    per = int(root.get("beatsPerBar", 4))
    beats = tempo.beats(root, end)
    return {"bpm": tempo.start_bpm(root), "beatsPerBar": per, "changes": bool(root.get("tempos")),
            "beats": beats, "bars": beats[::per]}


def facts(folder, item: str = "") -> dict | None:
    """What plays, in words an agent reads (no render): the item, its name, its length, tempo and bars. None: no sound."""
    song = find(folder, item)
    if song is None:
        return None
    root = read(folder, song["id"])
    with markers.project(folder):
        length = compile_doc(root).get("length", 0.0)
        marks = [{"name": n, "at": round(t, 3)} for n, t in markers.all(root)]
    seconds = tempo.seconds_at(root, float(length["beat"])) if isinstance(length, dict) else float(length or 0.0)
    g = grid(root, seconds)
    return {"item": song["id"], "name": song["name"], "seconds": round(seconds, 3), "bpm": g["bpm"],
            "beatsPerBar": g["beatsPerBar"], "tempoChanges": g["changes"], "bars": g["bars"],
            "markers": marks}
