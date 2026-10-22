"""Add a sound here (UX_SPEC 3.28 Sync sound; docs/PLAN.md › Sound in 2D): a sound from Sound's library tied to a
layer's start. 2D never mixes (AGENTS.md rule 9): the cue is a clip in RostrumSound's song (the one that plays with the
scene: project_sound.py), on a track "Cues from 2D", made through Sound's own operations; its time is a shared project
marker ("Logo · sound", rule 8) that `follow` keeps on the layer's start, so when the layer moves the cue moves and
Sound mixes it where it now is. The marker's id names the 2D item and the layer (`mk_cue_<item>_<layer>`). No Qt.

    cue(folder, doc, "logo", "C:/…/whoosh.wav", who, at=0.1)     # the clip, its marker, its track
    follow(folder, doc, who)                                      # after any 2D change: markers back on their layers
    choices("whoosh")                                             # sounds to pick from: Sound's library + your folders
"""
from __future__ import annotations

from pathlib import Path

from rostrum_core import RostrumError, codes, markers

from . import fields as F
from . import project_sound, retime
from .names import display_name

TRACK, TRACK_NAME = "cues_2d", "Cues from 2D"


def marker_id(item: str, layer: str) -> str:
    return f"mk_cue_{item}_{layer}"


def layer_start(folder, doc, layer_id: str) -> float:
    """The layer's start in scene seconds (its marker's or parent's offset plus its own start)."""
    off = retime.offset_of(doc.data, layer_id, markers.times(folder))
    return round(off + float(doc.item(layer_id).get("start", 0.0)), 6)


def _marker(folder, doc, layer_id: str, who) -> str:
    """The cue marker's name, made at the layer's start when it is not there yet (names are unique: "Logo · sound 2")."""
    mid, rows = marker_id(doc.item_id, layer_id), markers.listing(folder)
    mine = next((m for m in rows if m["id"] == mid), None)
    if mine:
        return mine["name"]
    layer = doc.item(layer_id)
    base, taken = f'{display_name(layer)} · sound', {m["name"].lower() for m in rows}
    name = next(n for n in (base if i == 1 else f"{base} {i}" for i in range(1, 1000)) if n.lower() not in taken)
    markers.edit(folder, [{"op": "marker.add", "args": {"name": name, "at": layer_start(folder, doc, layer_id),
                                                        "id": mid, "owner": "2d"}}], who, label="Sound cue marker")
    return name


def cue(folder, doc, layer_id: str, sound, who, at: float = 0.0, chosen: str = "") -> dict:
    """Put `sound` (a file) under layer `layer_id`, `at` seconds after its start, in the song that plays (`chosen`: the
    scene's soundtrack; empty = the main mix). Returns {song, track, clip, marker, file}. Loud on any missing piece."""
    if not folder:
        raise RostrumError(codes.BAD_ARGUMENT, "sound.cue", "the document", "is not in a project folder")
    if not doc.has(layer_id) or doc.item(layer_id)["type"] not in F.LAYERS:
        raise RostrumError(codes.NOT_FOUND, "sound.cue", f'layer "{layer_id}"', "is not a layer of this document")
    file = Path(sound)
    if not file.is_file():
        raise RostrumError(codes.NOT_FOUND, "sound.cue", f'sound "{sound}"', "is not a file",
                           hint="Pick one with inspect_sounds (Sound's library and your sound folders).")
    song = project_sound.song(folder, chosen)
    if song is None:
        raise RostrumError(codes.BAD_ARGUMENT, "sound.cue", "the project", "has no RostrumSound item to put the sound in",
                           hint="Make the project's sound in RostrumSound first (it owns every sound and mixes it).")
    name = _marker(folder, doc, layer_id, who)
    from rostrum_core import live
    from rostrum_sound.opening import open_whole
    snd = open_whole(folder, song["id"])
    live.keep(snd)                                   # one door with Sound's own window, if it has the song open
    ids = {t["id"] for t in snd.data.get("tracks", [])}
    clip_id = _free_id(snd, f"cue_{layer_id}")
    calls = [] if TRACK in ids else [{"op": "track.add", "args": {"id": TRACK, "name": TRACK_NAME}}]
    when = f"#{name}" + (f"{at:+g}" if at else "")
    calls.append({"op": "clip.add", "target": [TRACK], "args": {"id": clip_id, "media": str(file), "at": when}})
    from rostrum_sound.doc import markers as song_markers
    with song_markers.project(folder):               # Sound's check reads the project's shared markers ("#Logo · sound")
        snd.apply(calls, who, label=f"Sound cue from 2D: {name}")
    return {"song": song["id"], "track": TRACK, "clip": clip_id, "marker": name, "at": when, "file": str(file)}


def _free_id(snd, base: str) -> str:
    from rostrum_core.tree import index
    taken = set(index(snd.data, snd.kind.lists))
    return next(i for i in (base if n == 1 else f"{base}_{n}" for n in range(1, 10000)) if i not in taken)


def follow(folder, doc, who) -> list[str]:
    """Every cue marker of this document back on its layer's start (one change; none when all are in place). A cue
    whose layer is gone stays where it was. Returns the names moved."""
    if not folder:
        return []
    prefix, calls, moved = marker_id(doc.item_id, ""), [], []
    for m in markers.listing(folder):
        layer = m["id"][len(prefix):] if m["id"].startswith(prefix) else ""
        if layer and doc.has(layer):
            t = layer_start(folder, doc, layer)
            if abs(t - float(m["at"])) > 1e-6:
                calls.append({"op": "marker.move", "target": [m["id"]], "args": {"at": max(0.0, t)}})
                moved.append(m["name"])
    if calls:
        markers.edit(folder, calls, who, label="Sound cues follow their layers")
    return moved


def choices(words: str = "", limit: int = 40) -> list[dict]:
    """Recordings to pick from, all `words` matching: Sound's installed library first, then the person's own sound
    folders (read-only). [{path, about, seconds, where}]; a source that isn't there is skipped."""
    out = []
    try:
        from rostrum_sound import library
        for p in library.find("recordings", words)[:limit]:
            d = library.describe(p)
            out.append({"path": d["path"], "about": d["about"], "seconds": d.get("seconds"), "where": "Library"})
    except FileNotFoundError:
        pass                                         # no library installed: the person's folders only
    from rostrum_sound import userlib
    for s in userlib.search(words=words or None, limit=limit)["sounds"]:
        if s.get("start", 0) == 0:                   # whole files only: a cue plays a file from its start
            out.append({"path": s["path"], "about": s["about"], "seconds": s.get("seconds"), "where": "Your sounds"})
    return out[:limit]


def watch(doc, said) -> callable:
    """Keep this document's cue markers on their layers after every change (the screen's window and the agent server
    both watch the document they hold). A failure is handed to `said` (the status line, the server's log) in plain
    words; the 2D change itself stands. Returns the unsubscribe."""
    def on(ev):
        if ev.kind != "change" or ev.change is None or not doc.folder:
            return
        try:
            follow(doc.folder, doc, ev.change.who)
        except Exception as e:  # noqa: BLE001  never silent: said where the person or the agent reads it
            said(e.line() if hasattr(e, "line") else f"Error: sound cues: could not follow their layers: {e}")
    return doc.subscribe(on)
