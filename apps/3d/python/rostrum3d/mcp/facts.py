"""inspect_3d_file, inspect_shot and inspect_exposure: facts, never changes."""
from __future__ import annotations

import tempfile
from pathlib import Path

from rostrum_core.errors import RostrumError, codes
from rostrum_core.mcp import Reply, Tools

from ..ops_import import EXTENSIONS, unit_name
from . import draw
from .shot import ITEM_SHOT, LOOK, QUALITY, TIME, doc_and_shot, frame_of, renderer_of, seconds, size_of

tools = Tools()
SHOWN = 24


def _size(bounds) -> list[float] | None:
    return [round(b - a, 4) for a, b in zip(*bounds)] if bounds else None


def _frames(r: dict) -> str:
    if not r.get("animated"):
        return ""
    return f', animated: frames {r.get("startFrame"):g}–{r.get("endFrame"):g} at {r.get("framesPerSecond"):g} fps'


@tools.tool("inspect_3d_file", {"required": ["file"], "properties": {
    "file": {"type": "string", "description": "A 3D file an import reads: USD (.usd .usda .usdc .usdz), glTF (.gltf .glb), OBJ, FBX or "
                                              "Alembic (.abc); absolute, or relative to the project folder."},
    "detail": {"enum": ["short", "full"], "default": "short", "description": "full adds every prim the engine listed (at most 2000)."}}})
def inspect_3d_file(ctx, args):
    """What a 3D file holds, without importing it: its format, its unit (and whether the file states one), up axis, animation
    (frames and fps), and its parts (path, type, material, size in the file's units). Use it before import.add to pick the parts
    you will give other materials or hide; import.add itself scales a file in another unit to metres and lists its meshes as parts."""
    path = Path(args["file"])
    if not path.is_absolute() and ctx.app.folder:
        path = Path(ctx.app.folder) / path
    if path.suffix.lower() not in EXTENSIONS or not path.is_file():
        raise RostrumError(codes.NOT_FOUND, ctx.tool, f'"{args["file"]}"', "is not a file that exists" if path.suffix.lower() in EXTENSIONS
                           else "is not a 3D file an import reads", EXTENSIONS, f"Looked for {path}.")
    engine = draw.engine_of(ctx)
    try:
        r = engine.inspect_usd(path)
    except Exception as e:
        raise RostrumError(codes.RENDER_FAILED, ctx.tool, f'"{path.name}"', f"could not be read: {e}") from e
    prims = [{**p, "size": _size(p.get("bounds"))} for p in r.get("prims", [])]
    parts = [p for p in prims if p["path"].count("/") <= 2 and "/Materials" not in p["path"]]
    unit = r.get("metersPerUnit") or 1.0
    units = f"{unit_name(unit)} ({unit:g} m per unit)" if r.get("unitsKnown", True) else "no unit stated (taken as metres)"
    lines = [f'{p["path"]} ({p["type"]}{", " + p["material"] if p.get("material") else ""}{", " + " × ".join(f"{v:g}" for v in p["size"]) if p["size"] else ""})'
             for p in parts[:SHOWN]]
    summary = (f'{path.name}: {r.get("format", "USD")}, {units}, up axis {r.get("upAxis")}, default prim {r.get("defaultPrim") or "none"}'
               f'{_frames(r)}, {len(prims)} prims{" (list cut at 2000)" if r.get("truncated") else ""}. Top parts: ' + ("; ".join(lines) or "none") +
               (f"; … {len(parts) - SHOWN} more" if len(parts) > SHOWN else "") + ".")
    data = {"file": str(path), "format": r.get("format", "USD"), "default_prim": r.get("defaultPrim"), "up_axis": r.get("upAxis"),
            "meters_per_unit": unit, "units_known": r.get("unitsKnown", True), "animated": r.get("animated", False),
            "start_frame": r.get("startFrame"), "end_frame": r.get("endFrame"), "frames_per_second": r.get("framesPerSecond"),
            "prim_count": len(prims), "truncated": r.get("truncated", False), "parts": parts}
    if args.get("detail") == "full":
        data["prims"] = prims
    return Reply(summary, data, warnings=engine.take_notices())


def _walk(items: list[dict]):
    for it in items:
        yield it
        yield from _walk(it.get("children", []))


@tools.tool("inspect_shot", {"properties": ITEM_SHOT})
def inspect_shot(ctx, args):
    """A shot's facts: frame rate, first and last frame, length in seconds, picture size, the shot camera, every camera in the scene with
    its lens, and how many items and lights it holds. Reads the document; draws nothing."""
    doc, info = doc_and_shot(ctx, args)
    scene = draw.scene_of(doc, info["id"])
    items = list(_walk(scene["items"]))
    cams = [{"id": c["id"], **{k: c["props"][k] for k in ("focalLength", "sensorWidth", "dof", "fStop", "focusDistance") if k in c["props"]}}
            for c in items if c["type"] == "camera"]
    lights = [c["id"] for c in items if c["type"] == "light"]
    frames = info["end"] - info["start"] + 1
    length = frames / info["fps"]
    data = {**info, "frames": frames, "seconds": round(length, 4), "last_time": round(seconds(info, info["end"]), 4), "cameras": cams,
            "lights": lights, "items": len(items), "materials": [m["id"] for m in scene.get("materials", [])]}
    return Reply(f'Shot {info["id"]}: frames {info["start"]}–{info["end"]} ({frames} frames, {length:.2f} s at {info["fps"]:g} fps), '
                 f'{info["width"]}×{info["height"]}, shot camera {info["camera"]}; {len(cams)} camera(s), {len(lights)} light(s), {len(items)} items.', data)


