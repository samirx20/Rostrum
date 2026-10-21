"""look_frame, look_sheet, look_at: the agent's eyes, through the shot's camera and the same engine as export (preview ≡ export)."""
from __future__ import annotations

import tempfile
from pathlib import Path

from rostrum_core.errors import RostrumError, codes
from rostrum_core.mcp import Reply, Tools

from . import draw, sheet
from .files import look_path
from .shot import ITEM_SHOT, LOOK, TIME, check_frame, doc_and_shot, frame_of, renderer_of, seconds, size_of

tools = Tools()
LOOK_SAMPLES = 64                         # Cycles samples for a look (denoised); render_still has its own


def _settings(renderer: str) -> dict:
    return {"samples": LOOK_SAMPLES, "denoise": True} if renderer == "cycles" else {}


@tools.tool("look_frame", {"properties": {**ITEM_SHOT, **TIME, **LOOK}})
def look_frame(ctx, args):
    """One rendered frame of a shot, seen through the SHOT's camera by the same render path as export: a PNG file and an image you
    can see. quality fast = Storm, final = Cycles (slower); renderer picks one by name (storm, cycles, stylized)."""
    doc, info = doc_and_shot(ctx, args)
    frame, renderer = frame_of(ctx, info, args), renderer_of(args)
    w, h = size_of(info, args)
    scene, engine = draw.scene_of(doc, info["id"]), draw.engine_of(ctx)
    dest = look_path(f'{doc.item_id or "doc"}_{info["id"]}_f{frame}_{renderer}')

    def job_fn(job):
        out = draw.render(ctx.tool, f"frame {frame} of {info['id']}", engine, scene, camera=info["camera"], renderer=renderer, frame=frame,
                          width=w, height=h, png=str(dest), **_settings(renderer))
        t = seconds(info, frame)
        return Reply(f'Frame {frame} ({t:.3f} s) of {info["id"]} through camera {info["camera"]}, {w}×{h}, {renderer}, {out["frames"][0]["ms"]:.0f} ms.',
                     {"time": t, "frame": frame, "width": w, "height": h, "renderer": out.get("renderer", renderer), "camera": info["camera"],
                      "timing": out.get("timing", {}), "vram": out.get("vram", {})}, [dest], [dest], engine.take_notices())

    return ctx.long(f'look_frame {info["id"]} f{frame}', job_fn)


@tools.tool("look_sheet", {"properties": {**ITEM_SHOT, **LOOK, "start": {"type": "number", "minimum": 0, "description": "Seconds from the start of the shot. Default 0."},
                                           "end": {"type": "number", "minimum": 0, "description": "Seconds from the start of the shot. Default: the last frame."},
                                           "count": {"type": "integer", "minimum": 2, "maximum": 24, "default": 6, "description": "Frames in the sheet, evenly spaced."},
                                           "cols": {"type": "integer", "minimum": 1, "maximum": 8, "description": "Tiles per row. Default 3."},
                                           "width": {"type": "integer", "minimum": 64, "maximum": 1280, "default": 480, "description": "Width of each tile in px."}}})
