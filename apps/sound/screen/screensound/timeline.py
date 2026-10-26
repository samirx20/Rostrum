"""What the Timeline shows, as plain data from the document's root (no Qt): one row per track with its notes,
hits and clips as blocks (seconds), the markers, the song's length and grid, and the piano roll of one track.

A track's hue is its own `colour` when set, else HUES (the one per-track colour list on the screen) by its place in
the song: `hue`, the one place every screen part (arrangement, piano roll, inspector) reads it from.
A clip without a length plays to the end of its file: the file's length is read once (and cached).
"""
from __future__ import annotations

import math
from functools import lru_cache
from operator import itemgetter

from rostrum_sound import clean_clips, names, roles, voice_lines
from rostrum_sound.doc import keys as K
from rostrum_sound.doc import media as mediafile
from rostrum_sound.doc import markers as mk
from rostrum_sound.doc import meter, tempo, times

from . import block_clock, groups, lanes, music_map, pick, timing
from . import block_memo, plugin_items
from .block_memo import BlockMemo
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
    total, peaks = media(clean_clips.played_file(c))
    dur = timing.length_sec(c["length"], root, timing.sec(c["at"], root, c["id"])) if c.get("length") is not None else max(total - c.get("in", 0), 0)
    if total and peaks:
        a, b = c.get("in", 0) / total, min(1.0, (c.get("in", 0) + dur) / total)
        peaks = peaks[int(a * len(peaks)):max(int(a * len(peaks)) + 1, int(b * len(peaks)))]
    return timing.sec(c["at"], root, c["id"]), max(dur, 0.05), peaks


def in_key_then(k: int, key) -> bool:
    """Is pitch `k` in the key playing (the one rule the roll's key shading uses too)? With no key, every pitch is."""
    return key is None or K.parse(key) is None or K.in_key(k, key)


def in_beats(item: dict, length=None) -> dict:
    """Where an item placed in beats is, in beats: {"atBeat": start} (and "endBeat": its end, when its `length` is in beats too).
    The screen places these through the tempo map itself (Tempo.js): a tempo change re-times them there, and their
    rows are not sent again (block_patch.text). Anything else ({}): its seconds."""
    at = item.get("at")
    if type(at) is not dict or "beat" not in at:
        return {}
    b = float(at["beat"])
    if length is None:
        return {"atBeat": b}
    return {"atBeat": b, "endBeat": b + float(length["beats"])} if type(length) is dict and "beats" in length else {}


NOTE_OWN = ("id", "type", "keys", "vel")        # what a note's block reads from the note alone (placed_note: the rest)


@lru_cache(maxsize=4096)
def spelled(ks: tuple, key) -> dict:
    """The names (and label) of the keys `ks` in `key` (Bb in D minor, not A#) and which are out of it. Shared by
    every block of that chord in that key: a block is never changed in place."""
    names = [timing.name(k, key) for k in ks]
    return {"names": names, "label": " ".join(names), "out": [not in_key_then(k, key) for k in ks]}


def placed_note(own: dict, n: dict, root: dict) -> dict:
    """A note's block: `own` (NOTE_OWN) placed on the song: its time in beats, its seconds, the key playing there."""
    t = timing.sec(n["at"], root, n["id"])
    return {**own, "t": t, "dur": timing.length_sec(n["dur"], root, t, n),
            **spelled(tuple(own["keys"]), K.key_at(root, t)), **in_beats(n, n["dur"])}


def note_block(n, root):
    return placed_note({"id": n["id"], "type": "note", "keys": timing.keys(n["pitch"]), "vel": n.get("vel", 0.8)}, n, root)


def again(root):
    """A note's block made before (for this note, or for it before it moved), placed on the song as it is now
    (block_memo.made's `again`): its pitch is not read again (about a quarter of making it; a hit's block is quicker
    to make than to copy, so hits are made). Everything the song gives it is read again: it equals note_block's."""
    return lambda n, b: placed_note(dict(zip(NOTE_OWN, _own(b))), n, root)


_own = itemgetter(*NOTE_OWN)


