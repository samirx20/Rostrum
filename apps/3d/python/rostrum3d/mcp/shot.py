"""Choosing what a tool call is about: the document, the shot, the frame, the picture size, the renderer."""
from __future__ import annotations

from rostrum_core.errors import RostrumError, codes

from rostrum3d.compile import shot_info
from rostrum3d.render_fields import settings

RENDERERS = ("storm", "cycles", "stylized")
QUALITY = {"fast": "storm", "final": "cycles"}
LOOK_WIDTH = 960

ITEM_SHOT = {
    "item": {"type": "string", "description": "The document's project item id. Optional when only one document is open."},
    "shot": {"type": "string", "description": "The shot's id. Default: the first one."},
}
TIME = {
    "frame": {"type": "integer", "minimum": 0, "description": "A frame number of the shot (the shot's own numbering: its start frame is the first)."},
    "at": {"type": "number", "minimum": 0, "description": "Seconds from the start of the shot (instead of frame)."},
}
LOOK = {
    "quality": {"enum": list(QUALITY), "description": "fast = Storm (about a second a frame), final = Cycles (path traced, what export gives). Not given on a shot whose Quality is Stylized: the stylized look."},
    "renderer": {"enum": list(RENDERERS), "description": "Overrides quality: storm, cycles or stylized (the stylized look: materials' Lines, Halftone and Light to colour, every other material plainly lit by the scene's real lights; guide materials)."},
    "width": {"type": "integer", "minimum": 64, "maximum": 4096, "default": LOOK_WIDTH, "description": "Picture width in px; the height follows the shot's shape."},
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


def size_of(info: dict, args: dict, default_width: int | None = None) -> tuple[int, int]:
    """(width, height): the width asked for, the height from the shot's own shape."""
    w = args.get("width", default_width or LOOK_WIDTH)
    return w, max(1, round(w * info["height"] / info["width"]))


def renderer_of(args: dict, default_quality: str = "fast") -> str:
    return args.get("renderer") or QUALITY[args.get("quality", default_quality)]


def look_renderer(args: dict, doc, infos: list[dict]) -> str:
    """A look's renderer: the call's renderer or quality, else stylized when every shot looked at renders Stylized (Storm can't
    draw Lines or Halftone, and the stylized look is as quick), else Storm."""
    if "renderer" in args or "quality" in args:
        return renderer_of(args)
    return "stylized" if all(render_settings(doc, i)["renderer"] == "stylized" for i in infos) else "storm"
