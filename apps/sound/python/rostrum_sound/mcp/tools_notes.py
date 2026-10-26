"""`inspect_notes`: one track's notes (or drum hits) in a stretch of the song, one short line each, so an agent can pick
the ones to edit without reading a whole track.

    id  time (s and bar.beat)  pitch  length  vel          e.g.   harp.n8438  8.44 s  bar 5.2  C#4  1.5 beats  vel 0.8

The stretch is `from` / `to` (bars {"bar": 5}, seconds, {"beat": 8} or a marker "#drop": the range target's own forms,
range_target.py) or `section` (a song section by name: from its start to its end). `from` is included, `to` is not.
The same ids go straight into edit_document. At most `limit` lines; the last line says how many more there are.
An id is made from where the note STARTED when it was made (`harp.n8438` = 8438 ms; doc/ids.py), and is kept when the
note moves; so do not work out a note's time from its id: read it from this list.
"""
from __future__ import annotations

from rostrum_core import RostrumError, codes
from rostrum_core.mcp import Reply, Tools

from ..doc import meter, tempo, times
from ..doc.select_time import end_of, start_of
from . import range_target as RT

LIMIT = 60


def _where(root, sec: float) -> str:
    beat = tempo.beat_at(root, sec)
    bars = meter.bar_at(root, beat)
    return f"{sec:.2f} s  bar {int(bars) + 1}.{(bars - int(bars)) * meter.bar_length_beats(root, beat) + 1:.2f}".replace(".00", "")


def _line(root, kind: str, item: dict) -> str:
    start = start_of(root, item)
    if kind == "hit":
        what, length = str(item["drum"]), ""
    else:
        p = item["pitch"]
        what = "+".join(map(str, p)) if isinstance(p, list) else str(p)
        length = f"  {tempo.beat_at(root, end_of(root, item)) - tempo.beat_at(root, start):.3g} beats"
    return f"{item['id']}  {_where(root, start)}  {what}{length}  vel {item.get('vel', 0.85):.2g}"


def _bounds(root, args) -> tuple[float, float]:
    if args.get("section"):
        got = [s for s in root.get("sections", []) if s.get("name") == args["section"]]
        if not got:
            raise RostrumError.not_found("inspect_notes", "section", args["section"], [s.get("name") for s in root.get("sections", [])])
        return start_of(root, got[0]), times.seconds(got[0]["end"], root, "inspect_notes")
    return RT.bounds(root, {k: args[k] for k in ("from", "to") if k in args}, "inspect_notes")


def register(tools: Tools):
    @tools.tool("inspect_notes", {"required": ["track"], "properties": {
        "track": {"type": "string", "description": "The track's id."},
        "from": {"description": 'Where to start (included): a bar {"bar": 5}, seconds, {"beat": 8} or a marker "#drop". Left out = the start.'},
        "to": {"description": "Where to stop (not included), same forms. Left out = the end."},
        "section": {"type": "string", "description": "A section's name: its start to its end (instead of from / to)."},
        "limit": {"type": "integer", "default": LIMIT, "minimum": 1, "maximum": 500},
        "item": {"type": "string", "description": "The song's item id. Optional when only one is open."}}})
    def inspect_notes(ctx, args):
        """A track's notes and drum hits in a stretch of the song, one line each: id, time (seconds and bar.beat), pitch (or drum), length in beats, velocity. Filter by `from` / `to` (bars, seconds, beats or a marker name) or `section`; capped at `limit` lines, then "… N more, narrow the range". The ids go into edit_document targets. (An id carries the note's start in ms from when it was made; it stays when the note moves, so read times from here.) Read-only."""
        doc = ctx.document(args.get("item"))
        root = doc.data
        track = doc.item(args["track"]) if doc.has(args["track"]) else None
        if track is None or track.get("type") != "track":
            raise RostrumError.not_found("inspect_notes", "track", args["track"], [t["id"] for t in root.get("tracks", [])])
        a, b = _bounds(root, args)
        rows = [(start_of(root, i), kind, i) for kind, key in (("note", "notes"), ("hit", "hits")) for i in track.get(key, [])]
        rows = sorted((r for r in rows if a - 1e-9 <= r[0] < b - 1e-9), key=lambda r: (r[0], r[2]["id"]))
        limit = args.get("limit", LIMIT)
        lines = [_line(root, kind, i) for _, kind, i in rows[:limit]]
        more = len(rows) - len(lines)
        if more:
            lines.append(f"… {more} more, narrow the range")
        head = f"{len(rows)} on {track['id']}" + (f" in {args['section']}" if args.get("section") else "") + ":"
        return Reply(head + "\n" + "\n".join(lines) if lines else f"{track['id']} has nothing in that stretch.",
                     {"count": len(rows), "ids": [i["id"] for _, _, i in rows[:limit]], "more": max(more, 0)})
