"""Add a sound here (UX_SPEC 3.28 Sync sound; docs/PLAN.md › Sound in 2D): a sound from Sound's library tied to a
layer's start. 2D never mixes (AGENTS.md rule 9): the cue is a clip in RostrumSound's song (the one that plays with the
scene: project_sound.py), on a track "Cues from 2D", made through Sound's own operations; its time is a shared project
marker ("Logo · sound", rule 8) that `follow` keeps on the layer's start, so when the layer moves the cue moves and
Sound mixes it where it now is. The marker's id names the 2D item and the layer (`mk_cue_<item>_<layer>`). No Qt.

The person's step is the marker and the clip together (rostrum_core.joint: one step across the markers and the song,
so Ctrl+Z takes both back and Redo brings both back; both are the person's). The marker follows its layer (`marker.follow`,
rostrum_core.links): kept on the layer's start by LINK, 2D's sound link, never an Undo step of its own.

    cue(folder, doc, "logo", "note:piano", who)                  # a note on the song's piano on the layer's start
    cue(folder, doc, "logo", "C:/…/my-tap.wav", who, at=0.1)     # or a recording: marker and clip, one Undo step
    follow(folder, doc)                                           # after any 2D change: markers back on their layers
    choices(folder=folder)                                        # music first, then your recordings (sound_cue_music)
"""
from __future__ import annotations

from pathlib import Path

from rostrum_core import RostrumError, Who, codes, joint, links, markers

from . import fields as F
from . import project_sound, retime, sound_cue_music
from .names import display_name

TRACK, TRACK_NAME = "cues_2d", "Cues from 2D"
LINK = Who.script("Rostrum2D")      # who keeps 2D's markers and video sound in step: never a person's Undo step


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
                                                        "id": mid, "owner": "2d"}}, _follow(doc, mid, layer_id)],
                 who, label="Sound cue marker")
    return name


def cue(folder, doc, layer_id: str, sound, who, at: float = 0.0, chosen: str = "", about: str = "",
        group: str | None = None) -> dict:
    """Put `sound` (a file, or a musical answer "note:<track>" / "hit:<track>": sound_cue_music) under layer `layer_id`, `at` seconds after its start, in the song that plays (`chosen`: the
    scene's soundtrack; empty = the main mix). `about`: the sound's name in the step's label (default: the file's).
    Returns {song, track, clip, marker, file}. Loud on any missing piece."""
    if not folder:
        raise RostrumError(codes.BAD_ARGUMENT, "sound.cue", "the document", "is not in a project folder")
    if not doc.has(layer_id) or doc.item(layer_id)["type"] not in F.LAYERS:
        raise RostrumError(codes.NOT_FOUND, "sound.cue", f'layer "{layer_id}"', "is not a layer of this document")
    music, file = sound_cue_music.is_music(str(sound)), Path(sound)
    if not music and not file.is_file():
        raise RostrumError(codes.NOT_FOUND, "sound.cue", f'sound "{sound}"', "is not a file",
                           hint="Pick one with inspect_sounds (Sound's library and your sound folders).")
    song = project_sound.song(folder, chosen)
    if song is None:
        raise RostrumError(codes.BAD_ARGUMENT, "sound.cue", "the project", "has no RostrumSound item to put the sound in",
                           hint="Make the project's sound in RostrumSound first (it owns every sound and mixes it).")
    with joint.step():                                  # the marker and the clip: one Undo step
        name = _marker(folder, doc, layer_id, who)
        snd = project_sound.open_song(folder, song["id"])   # live: one door with Sound's own window and 2D's Undo
        ids = {t["id"] for t in snd.data.get("tracks", [])}
        clip_id = _free_id(snd, f"cue_{layer_id}")
        when = f"#{name}" + (f"{at:+g}" if at else "")
        if music:
            calls, track = sound_cue_music.calls(snd, str(sound), when), str(sound).partition(":")[2]
        else:
            calls = [] if TRACK in ids else [{"op": "track.add", "args": {"id": TRACK, "name": TRACK_NAME}}]
            calls.append({"op": "clip.add", "target": [TRACK], "args": {"id": clip_id, "media": str(file), "at": when}})
            track = TRACK
        snd.apply(calls, who, label=f"Add a sound here: {about or file.stem} at {name}", session=group)
    return {"song": song["id"], "track": track, "clip": None if music else clip_id, "marker": name, "at": when,
            "file": "" if music else str(file), "music": str(sound) if music else ""}