def hit_block(h, root):
    return {"id": h["id"], "type": "hit", "t": timing.sec(h["at"], root, h["id"]), "dur": HIT_SECONDS,
            "drum": str(h["drum"]), "label": str(h["drum"]), "vel": h.get("vel", 0.85), **in_beats(h)}


def tie_of(item: dict) -> dict | None:
    """The project marker an item's start is written on ("#logo lands+0.1" -> {name, offset}); None when it is not tied.
    A clip tied to a marker follows it when the marker moves (2D's "Add a sound here" writes its cues this way)."""
    parts = mk.parts(item.get("at"))
    return {"name": parts[0], "offset": parts[1], "unit": parts[2]} if parts else None


TIE_NAME = 14           # characters of a marker's name in the inspector's subtitle (the block shows it whole)


def tie_words(item: dict) -> str:
    """"tied to marker “logo lands”" (with "· 0.1 s after" when it starts off the marker); "" when not tied."""
    tie = tie_of(item)
    if not tie:
        return ""
    unit = "beats" if tie["unit"] == "beats" else "s"
    off = f" · {abs(tie['offset']):g} {unit} {'after' if tie['offset'] > 0 else 'before'}" if abs(tie["offset"]) > 1e-6 else ""
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


OWN = block_clock.OWN


clock = block_clock.clock      # what a note's or hit's block reads besides its own item (block_clock.py)


def blocks(track: dict, root: dict, memo: BlockMemo | None = None) -> list[dict]:
    """A track's blocks: notes, hits, clips, voice lines. `memo`: notes and hits not changed since are not made again
    (block_memo.py; the blocks are then shared: never changed in place)."""
    clips = layered([{**clip_block(c, root), **({"group": c["group"]} if c.get("group") else {})}
                     for c in plugin_items.known(track.get("clips", []))])
    notes = plugin_items.known(track.get("notes", []))
    held = block_memo.Same(notes) if any(n.get("dur") == times.NEXT for n in notes) else None   # reads its neighbours
    return (block_memo.made(memo, (track["id"], "notes"), notes, lambda n: note_block(n, root), held, again(root))
            + block_memo.made(memo, (track["id"], "hits"), plugin_items.known(track.get("hits", [])), lambda h: hit_block(h, root))
            + clips
            + [line_block(track, ln, root) for ln in plugin_items.known(track.get("lines", []))])


def drums_of(track: dict, memo: BlockMemo | None = None) -> list[str]:
    """The drum rows a track's piano roll shows: the synth kit's order first, then any others as they come. `memo`:
    the drums counted again only for the hits an edit changed (block_memo.tally)."""
    hits = track.get("hits", [])
    used = (set(memo.tally((track["id"], "drums"), hits, lambda h: str(h["drum"]))) if memo is not None
            else {str(h["drum"]) for h in hits})
    known = [d for d in [*names.SYNTH_DRUMS, *names.GM_DRUMS] if d in used]
    return list(dict.fromkeys(known + sorted(used - set(known))))


def roll_drums(track: dict, memo: BlockMemo | None = None) -> list[str]:
    """The rows of a drum track's piano roll: a synth drum kit shows all its drums (so the area is the kit, not three
    thin rows), then any other drum the track has hit."""
    used = drums_of(track, memo)
    return list(dict.fromkeys([*names.SYNTH_DRUMS, *used])) if track.get("instrument") == "kit" else used


def kind_of(track: dict) -> str:
    """What the piano roll draws for a track: "notes", "drums", "audio" (clips, voice lines) or "empty"."""
    if track.get("instrument") == "voice":
        return "audio"
    if track.get("instrument") in ("kit", "kitSfz") or track.get("hits"):
        return "drums"
    if track.get("instrument") not in (None, "none") or track.get("notes"):
        return "notes"
    return "audio" if track.get("clips") else "empty"


def icon_of(track: dict) -> str:
    """The small picture on a track's header: "voice" (a voice track), else its kind (notes, drums, audio). A track
    with no instrument and nothing on it yet takes sound (a recording, a file): it shows "audio" from the start."""
    kind = kind_of(track)
    return "voice" if track.get("instrument") == "voice" else "audio" if kind == "empty" else kind


