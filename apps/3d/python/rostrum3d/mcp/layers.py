"""The passes of a render (SPEC §11.2, EXR only; the core writes them, core/src/passes.h): which a call asks for, and
what the layered EXR holds, for the render's manifest (its layers, their channel names, which item each mask is and
what adds up to what), so the Editor and agents read the file by its manifest, never by guessing."""
from __future__ import annotations

from rostrum_core.errors import RostrumError, codes

from rostrum3d.render_fields import PASSES, passes as shot_passes

PASSES_ARG = {"type": "array", "items": {"enum": list(PASSES)}, "uniqueItems": True,
              "description": "EXR layers beside Beauty (Cycles only; guide rendering). Default: the shot's Passes; [] = Beauty alone."}
ADDS_UP = "R G B (the beauty, before noise clean-up; exactly with it off) = light + reflections + rest"
MEANING = {"beauty": "the picture: scene-linear Rec.709, alpha = coverage", "light": "light on matte surfaces (diffuse, direct + bounced)",
           "reflections": "reflections and highlights (glossy)", "rest": "everything else: glass, glow, sky, haze",
           "shadow": "0 lit .. 1 in full shadow (matte surfaces' direct light lost to shadows)",
           "masks": "1 where the item (or anything it holds) is, else 0; hard-edged", "depth": "distance from the camera plane, metres; 0 = nothing",
           "normal": "surface direction, world space, Y up, -1..1",
           "motion": "motion vectors in pixels, x right, y up: X Y = where it was a frame before minus where it is, "
                     "Z W = where it is minus where it will be a frame after; the picture rendered sharp"}
LIGHT_GROUPS = ("R G B (before noise clean-up) = the sum of the lightgroup_<light> layers + what glows on its own "
                "(emissive surfaces); each is one light's share, not cleaned of noise")
CRYPTOMATTE = ("CryptoObject00..02: Cryptomatte object ranks (id, share) x 2 each, one id per top-level item; "
               "names and ids in the file's header (cryptomatte/<key>/manifest), as Nuke, Resolve and Natron read them")


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
    groups = {layer: layer.split("_", 1)[1] for layer in layers if layer.startswith("lightgroup_")}
    if groups:
        out["light_groups"] = {layer: names.get(light, light) for layer, light in groups.items()}
        out["meaning"]["lightgroup_<light>"] = LIGHT_GROUPS
    if "CryptoObject00" in layers:
        out["meaning"]["CryptoObject00"] = CRYPTOMATTE
    return out
