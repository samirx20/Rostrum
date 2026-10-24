"""The passes of a render (SPEC §11.2, EXR only; the core writes them, core/src/passes.h): which a call asks for, and
what the layered EXR holds, for the render's manifest (its layers, their channel names, which item each mask is and
what adds up to what), so the Editor and agents read the file by its manifest, never by guessing."""
from __future__ import annotations

from rostrum_core.errors import RostrumError, codes

from rostrum3d.render_fields import PASSES, passes as shot_passes

PASSES_ARG = {"type": "array", "items": {"enum": list(PASSES)}, "uniqueItems": True,
              "description": "Layers of the EXR beside the picture (Beauty, always): light, reflections (with either, rest = glass, "
                             "glow and sky, so light + reflections + rest = the picture before noise clean-up), shadow (0 lit .. 1 in "
                             "shadow; renders each frame twice), masks (one per item, named by its id), depth (metres from the camera), "
                             "normal (surface direction). Cycles only. Default: the shot's own Passes (Beauty + Masks); [] = Beauty alone."}
ADDS_UP = "R G B (the beauty, before noise clean-up; exactly with it off) = light + reflections + rest"
MEANING = {"beauty": "the picture: scene-linear Rec.709, alpha = coverage", "light": "light on matte surfaces (diffuse, direct + bounced)",
           "reflections": "reflections and highlights (glossy)", "rest": "everything else: glass, glow, sky, haze",
           "shadow": "0 lit .. 1 in full shadow (matte surfaces' direct light lost to shadows)",
           "masks": "1 where the item (or anything it holds) is, else 0; hard-edged", "depth": "distance from the camera plane, metres; 0 = nothing",
           "normal": "surface direction, world space, Y up, -1..1"}


def chosen(where: str, args: dict, shot: dict, renderer: str, exr: bool) -> list[str]:
    """The passes for this call: `args["passes"]`, else the shot's own; none without an EXR or with a renderer other than Cycles."""
    asked = args.get("passes")
    if asked and not exr:
        raise RostrumError(codes.BAD_ARGUMENT, where, "passes", "are layers of the EXR, and no EXR is written", hint="Add exr.")
    if asked and renderer != "cycles":
        raise RostrumError(codes.BAD_ARGUMENT, where, "passes", f"are made by Cycles only, not {renderer}",
                           hint="Use quality final (Cycles), or leave passes out.")
    if not exr or renderer != "cycles":
        return []
    return list(asked) if asked is not None else shot_passes(shot)


def _names(items: list, out: dict) -> dict:
    for it in items:
        out[it["id"]] = it.get("name") or it["id"]
        _names(it.get("children", []), out)
    return out


def describe(channels: list[str], data: dict) -> dict:
    """The manifest's `exr` part from the core's channel list (render reply `channels`) and the document's data."""
    layers: dict[str, list[str]] = {}
    for c in channels:
        layer, _, _ = c.rpartition(".")
        layers.setdefault(layer or "beauty", []).append(c)
    names = _names(data.get("items", []), {})
    masks = {c: {"item": c.split(".", 1)[1], "name": names.get(c.split(".", 1)[1], c.split(".", 1)[1])} for c in layers.get("masks", [])}
    out = {"channels": channels, "layers": layers, "meaning": {k: v for k, v in MEANING.items() if k in layers}}
    if masks:
        out["masks"] = masks
    if "rest" in layers:
        out["adds_up"] = ADDS_UP
    return out
