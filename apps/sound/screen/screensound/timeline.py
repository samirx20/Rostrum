"""What the Timeline shows, as plain data from the document's root (no Qt): one row per track with its notes,
hits and clips as blocks (seconds), the markers, the song's length and grid, and the piano roll of one track.

A track's hue is its own `colour` when set, else HUES (the one per-track colour list on the screen) by its place in
the song: `hue`, the one place every screen part (arrangement, piano roll, inspector) reads it from.
A clip without a length plays to the end of its file: the file's length is read once (and cached).
"""
from __future__ import annotations

import math
from functools import lru_cache

from rostrum_core import marker_times
from rostrum_sound import names, voice_lines
from rostrum_sound.doc import keys as K
from rostrum_sound.doc import markers as mk
from rostrum_sound.doc import meter

from . import groups, lanes, music_map, pick, timing
from .handles import level_y

# no blues: blue is the selection (Theme.accent)
HUES = ["#4fb5a5", "#e0a458", "#d27aa8", "#a0c167", "#b48ce0", "#c98c6b", "#d6c86c", "#e07a6b"]


def hue(track: dict, index: int) -> str:
    """The colour a track is drawn in: its own `colour`, else its place's hue."""
    return track.get("colour") or HUES[index % len(HUES)]


HIT_SECONDS = 0.12          # how long a drum hit's block is drawn
PEAKS = 48                  # waveform points per clip


@lru_cache(maxsize=256)
def media(path: str) -> tuple[float, tuple[float, ...]]:
    """(seconds, peaks 0..1) of an audio file; (0, ()) when it can't be read (the render reports why)."""
    try:
        import numpy as np
        import soundfile as sf
        data, rate = sf.read(path, always_2d=True, dtype="float32")
    except Exception:  # noqa: BLE001  unreadable here; the engine's render names the problem loudly
        return 0.0, ()
    mono = np.abs(data).max(axis=1)
    if not len(mono):
        return 0.0, ()
    chunks = np.array_split(mono, min(PEAKS, len(mono)))
    peaks = np.array([c.max() for c in chunks])
    top = float(peaks.max()) or 1.0
    return len(mono) / rate, tuple(round(float(p / top), 3) for p in peaks)


def clip_span(c: dict, root: dict) -> tuple[float, float, tuple]:
    """(start, seconds, peaks) of a clip, as it plays."""
    total, peaks = media(c["media"])
    dur = timing.length_sec(c["length"], root, timing.sec(c["at"], root, c["id"])) if c.get("length") is not None else max(total - c.get("in", 0), 0)
    if total and peaks:
        a, b = c.get("in", 0) / total, min(1.0, (c.get("in", 0) + dur) / total)
        peaks = peaks[int(a * len(peaks)):max(int(a * len(peaks)) + 1, int(b * len(peaks)))]
    return timing.sec(c["at"], root, c["id"]), max(dur, 0.05), peaks


def in_key_then(k: int, key) -> bool:
    """Is pitch `k` in the key playing (the one rule the roll's key shading uses too)? With no key, every pitch is."""
    return key is None or K.parse(key) is None or K.in_key(k, key)


def note_block(n, root):
    ks = timing.keys(n["pitch"])
    t = timing.sec(n["at"], root, n["id"])
    key = K.key_at(root, t)                     # spelled in the key playing there (Bb in D minor, not A#)
    label = " ".join(timing.name(k, key) for k in ks)
    return {"id": n["id"], "type": "note", "t": t, "dur": timing.length_sec(n["dur"], root, t, n), "keys": ks, "names": [timing.name(k, key) for k in ks], "label": label, "vel": n.get("vel", 0.8),
            "out": [not in_key_then(k, key) for k in ks]}


def hit_block(h, root):
    return {"id": h["id"], "type": "hit", "t": timing.sec(h["at"], root, h["id"]), "dur": HIT_SECONDS,
            "drum": str(h["drum"]), "label": str(h["drum"]), "vel": h.get("vel", 0.85)}


def tie_of(item: dict) -> dict | None:
    """The project marker an item's start is written on ("#logo lands+0.1" -> {name, offset}); None when it is not tied.
    A clip tied to a marker follows it when the marker moves (2D's "Add a sound here" writes its cues this way)."""
    parts = marker_times.split(item.get("at"))
    return {"name": parts[0], "offset": parts[1]} if parts else None


TIE_NAME = 14           # characters of a marker's name in the inspector's subtitle (the block shows it whole)


def tie_words(item: dict) -> str:
    """"tied to marker “logo lands”" (with "· 0.1 s after" when it starts off the marker); "" when not tied."""
    tie = tie_of(item)
    if not tie:
        return ""
    off = f" · {abs(tie['offset']):g} s {'after' if tie['offset'] > 0 else 'before'}" if abs(tie["offset"]) > 1e-6 else ""
    name = tie["name"] if len(tie["name"]) <= TIE_NAME else tie["name"][:TIE_NAME - 1].rstrip() + "…"
    return f"tied to marker “{name}”{off}"


