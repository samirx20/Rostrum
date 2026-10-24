"""What every Lottie layer has: the transform (`ks`), masks, blend mode, in / out frames, and the report lines for
what Lottie can't carry (tilt, effects, mask softness).

Our anchor is a fraction of the box that sits at (x, y); Lottie's `a` is a point in the layer's own px that sits at
`p`. Scale is a percent, opacity 0..100.
"""
from __future__ import annotations

from .. import blends, pathdata
from .lottie_frame import ride_keys
from .lottie_props import Ctx, build, frozen
from .lottie_shapes import shape_value

EFFECT_SAYS = {"blur": "blur", "glow": "glow", "shadow": "drop shadow", "backdrop": "frosted-glass backdrop"}


def transform(node: dict, ctx: Ctx, fit: tuple | None = None) -> dict:
    """`ks`. `fit` = (image w, image h, scale x, scale y): the layer is the image's own px, scaled to fill our box."""
    sfx, sfy = (fit[2], fit[3]) if fit else (1.0, 1.0)

    def anchor(p):
        bx, by = p["anchorX"] * p["w"], p["anchorY"] * p["h"]
        return [fit[0] / 2 + (bx - p["w"] / 2) / sfx, fit[1] / 2 + (by - p["h"] / 2) / sfy, 0] if fit else [bx, by, 0]

    names = ["anchorX", "anchorY", "w", "h"]
    pr = node["props"]
    ks = {"a": build(node, names, anchor, ctx, "anchor"),
          "s": build(node, ["scale", "scaleX", "scaleY"],
                     lambda p: [p["scale"] * p["scaleX"] * sfx * 100, p["scale"] * p["scaleY"] * sfy * 100, 100], ctx, "scale"),
          "r": build(node, ["rotation"], lambda p: p["rotation"], ctx, "rotation"),
          "o": build(node, ["opacity"], lambda p: p["opacity"] * 100, ctx, "opacity")}
    if node.get("anim", {}).keys() & {"x", "y"}:                    # keyed apart: Lottie's split position
        ks["p"] = {"s": True, "x": build(node, ["x"], lambda p: p["x"], ctx, "x"), "y": build(node, ["y"], lambda p: p["y"], ctx, "y")}
    else:
        ks["p"] = {"a": 0, "k": [pr["x"], pr["y"], 0]}
    return ks


def _mask(mask: dict, ctx: Ctx, first: bool) -> dict:
    props = frozen(mask, ["angle", "feather", "invert"], ctx, "a Lottie mask can't follow it")
    node = {**mask, "props": props, "anim": {k: v for k, v in mask.get("anim", {}).items() if k not in ("angle", "feather")}}
    if props["feather"] > 0:
        ctx.say(f'mask "{mask["id"]}": soft edge (feather {props["feather"]:g} px) is not in Lottie; the edge is hard')

    def pt(p):
        w, h = max(p["w"], 0.01), max(p["h"], 0.01)         # never degenerate: a shape keeps its point count across keyframes
        d = pathdata.ellipse(w, h) if p["shape"] == "ellipse" else pathdata.rect(w, h, max(p["radius"], 0.001) if props["radius"] > 0 else 0)
        d = pathdata.write(pathdata.transformed(pathdata.commands(d), lambda x, y: (x + p["x"], y + p["y"])))
        return shape_value(d, props["angle"], (p["x"] + w / 2, p["y"] + h / 2))

    return {"nm": mask["id"], "inv": bool(props["invert"]), "mode": "a" if first else "i", "o": {"a": 0, "k": 100},
            "x": {"a": 0, "k": 0}, "pt": build(node, ["x", "y", "w", "h", "radius"], pt, ctx, f'mask "{mask["id"]}"', bake=props["radius"] > 0 and props["shape"] == "rect")}


def clip_mask(node: dict) -> dict:
    """A group's `clip` as a mask over its own box (so it follows w, h when they are keyed)."""
    w, h = node["props"]["w"], node["props"]["h"]
    props = {"shape": "rect", "x": 0, "y": 0, "w": w, "h": h, "radius": 0, "feather": 0, "invert": False, "angle": 0}
    return {"id": "clip", "props": props, "anim": {k: v for k, v in node.get("anim", {}).items() if k in ("w", "h")}}


def common(node: dict, ctx: Ctx, ty: int, ind: int, extra_masks: list[dict] = ()) -> dict:
    """The fields every layer shares; the caller adds `shapes` / `refId` and `ip`, `op` are set here."""
    pr = node["props"]
    masks = [*extra_masks, *node.get("masks", [])]
    for key in ("tiltX", "tiltY"):
        if pr[key] != 0 or key in node.get("anim", {}):
            ctx.say("2.5D tilt is not in Lottie; the layer is drawn flat")
            break
    for fx in node.get("effects", []):             # a gradient is a fill (lottie_shapes / lottie_text); any other is said
        if fx["type"] != "gradient":
            ctx.say(f'{EFFECT_SAYS.get(fx["type"], fx["type"])} effect is not exported (Lottie players ignore effects)')
    layer = {"ddd": 0, "ind": ind, "ty": ty, "nm": node["id"], "sr": 1, "ks": transform(node, ctx),
             "ao": 0, "ip": round(pr["start"] * ctx.fps, 4), "op": round(min(pr["end"], ctx.duration) * ctx.fps, 4),
             "st": 0, "bm": blends.LOTTIE[pr["blend"]]}
    if pr.get("ridePath") or "ridePath" in node.get("anim", {}):
        layer["ks"].update(ride_keys(node, ctx))
    if masks:
        layer["hasMask"] = True
        layer["masksProperties"] = [_mask(m, ctx, i == 0) for i, m in enumerate(masks)]
    return layer
