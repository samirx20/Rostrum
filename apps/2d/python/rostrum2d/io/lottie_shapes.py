"""Shape and path layers → the `shapes` list of a Lottie shape layer.

Lottie draws the items of a group top-first, so a stroke group is listed above the fill group. Our shape outline is
drawn INSIDE the box, Lottie centres a stroke on the line: the outline's geometry is inset by half its width. The
stroke and the fill each get their own group so a trim (ours trims the stroke only) never cuts the fill.
"""
from __future__ import annotations

import math

from .. import pathdata
from .lottie_props import Ctx, build, frozen, rgb

CAP, JOIN, RULE = {"butt": 1, "round": 2, "square": 3}, {"miter": 1, "round": 2, "bevel": 3}, {"nonzero": 1, "evenodd": 2}
_TR = {"ty": "tr", "p": {"a": 0, "k": [0, 0]}, "a": {"a": 0, "k": [0, 0]}, "s": {"a": 0, "k": [100, 100]},
       "r": {"a": 0, "k": 0}, "o": {"a": 0, "k": 100}, "sk": {"a": 0, "k": 0}, "sa": {"a": 0, "k": 0}}
_STILL = lambda v: {"a": 0, "k": v}  # noqa: E731


def group(name: str, items: list[dict]) -> dict:
    return {"ty": "gr", "nm": name, "it": [*items, dict(_TR)]}


def shape_value(d: str, rotate: float = 0.0, about=(0.0, 0.0)) -> dict:
    """Path data → one Lottie bezier shape (first subpath), optionally turned about a point."""
    sub = pathdata.to_points(d)[0]
    c, s = math.cos(math.radians(rotate)), math.sin(math.radians(rotate))
    turn = lambda x, y: [x * c - y * s, x * s + y * c]  # noqa: E731
    pts = sub["points"]
    verts = [turn(p["x"] - about[0], p["y"] - about[1]) for p in pts]
    return {"c": sub["closed"], "v": [[about[0] + x, about[1] + y] for x, y in verts],
            "i": [turn(*p["in"]) for p in pts], "o": [turn(*p["out"]) for p in pts]}


def _geometry(node: dict, ctx: Ctx, inset: bool) -> list[dict]:
    """The rect / ellipse of a shape layer (inset by half the outline width for the stroke)."""
    pr = node["props"]
    w = lambda p: p["strokeWidth"] if inset else 0.0  # noqa: E731
    size = build(node, ["w", "h", "strokeWidth"], lambda p: [max(p["w"] - w(p), 0), max(p["h"] - w(p), 0)], ctx, "size")
    pos = build(node, ["w", "h"], lambda p: [p["w"] / 2, p["h"] / 2], ctx, "size")
    if pr["shape"] == "ellipse":
        return [{"ty": "el", "nm": "ellipse", "d": 1, "s": size, "p": pos}]
    rad = build(node, ["radius", "strokeWidth"], lambda p: max(p["radius"] - w(p) / 2, 0), ctx, "corner radius")
    return [{"ty": "rc", "nm": "rect", "d": 1, "s": size, "p": pos, "r": rad}]


def gradient(effect: dict | None, node: dict, ctx: Ctx, stroke: bool = False) -> dict | None:
    """A gradient effect → Lottie gradient fill (`gf`) or stroke (`gs`); None (and a report) for conic."""
    if effect is None:
        return None
    g = frozen(effect, list(effect["props"]), ctx, "a Lottie gradient can't follow it")
    if g["style"] == "conic":
        ctx.say("conic gradient is not in Lottie; the plain colour is used instead")
        return None
    w, h = node["props"]["w"], node["props"]["h"]
    stops = [(0.0, g["color1"])] + ([(g["mid"], g["color3"])] if g["middle"] else []) + [(1.0, g["color2"])]
    flat = [v for off, col in stops for v in (off, *rgb(col)[:3])]
    if g["style"] == "linear":
        a = math.radians(g["angle"])
        dx, dy, half = math.sin(a), -math.cos(a), (abs(w * math.sin(a)) + abs(h * math.cos(a))) / 2
        s, e, ty = [w / 2 - dx * half, h / 2 - dy * half], [w / 2 + dx * half, h / 2 + dy * half], 1
    else:
        cx, cy = g["cx"] * w, g["cy"] * h
        s, e, ty = [cx, cy], [cx + max(min(cx, w - cx, cy, h - cy), 0.0), cy], 2
    out = {"ty": "gs" if stroke else "gf", "nm": "gradient", "t": ty, "s": _STILL(s), "e": _STILL(e),
           "g": {"p": len(stops), "k": _STILL(flat)}, "o": _STILL(100), "h": _STILL(0), "a": _STILL(0)}
    return out


