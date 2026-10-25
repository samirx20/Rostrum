"""look_arrangement: the written song as a picture and facts, straight from the document (no render needed):
what plays where, the markers, and for each marker which tracks start on it and how far off the others are."""
from __future__ import annotations

from rostrum_core.mcp import Reply, Tools

from ..doc import markers
from ..ears import arrangement as A
from ..ears.draw_arrangement import arrangement_picture
from .tools_render import ITEM


def register(tools: Tools):
    @tools.tool("look_arrangement", {"properties": {**ITEM,
        "start": {"type": "number", "description": "Seconds: draw from here (default the start)."},
        "end": {"type": "number", "description": "Seconds: draw to here (default the song's end)."}}})
    def look_arrangement(ctx, args):
        """See the written song without rendering: a picture with one row per track (notes by pitch, drum hits, clips), bar numbers, sections and markers; and, for every marker, which tracks start on it (within 10 ms) and each track's nearest start in ms and beats. Use it after run_script to check that parts are where you meant, and that hits sit on their markers (look_music (what: events) checks the rendered sound)."""
        doc = ctx.document(args.get("item"))
        with markers.project(getattr(doc, "folder", None)):
            arr = A.read(doc.data)
            near = A.near_markers(doc.data, arr)
        png = str(ctx.app.state.look_dir(doc.item_id) / "arrangement.png")
        arrangement_picture(png, arr, args.get("start", 0.0), args.get("end"), f"{doc.item_id}: arrangement")
        data = {"end_s": round(arr["end"], 3), "bars": arr["bar_count"], "png": png, "markers": near, "broken_notes": arr["broken"],
                "sections": [{"name": n, "start_s": round(s, 3), "end_s": round(e, 3)} for n, s, e in arr["sections"]],
                "tracks": [{"id": t["id"], "notes": len(t["notes"]), "hits": len(t["hits"]), "clips": len(t["clips"]),
                            "first_s": A.starts(t)[0] if A.starts(t) else None} for t in arr["tracks"]]}
        return Reply(A.summary(arr, near), data, [png], [png])
