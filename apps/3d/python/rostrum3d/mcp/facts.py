"""inspect_usd_file and inspect_shot: facts, never changes."""
from __future__ import annotations

from pathlib import Path

from rostrum_core.errors import RostrumError, codes
from rostrum_core.mcp import Reply, Tools

from . import draw
from .shot import ITEM_SHOT, doc_and_shot, seconds

tools = Tools()
USD_EXT = (".usd", ".usda", ".usdc", ".usdz")
SHOWN = 24


def _size(bounds) -> list[float] | None:
    return [round(b - a, 4) for a, b in zip(*bounds)] if bounds else None


@tools.tool("inspect_usd_file", {"required": ["file"], "properties": {
    "file": {"type": "string", "description": "A .usd / .usda / .usdc / .usdz file (absolute, or relative to the project folder)."},
    "detail": {"enum": ["short", "full"], "default": "short", "description": "full adds every prim the engine listed (at most 2000)."}}})
def inspect_usd_file(ctx, args):
    """What a USD file holds, without importing it: its default prim, up axis, units, and its parts (prim path, type, material, size in
    scene units). Use it to pick the parts you will give other materials or hide when you import the file."""
    path = Path(args["file"])
    if not path.is_absolute() and ctx.app.folder:
        path = Path(ctx.app.folder) / path
    if path.suffix.lower() not in USD_EXT or not path.is_file():
        raise RostrumError(codes.NOT_FOUND, ctx.tool, f'"{args["file"]}"', "is not a USD file that exists" if path.suffix.lower() in USD_EXT else "is not a USD file",
                           USD_EXT, f"Looked for {path}.")
    engine = draw.engine_of(ctx)
    try:
        r = engine.inspect_usd(path)
    except Exception as e:
        raise RostrumError(codes.RENDER_FAILED, ctx.tool, f'"{path.name}"', f"could not be read: {e}") from e
    prims = [{**p, "size": _size(p.get("bounds"))} for p in r.get("prims", [])]
    parts = [p for p in prims if p["path"].count("/") <= 2]
    lines = [f'{p["path"]} ({p["type"]}{", " + p["material"] if p.get("material") else ""}{", " + " × ".join(f"{v:g}" for v in p["size"]) if p["size"] else ""})'
             for p in parts[:SHOWN]]
    summary = (f'{path.name}: default prim {r.get("defaultPrim") or "none"}, up axis {r.get("upAxis")}, {r.get("metersPerUnit")} m per unit, '
               f'{len(prims)} prims{" (list cut at 2000)" if r.get("truncated") else ""}. Top parts: ' + ("; ".join(lines) or "none") +
               (f"; … {len(parts) - SHOWN} more" if len(parts) > SHOWN else "") + ".")
    data = {"file": str(path), "default_prim": r.get("defaultPrim"), "up_axis": r.get("upAxis"), "meters_per_unit": r.get("metersPerUnit"),
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