def can_record(track: dict) -> bool:
    """A track takes a microphone or a keyboard unless it is a voice track (spoken lines are typed, not recorded)."""
    return track.get("instrument") != "voice"


def rows(root: dict, open_lanes: dict | None = None, folded=frozenset()) -> list[dict]:
    """The arrangement's rows: one per track (`track_row`), then the buses and the master as compact rows (`mix`:
    true) that hold only their automation lanes; a bus that tracks play into is a group header above them instead
    (groups.py), its tracks folded away when `folded` has it. `open_lanes` (track id -> (item id, lane)) adds `auto`:
    the automation lane drawn under that track's row."""
    return arrange(root, track_rows(root, open_lanes), open_lanes, folded)


def track_rows(root: dict, open_lanes: dict | None = None, made: dict | None = None,
               memo: BlockMemo | None = None) -> list[dict]:
    """Every track's row in song order. `made` (track id -> row): rows still current, taken as they are (a drag's
    step makes again only the tracks it changed, stepped.py); `memo`: in a row made again, only its changed notes
    and hits are (block_memo.py)."""
    made, open_lanes = made or {}, open_lanes or {}
    return [made.get(t["id"]) or track_row(t, i, root, open_lanes, memo) for i, t in enumerate(root.get("tracks", []))]


def arrange(root: dict, tracks: list[dict], open_lanes: dict | None, folded) -> list[dict]:
    """The track rows in drawing order with the group headers and the compact mix rows (made again: they are few)."""
    return groups.arrange(root, tracks, lanes.mix_rows(root, open_lanes or {}), folded)


def track_row(t: dict, i: int, root: dict, open_lanes: dict, memo: BlockMemo | None = None) -> dict:
    """A track's row: name, hue, mute / solo, kind, header icon, its blocks, and what places them across the row so
    it reads like a small piano roll (`span`: its lowest and highest key, notes by pitch; `drums`: its drum rows, in
    order; pick.lanes). The blocks are the roll's own (shared, never changed in place): a note above the span or a
    first hit on a new drum changes the row's layout only, never every block (that sent a drum row's 850 hits again
    on the first hit, ~40-70 ms on a 3-minute song)."""
    if plugin_items.is_plugin(t["type"]):
        return plugin_items.row(t, i, hue(t, i))
    bl = blocks(t, root, memo)
    ks = [k for b in bl if b["type"] == "note" for k in b["keys"]]
    pick.stack(bl)                       # overlapping clips / sounds share the lane in rows
    return {"id": t["id"], "name": t.get("name") or t["id"], "hue": hue(t, i),
            "span": [min(ks), max(ks)] if ks else [60, 60], "drums": drums_of(t, memo),
            "mute": bool(t.get("mute")), "solo": bool(t.get("solo")), "locked": bool(t.get("locked")), "kind": kind_of(t), "blocks": bl,
            "icon": icon_of(t), "canRecord": can_record(t), "canSolo": True, "canLane": True,
            "autoUsed": lanes.used(t),
            "auto": lanes.lane_data(t, root, *open_lanes[t["id"]]) if t["id"] in open_lanes else None}


def markers(root: dict) -> list[dict]:
    """The named markers by time. `named` is true when a section of the same name starts at the marker: the
    section bar already says it, so the marker band draws no second tag (the line through the rows stays)."""
    starts = {(s["name"], round(s["t"], 4)) for s in music_map.sections(root)}
    out = [{"id": m["id"], "name": name, "t": mk.time_of(root, name), "shared": bool(m.get("shared")),
            "colour": m.get("colour") or ""}
           for name, m in mk.items(root)]      # shared: the project's (dragged here, in 2D or with edit_markers)
    return sorted(({**m, "named": (m["name"], round(m["t"], 4)) in starts} for m in out), key=lambda m: m["t"])


EMPTY_BARS = 8              # a song always has room for at least this many bars to write in
SPARE_BARS = 2              # and, once it has sound, this many empty bars after the last sound