def look_sheet(ctx, args):
    """A contact sheet: `count` frames spread over the shot (or a range) in one image, each tile labelled with its frame and time. Drawn fast
    (Storm) unless you say otherwise. Use it to check a whole move at a glance; look_frame for detail."""
    doc, info = doc_and_shot(ctx, args)
    fps, first, last = info["fps"], info["start"], info["end"]
    f0 = first + round(args.get("start", 0.0) * fps)
    f1 = last if "end" not in args else first + round(args["end"] * fps)
    if f0 >= f1:
        raise RostrumError(codes.BAD_ARGUMENT, ctx.tool, f"range {f0}–{f1}", f"must run forward inside the shot (frames {first}–{last})")
    check_frame(ctx, info, f0), check_frame(ctx, info, f1)
    count = args.get("count", 6)
    frames = sorted({round(f0 + (f1 - f0) * i / (count - 1)) for i in range(count)})
    renderer, tile_w = renderer_of(args), args.get("width", 480)
    w, h = size_of(info, {"width": tile_w})
    cols = args.get("cols", min(3, len(frames)))
    scene, engine = draw.scene_of(doc, info["id"]), draw.engine_of(ctx)
    dest = look_path(f'{doc.item_id or "doc"}_{info["id"]}_sheet_{renderer}')

    def job_fn(job):
        with tempfile.TemporaryDirectory(prefix="rostrum3d_sheet_") as tmp:
            pngs = []
            for i, f in enumerate(frames):                # one request per frame: the contract's `frames` is a contiguous range
                png = Path(tmp) / f"f{f}.png"
                draw.render(ctx.tool, f"frame {f} of {info['id']}", engine, scene, camera=info["camera"], renderer=renderer, frame=f,
                            width=w, height=h, png=str(png), **_settings(renderer))
                pngs.append(png)
                job.progress(i + 1, len(frames))
            sw, sh = sheet.contact_sheet([(p, f"f{f}   {seconds(info, f):.2f} s") for p, f in zip(pngs, frames)], tile_w, cols, dest)
        return Reply(f'Contact sheet of {info["id"]}: {len(frames)} frames, {frames[0]}–{frames[-1]} ({seconds(info, frames[0]):.2f}–{seconds(info, frames[-1]):.2f} s), '
                     f'{renderer}, {sw}×{sh}.', {"frames": frames, "times": [round(seconds(info, f), 4) for f in frames], "width": sw, "height": sh,
                                                 "cols": cols, "camera": info["camera"]}, [dest], [dest], engine.take_notices())

    return ctx.long(f'look_sheet {info["id"]}', job_fn)


@tools.tool("look_at", {"properties": {**ITEM_SHOT, **TIME, "x": {"type": "number", "minimum": 0, "description": "Pixels from the left of the picture."},
                                        "y": {"type": "number", "minimum": 0, "description": "Pixels from the top of the picture."},
                                        "points": {"type": "array", "minItems": 1, "maxItems": 64, "items": {"type": "array", "items": {"type": "number", "minimum": 0}, "minItems": 2, "maxItems": 2},
                                                   "description": "Several points as [[x, y], …] (instead of x and y)."},
                                        "width": {"type": "integer", "minimum": 64, "maximum": 4096, "default": 960, "description": "Width of the picture the pixels count in (the one look_frame gave). Default 960."},
                                        "height": {"type": "integer", "minimum": 1, "maximum": 4096, "description": "Height of that picture. Default: follows the shot's shape."}}})
def look_at(ctx, args):
    """What is at a pixel (x, y) of a picture from the shot camera at a frame: the item id, the part (prim), its material, the point in the
    world (metres) and the distance from the camera. Counted from the top-left of a width×height picture, the same whatever renderer drew it."""
    doc, info = doc_and_shot(ctx, args)
    points = args.get("points") or ([[args["x"], args["y"]]] if "x" in args and "y" in args else None)
    if not points or ("points" in args and ("x" in args or "y" in args)):
        raise RostrumError(codes.BAD_ARGUMENT, ctx.tool, '"x", "y" and "points"', "need either x and y, or points", ["x and y", "points"])
    frame = frame_of(ctx, info, args)
    w, h = size_of(info, args, 960)
    h = args.get("height", h)
    scene, engine = draw.scene_of(doc, info["id"]), draw.engine_of(ctx)

    def job_fn(job):
        rows = []
        for x, y in points:                                # the engine's `point` is the world point; the pixel is kept as `pixel`
            r = draw.call(ctx.tool, f"point ({x:g}, {y:g})", engine, scene, "pick", camera=info["camera"], frame=frame, width=w, height=h, x=x, y=y)
            rows.append({"pixel": [x, y], **{k: v for k, v in r.items() if k not in ("ok", "ms")}})
        lines = [f'({r["pixel"][0]:g}, {r["pixel"][1]:g}): ' + (f'{r["item"]} ({r["prim"]}), material {r.get("material") or "none"}, '
                                                              f'{r["distance"]:.3g} m away at {[round(c, 3) for c in r["point"]]}'
                                                              if r.get("hit") else "nothing (background)") for r in rows]
        t = seconds(info, frame)
        return Reply(f'At frame {frame} ({t:.3f} s) of {info["id"]}, picture {w}×{h}: ' + "; ".join(lines) + ".",
                     {"time": t, "frame": frame, "width": w, "height": h, "hits": rows}, warnings=engine.take_notices())

    return ctx.long(f'look_at {info["id"]} f{frame}', job_fn)

