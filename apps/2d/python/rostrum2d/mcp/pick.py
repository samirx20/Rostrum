"""Choosing what a tool call is about: the document, the composition, the time (a number of seconds or a frame)."""
from __future__ import annotations

from rostrum_core.errors import RostrumError, codes

ITEM_COMP = {
    "item": {"type": "string", "description": "The document's project item id. Optional when only one document is open."},
    "comp": {"type": "string", "description": "The composition's id. Default: the first one."},
}
TIME = {
    "time": {"type": "number", "minimum": 0, "description": "Seconds."},
    "frame": {"type": "integer", "minimum": 0, "description": "A whole frame number at the composition's frame rate (instead of time)."},
}


def doc_and_comp(ctx, args: dict):
    doc = ctx.document(args.get("item"))
    comps = doc.data.get("comps", [])
    if not comps:
        raise RostrumError(codes.NOT_FOUND, ctx.tool, "composition", "the document has no composition yet", hint="Add one with the comp() script call or comp.add.")
    want = args.get("comp")
    if want is None:
        return doc, comps[0]
    comp = next((c for c in comps if c["id"] == want), None)
    if comp is None:
        raise RostrumError.not_found(ctx.tool, "composition", want, [c["id"] for c in comps], "the compositions of this document")
    return doc, comp


def comp_of(ctx, args: dict) -> dict:
    return doc_and_comp(ctx, args)[1]


def time_of(ctx, comp: dict, args: dict, key: str = "time", frame_key: str = "frame", default: float = 0.0) -> tuple[float, int]:
    """(seconds, frame) from `time` or `frame`; both given, or one past the last frame, is an error."""
    fps, duration = comp.get("fps", 30), comp.get("duration", 5.0)
    frames = round(duration * fps)
    if key in args and frame_key in args:
        raise RostrumError(codes.BAD_ARGUMENT, ctx.tool, f'"{key}" and "{frame_key}"', "were both given", [key, frame_key], "Give one.")
    t = args[frame_key] / fps if frame_key in args else args.get(key, default)
    frame = round(t * fps)
    if frame >= frames:
        raise RostrumError(codes.BAD_ARGUMENT, ctx.tool, f'"{frame_key if frame_key in args else key}"', f"is at or past the end ({duration} s, {frames} frames at {fps} fps)",
                           hint=f"The last frame is {frames - 1} ({round((frames - 1) / fps, 4)} s).")
    return t, frame
