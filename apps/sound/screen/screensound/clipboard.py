"""Copy and paste of notes, drum hits, clips and voice lines (no Qt): Ctrl+C keeps the selected items with their
times relative to the first one and the tracks they came from; Ctrl+V puts them back at the playhead on the selected
track (several tracks copied: that track and the ones below it, in order; nothing selected: the tracks they came
from). Paste is operations an agent calls too (`note.add_many`, `hit.add_many`, `clip.add`, `line.add`), all in one
change. Times keep their form: beats stay beats, a time on a marker stays on it with a new offset.
"""
from __future__ import annotations

import copy

from rostrum_core import RostrumError, codes
from rostrum_sound.doc import media
from rostrum_sound.doc import select_time as ST
from rostrum_sound.doc.fields import DEFAULTS
from rostrum_sound.doc.shift import write_like

from .timeline import kind_of

KINDS = ("note", "hit", "clip", "line")
MANY = {"note": "notes", "hit": "hits"}     # kinds with an add_many (one call per track)
FITS = {"note": ("notes", "empty"), "hit": ("drums", "empty"), "clip": ("audio", "empty", "notes", "drums"),
        "line": ("audio",)}
_KEPT = [{"items": [], "tracks": []}]       # the one clipboard of this run: every song open in the app shares it


def kept() -> dict:
    return _KEPT[0]


def keep(board: dict) -> dict:
    _KEPT[0] = board
    return board


WHAT = {"note": "notes", "hit": "drum hits", "clip": "clips", "line": "voice lines"}


def copy_items(doc, ids) -> dict:
    """{"items": [{kind, track, offset, fields}], "tracks": [source track ids in song order]}; [] items = nothing."""
    root = doc.data
    items = [doc.item(i) for i in ids if doc.item(i)["type"] in KINDS]
    if not items:
        return {"items": [], "tracks": []}
    first = min(ST.start_of(root, it) for it in items)
    order = [t["id"] for t in root.get("tracks", [])]
    out = [{"kind": it["type"], "track": doc.parent_of(it["id"])[0], "offset": ST.start_of(root, it) - first,
            "fields": {k: copy.deepcopy(v) for k, v in it.items() if k not in ("id", "type", "effects")}}
           for it in items]
    with media.of(doc):                     # a clip's sound as a full path: it can be pasted into another song
        for o in out:
            if o["kind"] == "clip" and isinstance(o["fields"].get("media"), str):
                o["fields"]["media"] = media.file(o["fields"]["media"])
    return {"items": out, "tracks": sorted({o["track"] for o in out}, key=order.index)}


def paste_calls(doc, board: dict, at: float, onto: str = "") -> list[dict]:
    """The calls that paste `board` with its first item at `at` seconds, onto `onto` and the tracks below it."""
    order = [t["id"] for t in root_tracks(doc)]
    if onto:
        start = order.index(onto)
        if start + len(board["tracks"]) > len(order):
            raise RostrumError(codes.BAD_ARGUMENT, "paste", f"{len(board['tracks'])} tracks",
                               f"don't fit from \"{onto}\" down: there are only {len(order) - start} tracks there",
                               hint="Select a higher track, or add tracks first.")
        where = dict(zip(board["tracks"], order[start:]))
    else:
        where = {t: t for t in board["tracks"]}
    per: dict[tuple[str, str], list[dict]] = {}
    for it in board["items"]:
        track = where[it["track"]]
        if not doc.has(track):
            raise RostrumError(codes.NOT_FOUND, "paste", f'track "{track}"', "is gone", hint="Select a track to paste onto.")
        tk = kind_of(doc.item(track))
        if tk not in FITS[it["kind"]]:
            name = doc.item(track).get("name") or track
            raise RostrumError(codes.BAD_ARGUMENT, "paste", f'"{name}"', f"can't hold {WHAT[it['kind']]}",
                               hint="Select a track of the same kind, then paste again.")
        args = _args(doc, it, at + it["offset"])
        per.setdefault((track, it["kind"]), []).append(args)
    calls = []
    for (track, kind), many in per.items():
        if kind in MANY:
            calls.append({"op": f"{kind}.add_many", "target": [track], "args": {MANY[kind]: many}})
        else:
            calls += [{"op": f"{kind}.add", "target": [track], "args": a} for a in many]
    return calls


def _args(doc, it, seconds):
    params = {p.name for p in doc.kind.registry.get(f"{it['kind']}.add").params} - {"id"}
    stored = DEFAULTS.get(it["kind"], {})
    # a field still at its default is left out: a setting that only applies while another is on (useCleaned) is
    # refused when added alone, and the new item gets that default anyway
    args = {k: v for k, v in it["fields"].items() if k in params and not (k in stored and v == stored[k])}
    if it["kind"] == "clip" and isinstance(args.get("media"), str):     # into this song's own media folder (a no-op at home)
        if not media.exists(args["media"]):
            raise RostrumError(codes.NOT_FOUND, "paste", f'the sound "{args["media"]}"', "is not there any more",
                               hint="Copy the clip again from a song that still has its sound.")
        args["media"] = media.keep(doc.folder, args["media"])
    args["at"] = write_like(it["fields"]["at"], max(0.0, round(seconds, 6)), doc.data)
    return args


def root_tracks(doc):
    return doc.data.get("tracks", [])
