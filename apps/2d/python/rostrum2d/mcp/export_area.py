"""Export › Picture › Area (camera spec § 4.14): a picture of any area of the world instead of the frame. The area is one world
rectangle for the whole range, taken at the first picture: the frame's own box ("frame", the default: the export as it
always was), the picked layers' box ("items"), or every layer and the frame's whole path ("world"). Drawn by the engine's
world picture (what the canvas shows, without the veil), so a layer looks the same as in the export. Pictures (png) only."""
from __future__ import annotations

from pathlib import Path

from PIL import Image
from rostrum_core.errors import RostrumError, codes

from rostrum2d.io import formats as table, readback

from . import world_facts as wf
from .render import _fail
from .world_picture import fitted, pixels_of

AREAS = ("frame", "items", "world")
ARGS = {"area": {"type": "string", "enum": list(AREAS), "description": "png only: which part of the world the picture shows. frame (default): the frame, as the export always was. "
                 "items: the box round the layers in `ids`, as the world draws them at the first picture (a logo as a PNG). world: every layer and the frame's whole path. "
                 "The size of an items or world picture is its world size × `scale`."},
        "ids": {"type": "array", "items": {"type": "string"}, "description": "area items: the layers to export (one or more)."},
        "scale": {"type": "number", "exclusiveMinimum": 0, "description": "area items / world: picture px per world px (default 1; at most 8192 px a side)."}}


def chosen(where: str, fmt: str, comp: dict, start: float, area=None, ids=None, scale=None) -> dict | None:
    """The area setting for this export (None for the frame): {area, x, y, w, h, scale}, the rectangle taken at `start`. A choice
    that doesn't fit the format or is missing what it needs is refused in words."""
    bad = lambda what, why, hint="": RostrumError(codes.BAD_ARGUMENT, where, what, why, hint=hint)
    if area in (None, "frame"):
        if ids or scale:
            raise bad('"ids" / "scale"', 'only apply to area "items" or "world"')
        return None
    if fmt != "png":
        raise bad(f'area "{area}"', f"is for pictures (png) only; {fmt} always holds the frame")
    if area == "items":
        if not ids:
            raise bad('area "items"', "needs the layers to export", "Pass ids: [the layer ids].")
        rect = wf.of_layers(comp, list(ids), start)
    else:
        if ids:
            raise bad('"ids"', 'only apply to area "items"')
        rect = wf.everything(comp, start)
    x0, y0, x1, y1 = rect
    if x1 - x0 <= 0 or y1 - y0 <= 0:
        raise bad(f'area "{area}"', "has nothing with a size to show")
    return {"area": area, **fitted(where, (x0, y0, x1 - x0, y1 - y0), scale=scale or 1.0)}


def pictures(where: str, scene: dict, s: dict, target: Path, progress, engine_factory) -> dict:
    """Write the area's pictures (one per frame of the range) as `target`'s sequence; the facts read back, as export() gives them."""
    from rostrum2d.engine import Engine
    f, p, a = table.FORMATS["png"], scene["comp"]["props"], s["area"]
    fps, first = p["fps"], round(s["start"] * p["fps"])
    n = max(1, round((s["end"] - s["start"]) * fps))
    pattern = table.pattern(f, target)
    Path(pattern).parent.mkdir(parents=True, exist_ok=True)
    try:
        with (engine_factory or Engine)() as eng:
            eng.load(scene)
            for i in range(n):
                img = pixels_of(eng, s["start"] + i / fps, a)
                if not s["alpha"]:
                    img = Image.alpha_composite(Image.new("RGBA", img.size, (0, 0, 0, 255)), img)
                img.save(pattern.replace("{frame}", f"{first + i:04d}"))
                if progress:
                    progress(i + 1, n)
    except RostrumError:
        raise
    except Exception as e:  # noqa: BLE001
        raise _fail(where, f"the {a['area']} picture {Path(pattern).name}", e) from e
    w, h = round(a["w"] * a["scale"]), round(a["h"] * a["scale"])
    facts = readback.check("png", pattern, n, w, h, s["alpha"], 8)
    return {"file": pattern, "frames": n, "fps": fps, "alpha": s["alpha"], "depth": 8, "checked": facts}