CELLS = ("top-left", "top", "top-right", "left", "middle", "right", "bottom-left", "bottom", "bottom-right")
EXPOSURE_SAMPLES = 32


def _share(hist: list[int], lo: int, hi: int) -> float:
    return sum(hist[lo:hi + 1]) / max(1, sum(hist)) * 100


def _percentile(hist: list[int], q: float) -> int:
    target, seen = sum(hist) * q / 100, 0
    for v, n in enumerate(hist):
        seen += n
        if seen >= target:
            return v
    return 255


def measure(png: Path) -> dict:
    """How bright a picture is: clipped / crushed shares, luminance spread, and the same per cell of a 3×3 grid (Pillow only)."""
    from PIL import Image, ImageChops
    img = Image.open(png).convert("RGB")
    r, g, b = img.split()
    top = ImageChops.lighter(ImageChops.lighter(r, g), b)          # the brightest channel of every pixel
    luma = img.convert("L", (0.2126, 0.7152, 0.0722, 0))           # Rec.709 weights
    w, h = img.size
    cells = []
    for i, name in enumerate(CELLS):
        box = (i % 3 * w // 3, i // 3 * h // 3, (i % 3 + 1) * w // 3, (i // 3 + 1) * h // 3)
        th, lh = top.crop(box).histogram(), luma.crop(box).histogram()
        cells.append({"cell": name, "mean": round(sum(v * n for v, n in enumerate(lh)) / max(1, sum(lh)), 1), "clipped_pct": round(_share(th, 254, 255), 1),
                      "crushed_pct": round(_share(th, 0, 2), 1), "centre": [(box[0] + box[2]) // 2, (box[1] + box[3]) // 2]})
    th, lh = top.histogram(), luma.histogram()
    return {"width": w, "height": h, "clipped_pct": round(_share(th, 254, 255), 2), "crushed_pct": round(_share(th, 0, 2), 2),
            "luminance": {"mean": round(sum(v * n for v, n in enumerate(lh)) / (w * h), 1), "p1": _percentile(lh, 1), "p99": _percentile(lh, 99),
                          "scale": "0 black – 255 white, display values"}, "cells": cells}


@tools.tool("inspect_exposure", {"properties": {**ITEM_SHOT, **TIME, "quality": {"enum": list(QUALITY), "default": "fast", "description": "fast = Storm at 320 px (about a second), final = Cycles at 320 px, 32 samples, denoised (what export will look like, slower)."},
                                                 "renderer": LOOK["renderer"], "width": {"type": "integer", "minimum": 64, "maximum": 1280, "default": 320, "description": "Width of the measured picture in px."}}})
def inspect_exposure(ctx, args):
    """How bright a shot's frame is, in numbers: the share of pixels blown out (any channel ≥ 254) and crushed to black (all ≤ 2), the mean,
    1st and 99th percentile brightness, and which part of a 3×3 grid is brightest and darkest, with the item at the brightest spot. Draws a small
    picture through the shot camera and looks at it; use it before a final render to catch a blown-out or too-dark shot. Nothing is changed."""
    doc, info = doc_and_shot(ctx, args)
    frame, renderer = frame_of(ctx, info, args), renderer_of(args)
    w, h = size_of(info, args, 320)
    scene, engine = draw.scene_of(doc, info["id"]), draw.engine_of(ctx)

    def job_fn(job):
        with tempfile.TemporaryDirectory(prefix="rostrum3d_exposure_") as tmp:
            png = Path(tmp) / "exposure.png"
            draw.render(ctx.tool, f"frame {frame} of {info['id']}", engine, scene, camera=info["camera"], renderer=renderer, frame=frame, width=w, height=h,
                        png=str(png), **({"samples": EXPOSURE_SAMPLES, "denoise": True} if renderer == "cycles" else {}))
            m = measure(png)
        bright, dark = max(m["cells"], key=lambda c: c["mean"]), min(m["cells"], key=lambda c: c["mean"])
        hit = draw.call(ctx.tool, f"the brightest spot ({bright['cell']})", engine, scene, "pick", camera=info["camera"], frame=frame, width=w, height=h,
                        x=bright["centre"][0], y=bright["centre"][1])
        bright["item"] = hit.get("item") if hit.get("hit") else None
        look = f"{bright['item']} is there" if bright["item"] else "background there"
        verdict = ("; a lot is blown out" if m["clipped_pct"] > 5 else "") + ("; a lot is crushed to black" if m["crushed_pct"] > 25 else "")
        return Reply(f'Frame {frame} of {info["id"]} ({renderer}, {m["width"]}×{m["height"]}): {m["clipped_pct"]:g} % blown out, {m["crushed_pct"]:g} % crushed, '
                     f'brightness mean {m["luminance"]["mean"]:g} (1 % at {m["luminance"]["p1"]:g}, 99 % at {m["luminance"]["p99"]:g} of 255). Brightest: {bright["cell"]} '
                     f'({bright["clipped_pct"]:g} % blown out, {look}); darkest: {dark["cell"]} ({dark["crushed_pct"]:g} % crushed){verdict}.',
                     {"frame": frame, "renderer": renderer, "brightest": bright["cell"], "darkest": dark["cell"], **m}, warnings=engine.take_notices())

    return ctx.long(f'inspect_exposure {info["id"]} f{frame}', job_fn)