def _fill(node: dict, ctx: Ctx, grad: dict | None) -> dict:
    if grad:
        return {**grad, "r": 1}
    return {"ty": "fl", "nm": "fill", "c": build(node, ["fill"], lambda p: rgb(p["fill"]), ctx, "fill colour"),
            "o": _STILL(100), "r": 1}


def _stroke(node: dict, ctx: Ctx, grad: dict | None, path: bool) -> dict:
    pr = node["props"]
    st = {"ty": "st", "nm": "stroke", "o": _STILL(100), "lc": CAP[pr["cap"]] if path else 1, "lj": JOIN[pr["join"]] if path else 1,
          "ml": pr["miter"] if path else 4,
          "c": build(node, ["strokeColor"], lambda p: rgb(p["strokeColor"]), ctx, "stroke colour"),
          "w": build(node, ["strokeWidth"], lambda p: p["strokeWidth"], ctx, "stroke width")}
    if grad:
        st = {**grad, "o": _STILL(100), "w": st["w"], "lc": st["lc"], "lj": st["lj"], "ml": st["ml"]}
    if path and (pr["dash"] > 0 or "dash" in node.get("anim", {})):
        st["d"] = [{"n": n, "nm": nm, "v": build(node, [f], lambda p, f=f: p[f], ctx, nm)}
                   for n, nm, f in (("d", "dash", "dash"), ("g", "gap", "gap"), ("o", "offset", "dashOffset"))]
    return st


def _trim(node: dict, ctx: Ctx, multi: bool) -> dict | None:
    anim, pr = node.get("anim", {}), node["props"]
    if not (anim.keys() & {"trimStart", "trimEnd"}) and pr["trimStart"] == 0 and pr["trimEnd"] == 1:
        return None
    return {"ty": "tm", "nm": "trim", "m": 2 if multi else 1, "o": _STILL(0),
            "s": build(node, ["trimStart"], lambda p: p["trimStart"] * 100, ctx, "trim start"),
            "e": build(node, ["trimEnd"], lambda p: p["trimEnd"] * 100, ctx, "trim end")}


def shapes_of(node: dict, ctx: Ctx) -> list[dict]:
    """The `shapes` of a shape or path layer."""
    pr, effects = node["props"], node.get("effects", [])
    grad_fx = next((e for e in effects if e["type"] == "gradient"), None)
    grad = gradient(grad_fx, node, ctx)
    out = []
    if node["type"] == "shape":
        if pr["stroke"]:
            out.append(group("outline", [*_geometry(node, ctx, True), _stroke(node, ctx, None, False)]))
        return [*out, group("fill", [*_geometry(node, ctx, False), _fill(node, ctx, grad)])]
    held = frozen(node, ["d"], ctx, "the Lottie export doesn't morph paths yet")["d"]
    subs = [{"ty": "sh", "nm": "path", "ks": _STILL(shape_value(d))} for d in _subpaths(held)]
    if pr["stroke"]:
        trim = _trim(node, ctx, len(subs) > 1)
        sgrad = None if pr["filled"] else gradient(grad_fx, node, ctx, stroke=True)
        out.append(group("stroke", [*subs, *([trim] if trim else []), _stroke(node, ctx, sgrad, True)]))
    if pr["filled"]:
        rule = {**_fill(node, ctx, grad), "r": RULE[pr["fillRule"]]}
        out.append(group("fill", [*subs, rule]))
    return out


def _subpaths(d: str) -> list[str]:
    """`d` split at each M, so every subpath is one Lottie shape (a hole stays a hole under the even-odd rule)."""
    parts = [c for c in pathdata.commands(d)]
    out, cur = [], []
    for c in parts:
        if c[0] == "M" and cur:
            out.append(pathdata.write(cur))
            cur = []
        cur.append(c)
    return [*out, pathdata.write(cur)] if cur else out
