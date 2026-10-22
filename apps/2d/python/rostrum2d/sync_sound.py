"""A video layer's own sound (UX_SPEC 3.28 Sync sound, 3.27 Video layers): passed to RostrumSound, which mixes it
(AGENTS.md rule 9: 2D never mixes). Each video layer whose file has a sound stream has one clip in the song that plays
(project_sound.py), on the track "Video sound from 2D": the video's own file, timed by a shared marker on the layer's
start ("Clip · video sound", id `mk_vs_<item>_<layer>`, rule 8), `in` = the layer's Clip starts at, `length` = what of
the file the bar shows (its length × Speed; a Speed other than 1 plays tape-style, Sound's `pitch`). Loop plays it once.

`sync` makes the song match the document after any 2D change (sound_cues.watch): a moved bar moves the marker, a
trimmed bar or a new Clip starts at re-sets the clip, a deleted layer takes its clip and marker away. Every change is
LINK's (sound_cues.LINK), never a person's Undo step: Undo of the 2D change brings the sound back in step. The level is
Sound's (`clip.set {volume}` in the song: the Video sound row's mute, Sound's own tools for agents); `sync` never
touches it. No project sound: nothing to sync (the row says so). No Qt.
"""
from __future__ import annotations

import math
from pathlib import Path

from rostrum_core import markers

from . import grain, project_sound, retime, video
from .video_audio import has_audio
from .names import display_name
from .sound_cues import LINK

TRACK, TRACK_NAME = "video_2d", "Video sound from 2D"


def marker_id(item: str, layer: str) -> str:
    return f"mk_vs_{item}_{layer}"


def clip_id(item: str, layer: str) -> str:
    return f"vs_{item}_{layer}"


def wanted(folder, doc) -> dict:
    """{layer id: {layer, name, file, at, in, length, pitch}} for every video layer whose file has sound, in composition
    seconds (markers and timed groups counted, retime.timed). A missing file is skipped (its layer says so already)."""
    out, times = {}, markers.times(folder)
    for comp in doc.data.get("comps", []):
        dur = float(comp.get("duration", 0.0))
        walk = [retime.timed(comp, times, comp.get("fps", 30))]
        while walk:
            node = walk.pop()
            for layer in node.get("layers", []):
                walk.append(layer)
                if layer.get("type") != "video" or grain.is_recipe(layer.get("src", "")):
                    continue
                try:
                    path = video.source(layer, Path(folder))
                except (ValueError, FileNotFoundError):
                    continue
                if not has_audio(path):
                    continue
                start, end = float(layer.get("start", 0.0)), min(float(layer.get("end", dur)), dur)
                speed, shown = float(layer.get("speed", 1.0)) or 1.0, max(start, 0.0)    # before 0 s: not heard
                if end - shown <= 1e-6:
                    continue
                out[layer["id"]] = {"layer": layer["id"], "name": display_name(layer), "file": str(path),
                                    "at": round(shown, 6),
                                    "in": round(float(layer.get("offset", 0.0)) + (shown - start) * speed, 6),
                                    "length": round((end - shown) * speed, 6),
                                    "pitch": round(12 * math.log2(speed), 4) if abs(speed - 1) > 1e-6 else 0.0}
    return out


def sync(folder, doc) -> list[str]:
    """The song (and the shared markers) made to match the document's video layers; returns what changed, in words."""
    if not folder or not doc.item_id:
        return []
    song = project_sound.song(folder, _soundtrack(doc))
    if song is None:
        return []
    want = wanted(folder, doc)
    snd = project_sound.open_song(folder, song["id"])
    have = {c["id"]: c for t in snd.data.get("tracks", []) if t["id"] == TRACK for c in t.get("clips", [])}
    prefix = clip_id(doc.item_id, "")
    names = _markers(folder, doc, want)
    calls, said = [], []
    if want and not any(t["id"] == TRACK for t in snd.data.get("tracks", [])):
        calls.append({"op": "track.add", "args": {"id": TRACK, "name": TRACK_NAME}})
    for lid, w in want.items():
        args = {"media": w["file"], "at": f'#{names[lid]}', "in": w["in"], "length": w["length"], "pitch": w["pitch"]}
        cid, now = clip_id(doc.item_id, lid), have.get(clip_id(doc.item_id, lid))
        if now is None:
            calls.append({"op": "clip.add", "target": [TRACK], "args": {"id": cid, **args}})
            said.append(f"{w['name']}: its sound is in Sound")
        elif any(_differs(now.get(k), v) for k, v in args.items()):
            calls.append({"op": "clip.set", "target": [cid], "args": args})
    gone = [cid for cid in have if cid.startswith(prefix) and cid[len(prefix):] not in want]
    if gone:
        calls.append({"op": "clip.remove", "target": gone})
        said.append(f"{len(gone)} video sound(s) taken out of Sound")
    if calls:
        snd.apply(calls, LINK, label="Video sound follows its layer")
    stale = [m["id"] for m in markers.listing(folder)
             if m["id"].startswith(marker_id(doc.item_id, "")) and m["id"][len(marker_id(doc.item_id, "")):] not in want]
    if stale:                                        # after the clips that used them are gone (the song's check)
        markers.edit(folder, [{"op": "marker.remove", "target": stale}], LINK, label="Video sound markers")
    return said


def _differs(a, b) -> bool:
    if isinstance(b, float):
        return a is None and b != 0.0 or a is not None and abs(float(a) - b) > 1e-6
    return a != b


def _markers(folder, doc, want: dict) -> dict:
    """Each wanted layer's marker name, made or moved to the layer's start first (one change by LINK)."""
    rows = {m["id"]: m for m in markers.listing(folder)}
    taken, calls, names = {m["name"].lower() for m in rows.values()}, [], {}
    for lid, w in want.items():
        mid = marker_id(doc.item_id, lid)
        if mid in rows:
            names[lid] = rows[mid]["name"]
            if abs(float(rows[mid]["at"]) - w["at"]) > 1e-6:
                calls.append({"op": "marker.move", "target": [mid], "args": {"at": w["at"]}})
            continue
        base = f"{w['name']} · video sound"
        name = next(n for n in (base if i == 1 else f"{base} {i}" for i in range(1, 1000)) if n.lower() not in taken)
        taken.add(name.lower())
        names[lid] = name
        calls.append({"op": "marker.add", "args": {"name": name, "at": w["at"], "id": mid, "owner": "2d"}})
    if calls:
        markers.edit(folder, calls, LINK, label="Video sound markers")
    return names


def _soundtrack(doc) -> str:
    comps = doc.data.get("comps", [])
    return comps[0].get("soundtrack", "") if comps else ""
