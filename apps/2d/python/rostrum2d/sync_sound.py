"""A video layer's own sound (UX_SPEC 3.28 Sync sound, 3.27 Video layers): passed to RostrumSound, which mixes it
(AGENTS.md rule 9: 2D never mixes). Each video layer whose file has a sound stream has one clip in the song that plays
(project_sound.py), on the track "Video sound from 2D": the video's own file, timed by a shared marker on the layer's
first heard moment ("Clip · video sound", id `mk_vs_<item>_<layer>`, rule 8), `in` = the layer's Clip starts at,
`length` = what of the file the bar shows (its length × Speed; a Speed other than 1 plays tape-style, Sound's `pitch`),
stopping at the file's end as the picture holds its last frame. A looped layer plays one clip per time round
(`vs_<item>_<layer>~2` … on "#<marker>+<seconds>"), wrapping where the picture wraps (video.pick). A layer inside a
group is heard only while the group shows it (the group's own start and end, as the engine draws it).

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

from . import grain, looping, project_sound, retime, video, video_audio
from .names import display_name
from .sound_cues import LINK

TRACK, TRACK_NAME = "video_2d", "Video sound from 2D"
ROUND = "~"                         # a looped layer's later clips: vs_<item>_<layer>~2, ~3 …
MAX_ROUNDS = 2000                   # more clips than this for one layer is said, never cut silently


def marker_id(item: str, layer: str) -> str:
    return f"mk_vs_{item}_{layer}"


def clip_id(item: str, layer: str) -> str:
    return f"vs_{item}_{layer}"


def layer_clips(song_doc, item: str, layer: str) -> list[str]:
    """The ids of one layer's clips in the song (one, or one per time round when it loops): what its mute sets."""
    base = clip_id(item, layer)
    return [c["id"] for t in song_doc.data.get("tracks", []) if t["id"] == TRACK for c in t.get("clips", [])
            if c["id"] == base or c["id"].startswith(base + ROUND)]


def wanted(folder, doc) -> dict:
    """{layer id: {layer, name, file, at, start, pitch, pieces: [{after, in, length}]}} for every video layer whose file has
    sound, in composition seconds (markers and timed groups counted, retime.timed). `at` is the first moment heard: the
    layer's start, cut to the comp and to every group it sits in. Each piece is a stretch of the file, `after` seconds
    after `at`. A missing file is skipped (its layer says so already)."""
    out, times = {}, markers.times(folder)
    for comp in doc.data.get("comps", []):
        dur, fps = float(comp.get("duration", 0.0)), float(comp.get("fps", 30))
        walk = [(retime.timed(comp, times, fps), 0.0, dur)]          # before 0 s: not heard
        while walk:
            node, lo, hi = walk.pop()
            for layer in node.get("layers", []):
                a, b = max(lo, float(layer.get("start", 0.0))), min(hi, float(layer.get("end", dur)))
                walk.append((layer, a, b))           # a group shows its children only between its own start and end
                if layer.get("type") != "video" or grain.is_recipe(layer.get("src", "")) or b - a <= 1e-6:
                    continue
                try:
                    path = video.source(layer, Path(folder))
                except (ValueError, FileNotFoundError):
                    continue
                if not video_audio.has_audio(path):
                    continue
                speed = float(layer.get("speed", 1.0)) or 1.0
                pieces = _pieces(layer, a, b, speed, video_audio.length(path), fps)
                if pieces:
                    out[layer["id"]] = {"layer": layer["id"], "name": display_name(layer), "file": str(path),
                                        "at": round(a, 6), "start": float(layer.get("start", 0.0)), "pieces": pieces,
                                        "pitch": round(12 * math.log2(speed), 4) if abs(speed - 1) > 1e-6 else 0.0}
    return out


def _pieces(layer: dict, a: float, b: float, speed: float, file_len: float, fps: float) -> list[dict]:
    """The stretches of the file heard from `a` to `b` (comp seconds): one, ending where the file does; a looped layer
    starts again where its picture does (the decoded frames' length, video.pick). Unknown length: one, as the bar."""
    # Sound can't play backwards: a ping-pong picture keeps its sound looping forward (as Loop), never reversed.
    wrap, loop = (round(file_len * fps) / fps if file_len > 0 else 0.0), looping.mode_of(layer.get("loop")) != "off"
    pos, t, out = float(layer.get("offset", 0.0)) + (a - float(layer.get("start", 0.0))) * speed, a, []
    while b - t > 1e-6:
        here = pos % wrap if loop and wrap else pos
        size = min((b - t) * speed, wrap - here) if wrap else (b - t) * speed
        if size > 1e-4:
            out.append({"after": round(t - a, 6), "in": round(here, 6), "length": round(size, 6)})
        if not (loop and wrap):
            break
        if len(out) > MAX_ROUNDS:
            raise RuntimeError(f"{layer['id']}: a looped video's sound would need over {MAX_ROUNDS} clips in Sound "
                               f'(a {wrap:g} s clip over {b - a:g} s); shorten the layer or turn Loop off')
        t, pos = t + max(size, 1e-4) / speed, pos + max(size, 1e-4)
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
    keep = set()
    for lid, w in want.items():
        base = clip_id(doc.item_id, lid)
        level = next((have[c]["volume"] for c in layer_clips(snd, doc.item_id, lid) if "volume" in have[c]), None)
        for n, p in enumerate(w["pieces"]):
            cid = base if n == 0 else f"{base}{ROUND}{n + 1}"
            keep.add(cid)
            at = f'#{names[lid]}' + (f'+{p["after"]:.6f}'.rstrip("0").rstrip(".") if p["after"] > 1e-6 else "")
            args = {"media": w["file"], "at": at, "in": p["in"], "length": p["length"], "pitch": w["pitch"]}
            now = have.get(cid)
            if now is None:                          # a new time round keeps the layer's level (its mute)
                calls.append({"op": "clip.add", "target": [TRACK],
                              "args": {"id": cid, **args, **({"volume": level} if level is not None else {})}})
                if n == 0:
                    said.append(f"{w['name']}: its sound is in Sound")
            elif any(_differs(now.get(k), v) for k, v in args.items()):
                calls.append({"op": "clip.set", "target": [cid], "args": args})
    gone = [cid for cid in have if cid.startswith(prefix) and cid not in keep]
    if gone:
        calls.append({"op": "clip.remove", "target": gone})
        said.append(f"{len(gone)} video sound clip(s) taken out of Sound")
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
