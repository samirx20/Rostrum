"""look_arrangement: the written song as a picture and facts, straight from the document (no render needed):
what plays where, the chords and each line's notes bar by bar, the markers, and for each marker which tracks start
on it and how far off the others are."""
from __future__ import annotations

from rostrum_core import RostrumError, codes
from rostrum_core.mcp import Reply, Tools

from ..doc import markers
from ..doc import meter, tempo
from ..ears import arrangement as A
from ..ears import bar_text as BT
from ..ears.written import written_notes
from ..ears.draw_arrangement import arrangement_picture
from .tools_render import ITEM


def register(tools: Tools):
    @tools.tool("look_arrangement", {"properties": {**ITEM,
        "start": {"type": "number", "description": "Seconds: draw from here (default the start)."},
        "end": {"type": "number", "description": "Seconds: draw to here (default the song's end)."},
        "bars": {"type": "string", "description": "Bars 'from-to' ('9-16') for the bar-by-bar text and the picture."}}})
    def look_arrangement(ctx, args):
        """See the written song without rendering: a picture with one row per track (notes by pitch, drum hits by drum, clips; shade and thickness = the written level, velocity × the track's volume and volume automation; at the left the track's median level in dB and its highest and lowest note), bar numbers, a chord row, sections and markers; bar_by_bar text (per bar the chord symbols, each one-line part's notes as name+octave@beat, bars: 'from-to' for long songs); per track in the data level_db, level_db_range, register (low/high note), drums, volume; and, for every marker, which tracks start on it (within 10 ms) and each track's nearest start in ms and beats. Use it after run_script to check that parts are where you meant, and that hits sit on their markers (look_music (what: events) checks the rendered sound)."""
        doc = ctx.document(args.get("item"))
        with markers.project(getattr(doc, "folder", None)):
            arr = A.read(doc.data)
            near = A.near_markers(doc.data, arr)
            first, last = _bars(args.get("bars"))
            bt = BT.read(doc.data, written_notes(doc.data), arr["end"], first, last)
        start, end = args.get("start"), args.get("end")
        if args.get("bars") and bt["to"] >= bt["from"]:
            start = tempo.seconds_at(doc.data, meter.bar_start(doc.data, bt["from"])) if start is None else start
            end = tempo.seconds_at(doc.data, meter.bar_start(doc.data, bt["to"] + 1)) if end is None else end
        png = str(ctx.app.state.look_dir(doc.item_id) / "arrangement.png")
        arrangement_picture(png, arr, start or 0.0, end, f"{doc.item_id}: arrangement", bt["chords"])
        noted = set(bt["chord_tracks"] + bt["line_tracks"])
        kits = [t["id"] for t in arr["tracks"] if t["hits"] and not t["mute"] and t["id"] not in noted]
        other = [t["id"] for t in arr["tracks"] if (t["clips"] or t["lines"]) and not t["mute"] and t["id"] not in noted | set(kits)]
        muted = [t["id"] for t in arr["tracks"] if t["mute"]]
        head = BT.header(bt, kits, muted, other)
        data = {"end_s": round(arr["end"], 3), "bars": arr["bar_count"], "png": png, "markers": near, "broken_notes": arr["broken"],
                "bar_by_bar": [head, *BT.lines(bt)],
                "sections": [{"name": n, "start_s": round(s, 3), "end_s": round(e, 3)} for n, s, e in arr["sections"]],
                "tracks": [{"id": t["id"], "notes": len(t["notes"]), "hits": len(t["hits"]), "clips": len(t["clips"]),
                            "first_s": A.starts(t)[0] if A.starts(t) else None, "volume": t["volume"],
                            "volume_automated": t["automated"], "muted": t["mute"], **A.levels(t, arr["key"])} for t in arr["tracks"]]}
        return Reply(f"{A.summary(arr, near)} {head}", data, [png], [png])


def _bars(text) -> tuple[int | None, int | None]:
    """'9-16' -> (9, 16); '9' -> (9, 9); '9-' -> (9, None); nothing -> the default window."""
    if text is None or str(text).strip() == "":
        return None, None
    a, sep, b = str(text).replace("–", "-").partition("-")
    try:
        first = int(a) if a.strip() else None
        last = int(b) if b.strip() else (None if sep else first)
    except ValueError:
        raise RostrumError(codes.BAD_ARGUMENT, "look_arrangement", "bars", f"{text!r} is not a bar range",
                           hint="Write bars as 'from-to', e.g. '9-16', or one bar, e.g. '12'.") from None
    return first, last