def _free_id(snd, base: str) -> str:
    from rostrum_core.tree import index
    taken = set(index(snd.data, snd.kind.lists))
    return next(i for i in (base if n == 1 else f"{base}_{n}" for n in range(1, 10000)) if i not in taken)


def _follow(doc, mid: str, layer_id: str) -> dict:
    return {"op": "marker.follow", "target": [mid], "args": {"item": doc.item_id, "part": layer_id}}


def follow(folder, doc) -> list[str]:
    """Every marker following this document's layers back on its layer's start (rostrum_core.links: one change by LINK
    in the open step; none when all are in place). A cue whose layer is gone stays where it was. Cue markers made before
    markers could follow get their `follows` once. Returns the names moved."""
    if not folder:
        return []
    prefix = marker_id(doc.item_id, "")
    old = [_follow(doc, m["id"], m["id"][len(prefix):]) for m in markers.listing(folder)
           if m["id"].startswith(prefix) and not m.get("follows") and doc.has(m["id"][len(prefix):])]
    if old:
        markers.edit(folder, old, LINK, label="Sound cues follow their layers")
    return links.refresh(folder, LINK, docs={doc.item_id: doc}, only=[doc.item_id])


def choices(words: str = "", limit: int = 40, folder=None, chosen: str = "") -> list[dict]:
    """What to pick from, music first (apps/sound/PURPOSE.md): with no words, a note / hit on the song's own instruments
    (sound_cue_music, when the project has a song), then the person's own recordings; never an effect first. With
    words: the person's recordings, then Sound's installed library, all words matching. [{path, about, seconds, where}];
    a source that isn't there is skipped."""
    out = []
    if not words.strip():
        song = project_sound.song(folder, chosen) if folder else None
        if song:
            out += sound_cue_music.rows(project_sound.open_song(folder, song["id"]))
    from rostrum_sound import userlib
    for s in userlib.search(words=words or None, limit=limit)["sounds"]:
        if s.get("start", 0) == 0:                   # whole files only: a cue plays a file from its start
            out.append({"path": s["path"], "about": s["about"], "seconds": s.get("seconds"), "where": "Your sounds"})
    if words.strip():
        try:
            from rostrum_sound import library
            for p in library.find("recordings", words)[:limit]:
                d = library.describe(p)
                out.append({"path": d["path"], "about": d["about"], "seconds": d.get("seconds"), "where": "Library"})
        except FileNotFoundError:
            pass                                     # no library installed: the person's folders only
    return out[:limit]


def watch(doc, said) -> callable:
    """Keep this document's cue markers on their layers and its videos' own sound in Sound's song (sync_sound.py) after
    every change (the screen's window and the agent server both watch the document they hold). A failure is handed to
    `said` (the status line, the server's log) in plain words; the 2D change itself stands. Once at the start too (a
    video placed while no window was open). Returns the unsubscribe."""
    def keep():
        if not doc.folder:
            return
        try:
            follow(doc.folder, doc)
            from . import sync_sound
            sync_sound.sync(doc.folder, doc)
        except Exception as e:  # noqa: BLE001  never silent: said where the person or the agent reads it
            said(e.line() if hasattr(e, "line") else f"Error: 2D's sound in Sound: {e}")
    keep()
    return doc.subscribe(lambda ev: keep() if ev.kind in ("change", "reset") else None)
