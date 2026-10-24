"""MIDI files in and out of a Sound document, and a MIDI keyboard take (`keyboard.py`).

    calls, skipped = import_calls(doc.data, "song.mid")        # the operations an import is: apply as one change
    doc.apply(calls, who, label="Import MIDI")                  # one undo step
    skipped = export(doc.data, "renders/cue/cue.mid")           # what MIDI can't hold is listed, never dropped quietly

An import adds tracks (one per MIDI track; drums on channel 10 become drum hits; the pedal, expression, mod wheel
and pitch wheel become the track's sustain / dynamics / vibrato / bend lanes), markers and sections; with
`song_map=True` (the default) the file's tempo map, time signature and key changes replace the document's. All in
beats, so the notes follow the tempo map. Our own reader and writer (smf_in.py / smf_out.py): no dependency.
"""
from __future__ import annotations

import re

from rostrum_core.tree import index

from ..doc import markers
from ..doc.registry import LISTS
from . import smf_in, smf_out
from .song import from_events

SAFE = re.compile(r"[^A-Za-z0-9_.\-]+")


def read(path) -> dict:
    """The file as a song in beats (`song.py`)."""
    return from_events(*smf_in.read_events(path))


def _free(word: str, taken: set, fallback: str) -> str:
    base = SAFE.sub("_", word).strip("_.-")[:48] or fallback
    out, n = base, 1
    while out in taken:
        n += 1
        out = f"{base}_{n}"
    taken.add(out)
    return out


def calls_for(root: dict, song: dict, song_map: bool = True, skipped: list | None = None) -> list[dict]:
    """The operation calls that put `song` into the document whose data is `root`. A file's marker named like a project
    marker is left out (the project's one already says it) and said in `skipped`."""
    taken = set(index(root, LISTS))
    calls = []
    if song_map:
        calls.append({"op": "doc.set", "target": ["root"], "args": {"tempo": song["tempo"],
                                                                    "beatsPerBar": song["beatsPerBar"],
                                                                    "beatUnit": song["beatUnit"]}})
        old = [i for k in ("tempos", "meters", "keys") for i in root.get(k, [])]
        calls += [{"op": f"{i['type']}.remove", "target": [i["id"]]} for i in old]
        calls += [{"op": "tempo.add", "args": {"at": {"beat": b}, "bpm": bpm}} for b, bpm in song["tempos"]]
        calls += [{"op": "meter.add", "args": {"at": {"beat": b}, "beatsPerBar": per, "beatUnit": unit}}
                  for b, per, unit in song["meters"]]
        calls += [{"op": "key.add", "args": {"at": {"beat": b}, "key": k}} for b, k in song["keys"]]
    names = {n for n, _ in markers.items(root)}
    shared = {markers.key(r["name"]) for r in markers.project_rows()}
    for b, name in song["markers"]:
        if markers.key(name) in shared:
            (skipped if skipped is not None else []).append(f'marker "{name}" left out: the project already has a marker of that name')
            continue
        calls.append({"op": "marker.add", "args": {"name": _free(name, names, "marker"), "at": {"beat": b}}})
    parts = {s.get("name") for s in root.get("sections", [])}
    for name, b0, b1 in song["sections"]:
        calls.append({"op": "section.add", "args": {"name": _free(name, parts, "section"), "at": {"beat": b0},
                                                    "end": {"beat": b1}}})
    for t in song["tracks"]:
        tid = _free(t["name"].lower(), taken, "midi")
        kind = "builtIn" if "builtIn" in t else "kit"
        calls.append({"op": "track.add", "args": {"id": tid, "name": t["name"], "instrument": kind, kind: t[kind]}})
        if t["notes"]:
            calls.append({"op": "note.add_many", "target": [tid], "args": {"notes": t["notes"]}})
        if t["hits"]:
            calls.append({"op": "hit.add_many", "target": [tid], "args": {"hits": t["hits"]}})
        calls += [{"op": "automation.set", "target": [tid], "args": {"lane": ln, "points": pts}}
                  for ln, pts in t.get("lanes", {}).items()]
        if "bendRange" in t:            # after the bend lane: the range is a setting of a track that has one
            calls.append({"op": "track.set", "target": [tid], "args": {"bendRange": t["bendRange"]}})
    return calls


def import_calls(root: dict, path, song_map: bool = True) -> tuple[list[dict], list[str]]:
    """(calls, what was skipped and why) for importing the MIDI file at `path`."""
    song = read(path)
    skipped = list(song["skipped"])
    return calls_for(root, song, song_map, skipped), skipped


def export(root: dict, path) -> list[str]:
    """Write the document's notes, hits, tempo map, keys, markers and sections as a .mid; returns what was skipped."""
    return smf_out.write(root, path)
