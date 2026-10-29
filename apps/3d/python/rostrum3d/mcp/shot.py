"""Choosing what a tool call is about: the document, the shot, the frame, the picture size, the renderer."""
from __future__ import annotations

from rostrum_core.errors import RostrumError, codes

from rostrum3d.compile import shot_info
from rostrum3d.render_fields import settings

RENDERERS = ("storm", "cycles", "stylized")
QUALITY = {"fast": "storm", "final": "cycles"}
LOOK_WIDTH = 960
WIDTH_WORDS = "The picture's width in px (a sheet: each frame's). Default 960; sheet 480, shots and exposure 320, material 256, paint 1200."
WIDTH = {"width": {"type": "integer", "minimum": 64, "maximum": 4096, "description": WIDTH_WORDS}}     # one meaning in every look

ITEM_SHOT = {
    "item": {"type": "string", "description": "The document's item id; optional with one document open."},
    "shot": {"type": "string", "description": "The shot's id. Default: the first."},
}
TIME = {
    "frame": {"type": "integer", "minimum": 0, "description": "A frame of the shot (its own numbering)."},
    "at": {"type": "number", "minimum": 0, "description": "Seconds from the shot's start (instead of frame)."},
}
LOOK = {
    "quality": {"enum": list(QUALITY), "description": "fast = Storm (quick), final = Cycles (as export). Default fast; a Stylized shot: stylized; material: final if needed."},
    "renderer": {"enum": list(RENDERERS), "description": "Overrides quality by name; stylized draws Lines and Halftone (guide materials)."},
    **WIDTH,
}


def doc_and_shot(ctx, args: dict) -> tuple[object, dict]:
    """(document, shot info: id, camera, fps, start, end, width, height)."""
    doc = ctx.document(args.get("item"))
    ids = [s["id"] for s in doc.data.get("shots", [])]
    if not ids:
        raise RostrumError(codes.NOT_FOUND, ctx.tool, "shot", "the document has no shot yet", hint="Add one with the shot() script call.")
    want = args.get("shot", ids[0])
    if want not in ids:
        raise RostrumError.not_found(ctx.tool, "shot", want, ids, "the shots of this document")
    info = dict(shot_info(doc.data, want))
    if not info.get("camera"):
        raise RostrumError(codes.NOT_FOUND, ctx.tool, f'shot "{want}"', "has no camera, so there is nothing to look through",
                           hint="Add a camera item and set it as the shot's camera.")
    return doc, info


def render_settings(doc, info: dict) -> dict:
    """The shot's stored render settings (quality, size, frames), read the one way (render_fields.settings)."""
    return settings(next(s for s in doc.data["shots"] if s["id"] == info["id"]), info)


def frame_of(ctx, info: dict, args: dict, default: int | None = None) -> int:
    """The shot frame from `frame` or `at`; both, or one outside the shot, is an error."""
    if "frame" in args and "at" in args:
        raise RostrumError(codes.BAD_ARGUMENT, ctx.tool, '"frame" and "at"', "were both given", ["frame", "at"], "Give one.")
    frame = args["frame"] if "frame" in args else (info["start"] + round(args["at"] * info["fps"]) if "at" in args else
                                                   info["start"] if default is None else default)
    check_frame(ctx, info, frame)
    return frame


def check_frame(ctx, info: dict, frame: int):
    if not info["start"] <= frame <= info["end"]:
        raise RostrumError(codes.BAD_ARGUMENT, ctx.tool, f"frame {frame}", f'is outside shot "{info["id"]}"',
                           hint=f'The shot runs from frame {info["start"]} to {info["end"]} ({seconds(info, info["end"]):.3f} s).')


def seconds(info: dict, frame: int) -> float:
    return (frame - info["start"]) / info["fps"]


COUNT = {"count": {"type": "integer", "minimum": 1, "maximum": 24, "description": "How many frames (sheet 2–24, default 6; shots 1–8 a row, 4) or angles (material 4–8, 6)."}}


def count_of(ctx, args: dict, default: int, least: int, most: int) -> int:
    """The call's `count` (shared by sheet, shots and material, each with its own bounds), else `default`."""
    n = args.get("count", default)
    if not least <= n <= most:
        raise RostrumError(codes.BAD_ARGUMENT, ctx.tool, f"count {n}", f"must be {least}–{most} here", hint=f"Ask for {least}–{most}.")
    return n


def width_of(ctx, args: dict, default: int, most: int = 4096) -> int:
    """The call's `width` (one meaning in every look: the picture's width in px), else `default`; at most `most`."""
    w = args.get("width", default)
    if w > most:
        raise RostrumError(codes.BAD_ARGUMENT, ctx.tool, f"width {w}", f"is more than {most} px for this look", hint=f"Ask for at most {most}.")
    return w


def size_of(info: dict, args: dict, default_width: int | None = None) -> tuple[int, int]:
    """(width, height): the width asked for, the height from the shot's own shape."""
    w = args.get("width", default_width or LOOK_WIDTH)
    return w, max(1, round(w * info["height"] / info["width"]))


def renderer_of(args: dict, default_quality: str = "fast") -> str:
    return args.get("renderer") or QUALITY[args.get("quality", default_quality)]


def quality_line(renderer: str) -> str:
    """The one plain line every look ends with: which quality the picture is."""
    return {"storm": '\nQuality: live preview (Storm, what the window shows); quality "final" draws it as the export does (Cycles, slower).',
            "cycles": "\nQuality: final (Cycles, as the export draws it).",
            "stylized": "\nQuality: Stylized, as the window and the export draw it."}.get(renderer, "")


def look_renderer(args: dict, doc, infos: list[dict]) -> str:
    """A look's renderer: the call's renderer or quality, else stylized when every shot looked at renders Stylized (Storm can't
    draw Lines or Halftone, and the stylized look is as quick), else Storm."""
    if "renderer" in args or "quality" in args:
        return renderer_of(args)
    return "stylized" if all(render_settings(doc, i)["renderer"] == "stylized" for i in infos) else "storm"