def clip_block(c, root):
    t, dur, peaks = clip_span(c, root)
    label = c["media"].replace("\\", "/").rsplit("/", 1)[-1]
    if tie_of(c):
        label = f'{tie_of(c)["name"]} · {label}'                     # the marker it is tied to, then the sound
    dur *= c.get("stretch", 1)      # a stretched clip lasts length × stretch
    return {"id": c["id"], "type": "clip", "t": t, "dur": dur, "label": label, "peaks": list(peaks),
            "fadeIn": min(c.get("fadeIn", 0), dur), "fadeOut": min(c.get("fadeOut", 0), dur),
            "volume": c.get("volume", 1), "levelY": level_y(c.get("volume", 1)),      # the level line (handles.py)
            **({"tie": tie_of(c)["name"]} if tie_of(c) else {})}                         # a marker tag on the block


SOUND_SECONDS = {"click": 0.08, "hit": 1.2}       # designed sounds without a length: how long their block is drawn


def sound_block(sd, root):
    """A designed sound, drawn as a clip with its design's name (its length, or the tail, or a short default)."""
    dur = sd.get("dur") or sd.get("tail") or SOUND_SECONDS.get(sd["design"], 0.5)
    return {"id": sd["id"], "type": "sound", "t": timing.sec(sd["at"], root, sd["id"]), "dur": float(dur),
            "label": spaced_design(sd["design"]), "peaks": []}


def spaced_design(d: str) -> str:
    return {"subDrop": "Sub drop", "hit": "Impact"}.get(d, d.capitalize())


def line_block(track, ln, root):
    """A voice line, drawn as a clip on its take (its words as the label); before its take is made, a block as long
    as the words would take to say (~0.4 s a word), marked "not made"."""
    take = voice_lines.take_of(track, ln)
    t = timing.sec(ln["at"], root, ln["id"])
    if take is None:
        return {"id": ln["id"], "type": "line", "t": t, "dur": max(0.4 * len(ln["text"].split()), 0.5),
                "label": f'not made · {ln["text"]}', "peaks": []}
    total, peaks = media(take.file)
    return {"id": ln["id"], "type": "line", "t": t, "dur": max(total, 0.05), "label": ln["text"], "peaks": list(peaks)}


def layered(clips: list[dict]) -> list[dict]:
    """A layer group reads as one sound: its earliest clip is labelled "<group> · n layers", the others carry no
    label (they lie under it), and every block knows its group."""
    groups: dict[str, list[dict]] = {}
    for b in clips:
        if b.get("group"):
            groups.setdefault(b["group"], []).append(b)
    for g, members in groups.items():
        first = min(members, key=lambda b: b["t"])
        for b in members:
            b["label"] = f"{g} · {len(members)} layers" if b is first else ""
    return clips


def blocks(track: dict, root: dict) -> list[dict]:
    clips = layered([{**clip_block(c, root), **({"group": c["group"]} if c.get("group") else {})}
                     for c in track.get("clips", [])])
    return ([note_block(n, root) for n in track.get("notes", [])]
            + [hit_block(h, root) for h in track.get("hits", [])]
            + clips
            + [line_block(track, ln, root) for ln in track.get("lines", [])]
            + [sound_block(sd, root) for sd in track.get("sounds", [])])


def drums_of(track: dict) -> list[str]:
    """The drum rows a track's piano roll shows: the synth kit's order first, then any others as they come."""
    used = {str(h["drum"]) for h in track.get("hits", [])}
    known = [d for d in [*names.SYNTH_DRUMS, *names.GM_DRUMS] if d in used]
    return list(dict.fromkeys(known + sorted(used - set(known))))


def roll_drums(track: dict) -> list[str]:
    """The rows of a drum track's piano roll: a synth drum kit shows all its drums (so the area is the kit, not three
    thin rows), then any other drum the track has hit."""
    used = drums_of(track)
    return list(dict.fromkeys([*names.SYNTH_DRUMS, *used])) if track.get("instrument") == "kit" else used


def kind_of(track: dict) -> str:
    """What the piano roll draws for a track: "notes", "drums", "audio" (clips, voice lines) or "empty"."""
    if track.get("instrument") == "voice":
        return "audio"
    if track.get("instrument") in ("kit", "kitSfz") or track.get("hits"):
        return "drums"
    if track.get("instrument") not in (None, "none") or track.get("notes"):
        return "notes"
    return "audio" if track.get("clips") or track.get("sounds") else "empty"