def song_length(root: dict, made: list[dict] | None = None, marks: list[dict] | None = None,
                memo: BlockMemo | None = None, least: float = 0.0) -> float:
    """The song's length on the screen (`song`'s): everything else `song` holds follows the tempo, meter and keys.
    `memo`: each row's last end kept, worked out again only from the blocks an edit changed (block_memo.last_end).
    `least`: where the picture ends (seconds): a song scored to picture has room for the whole picture before any
    music is written, so its cuts can be marked first (critic r7)."""
    if made is not None and memo is not None:
        ends = [memo.last_end((r["id"], "end"), r["blocks"]) for r in made if r["blocks"]]
    else:
        every = [r["blocks"] for r in made] if made is not None else [blocks(t, root) for t in root.get("tracks", [])]
        ends = [b["t"] + b["dur"] for bl in every for b in bl]
    ends += [m["t"] for m in (markers(root) if marks is None else marks)] + [s["end"] for s in music_map.sections(root)]
    ends.append(least)
    bar = meter.start_bar(root) * timing.spb(root)
    if root.get("length") is not None:
        length = timing.sec(root["length"], root)
    else:
        length = max(EMPTY_BARS, math.ceil(max(ends, default=0) / bar) + SPARE_BARS) * bar
    return max(length, 1.0)


def song(root: dict, made: list[dict] | None = None, marks: list[dict] | None = None, memo: BlockMemo | None = None,
         least: float = 0.0) -> dict:
    """The grid and length: what the ruler draws. Without a set length: room to write: the last sound rounded up
    to a whole bar plus SPARE_BARS, never under EMPTY_BARS (the mix itself still ends at its last sound + 2 s).
    `made`: the track rows already made (track_rows: their blocks are these; nothing is made twice); `marks`: the
    markers already read (`markers`: they read the project's shared markers)."""
    length = song_length(root, made, marks, memo, least)
    return {"length": length, "spb": timing.spb(root), "beatsPerBar": meter.start_per_bar(root),
            "beatUnit": meter.start_unit(root), "barBeats": meter.start_bar(root),
            "tempo": float(root.get("tempo", 120)), "tempoMap": [list(s) for s in tempo.segments(root)],   # (Tempo.js)
            **music_map.grid(root, length)}


def _sounds_best(track: dict) -> list[int]:
    """An empty track's roll opens on where its sound sounds best (roles.py: Sub bass E1-G3), else around middle C."""
    r = roles.ROLES.get(roles.key(track) or "")
    return [K.midi(r.low), K.midi(r.high)] if r and r.low else [60]


def roll(track: dict | None, root: dict, hue: str = HUES[0], play_lane: str = "sustain", keep: tuple | None = None,
         memo: BlockMemo | None = None) -> dict:
    """The piano roll of one track: its kind, the key range (notes: at least two octaves around what's there)
    or the drum rows, its blocks, and (notes) its playing lane `play_lane` (sustain, expression or bend). `keep` =
    (lo, hi) the keys already shown: the range only grows from it, so an edit never slides the rows under the pointer."""
    if track is None:
        return {"id": "", "name": "", "kind": "none", "blocks": [], "lo": 48, "hi": 72, "rowNames": [], "drums": [], "hue": hue}
    bl = blocks(track, root, memo)
    ks = [k for b in bl if b["type"] == "note" for k in b["keys"]] or _sounds_best(track)
    lo, hi = min(ks) - 4, max(ks) + 4
    if keep:                       # the keys already shown stay: the first note drawn in them adds no key row
        lo, hi = min(lo, keep[0]), max(hi, keep[1])
    if hi - lo < 24:
        mid = (lo + hi) // 2
        lo, hi = mid - 12, mid + 12
    # Whole octaves (C up to B): a note drawn a key past the edge rarely changes the range, and a range that changes
    # makes every key row on screen again (~18 ms of one press).
    lo, hi = max(0, lo // 12 * 12), min(127, -(-(hi + 1) // 12) * 12 - 1)
    if keep:
        lo, hi = min(lo, keep[0]), max(hi, keep[1])
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
            "lo": lo, "hi": hi, "rowNames": row_names, "drums": roll_drums(track, memo), "hue": hue,
            "played": lanes.played(track, root, play_lane) if kind_of(track) == "notes" else None}