def rows(root: dict, open_lanes: dict | None = None, folded=frozenset()) -> list[dict]:
    """One row per track for the arrangement: name, hue, mute / solo, kind, and its blocks with lanes 0..1 (top to
    bottom: notes by pitch, one per key of a chord; hits by drum row) so a row reads like a small piano roll.
    `open_lanes` (track id -> (item id, lane)) adds `auto`: the automation lane drawn under that track's row.
    The buses and the master follow as compact rows (`mix`: true) that hold only their automation lanes; a bus that
    tracks play into is a group header above them instead (groups.py), its tracks folded away when `folded` has it."""
    out = []
    for i, t in enumerate(root.get("tracks", [])):
        bl = blocks(t, root)
        ks = [k for b in bl if b["type"] == "note" for k in b["keys"]]
        lo, hi = (min(ks), max(ks)) if ks else (60, 60)
        drums = drums_of(t)
        for b in bl:
            if b["type"] == "note":
                b["lanes"] = [0.5 if hi == lo else 1 - (k - lo) / (hi - lo) for k in b["keys"]]
            elif b["type"] == "hit":
                b["lanes"] = [drums.index(b["drum"]) / max(len(drums) - 1, 1)]
        pick.stack(bl)                       # overlapping clips / sounds share the lane in rows
        out.append({"id": t["id"], "name": t.get("name") or t["id"], "hue": hue(t, i),
                    "mute": bool(t.get("mute")), "solo": bool(t.get("solo")), "locked": bool(t.get("locked")), "kind": kind_of(t), "blocks": bl,
                    "autoUsed": lanes.used(t),
                    "auto": lanes.lane_data(t, root, *open_lanes[t["id"]]) if t["id"] in (open_lanes or {}) else None})
    return groups.arrange(root, out, lanes.mix_rows(root, open_lanes or {}), folded)


def markers(root: dict) -> list[dict]:
    """The named markers by time. `named` is true when a section of the same name starts at the marker: the
    section bar already says it, so the marker band draws no second tag (the line through the rows stays)."""
    starts = {(s["name"], round(s["t"], 4)) for s in music_map.sections(root)}
    out = [{"id": m["id"], "name": name, "t": mk.time_of(root, name), "shared": bool(m.get("shared"))}
           for name, m in mk.items(root)]      # shared: the project's (dragged here, in 2D or with edit_markers)
    return sorted(({**m, "named": (m["name"], round(m["t"], 4)) in starts} for m in out), key=lambda m: m["t"])


EMPTY_BARS = 8              # a song always has room for at least this many bars to write in
SPARE_BARS = 2              # and, once it has sound, this many empty bars after the last sound


def song(root: dict) -> dict:
    """The grid and length: what the ruler draws. Without a set length: room to write: the last sound rounded up
    to a whole bar plus SPARE_BARS, never under EMPTY_BARS (the mix itself still ends at its last sound + 2 s)."""
    ends = [b["t"] + b["dur"] for t in root.get("tracks", []) for b in blocks(t, root)]
    ends += [m["t"] for m in markers(root)] + [s["end"] for s in music_map.sections(root)]
    bar = meter.start_bar(root) * timing.spb(root)
    if root.get("length") is not None:
        length = timing.sec(root["length"], root)
    else:
        length = max(EMPTY_BARS, math.ceil(max(ends, default=0) / bar) + SPARE_BARS) * bar
    length = max(length, 1.0)
    return {"length": length, "spb": timing.spb(root), "beatsPerBar": meter.start_per_bar(root),
            "beatUnit": meter.start_unit(root), "barBeats": meter.start_bar(root),
            "tempo": float(root.get("tempo", 120)), **music_map.grid(root, length)}


def roll(track: dict | None, root: dict, hue: str = HUES[0], play_lane: str = "sustain") -> dict:
    """The piano roll of one track: its kind, the key range (notes: at least two octaves around what's there)
    or the drum rows, its blocks, and (notes) its playing lane `play_lane` (sustain, expression or bend)."""
    if track is None:
        return {"id": "", "name": "", "kind": "none", "blocks": [], "lo": 48, "hi": 72, "rowNames": [], "drums": [], "hue": hue}
    bl = blocks(track, root)
    ks = [k for b in bl if b["type"] == "note" for k in b["keys"]] or [60]
    lo, hi = min(ks) - 4, max(ks) + 4
    if hi - lo < 24:
        mid = (lo + hi) // 2
        lo, hi = mid - 12, mid + 12
    lo, hi = max(0, lo), min(127, hi)
    # The rows' names, by the one speller, once per key in force: [{t, names}] from time 0 (the key before the
    # first change, or none) and at each key change. The screen reads the entry at the view's left edge.
    # `inKey` is the same per row: false for a row outside that key (shaded darker); all true with no key.
    def spell(key):
        rows = range(hi, lo - 1, -1)
        return {"names": [timing.name(k, key) for k in rows],
                "inKey": [in_key_then(k, key) for k in rows],
                "root": K.parse(key)[0] if key is not None and K.parse(key) is not None else -1}   # the tonic's pitch class
    row_names = [{"t": 0.0, **spell(K.key_at(root, 0.0))}]
    row_names += [{"t": c["t"], **spell(c["key"])} for c in music_map.key_changes(root) if c["t"] > 0]
    return {"id": track["id"], "name": track.get("name") or track["id"], "kind": kind_of(track), "blocks": bl,
            "lo": lo, "hi": hi, "rowNames": row_names, "drums": roll_drums(track), "hue": hue,
            "played": lanes.played(track, root, play_lane) if kind_of(track) == "notes" else None}
