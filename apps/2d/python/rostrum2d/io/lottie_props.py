"""One Lottie property ({"a": 0|1, "k": …}) from one or more of our fields.

A Lottie property can depend on several of our fields (a layer's scale is scale · scaleX; its anchor is a fraction
of the box in ours and px in Lottie). `build` gives still ones as values; with ONE keyed source the keys are mapped
(an affine map keeps the easing exact); with several keyed sources it bakes a keyframe per frame and says so.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from rostrum_core.keys import key_value, track_value
from .lottie_keys import LINEAR, emit, expand


@dataclass
class Ctx:
    fps: float
    duration: float
    report: list[str] = field(default_factory=list)     # what will differ from the preview
    baked: list[str] = field(default_factory=list)      # what is carried as a keyframe every frame: looks the same, bigger file
    layer: str = ""
    outlines: object = None          # lottie_outline.Outlines: asks the engine for varied-stroke outlines
    siblings: list = field(default_factory=list)   # the scene nodes beside the current layer (a rider's path is one)

    def say(self, text: str) -> None:
        line = f'layer "{self.layer}": {text}'
        if line not in self.report:
            self.report.append(line)

    def bake(self, text: str) -> None:
        """Carried exactly, as a keyframe every frame: not a difference, so not in the report."""
        line = f'layer "{self.layer}": {text}'
        if line not in self.baked:
            self.baked.append(line)


def rgb(hex_: str) -> list[float]:
    """#rrggbb → Lottie's [r, g, b, 1] (0..1, sRGB)."""
    return [int(hex_[i:i + 2], 16) / 255 for i in (1, 3, 5)] + [1]


def frozen(node: dict, names: list[str], ctx: Ctx, why: str) -> dict:
    """The node's props with each keyed field in `names` held at its first key; the report says so."""
    props = dict(node["props"])
    for n in names:
        if n in node.get("anim", {}):
            keys = sorted(node["anim"][n], key=lambda k: k["t"])
            props[n] = key_value(keys[0])
            ctx.say(f'"{n}" is keyed but {why}; held at its first value')
    return props


def build(node: dict, names: list[str], f, ctx: Ctx, what: str = "", bake: bool = False) -> dict:
    """The Lottie property for f(values) where values = the node's props (animated ones evaluated).
    `bake`: a keyframe per frame even for one keyed field (f is not affine in it: a rounded rect's corners)."""
    props, anim = node["props"], node.get("anim", {})
    keyed = [n for n in names if n in anim]
    if not keyed:
        return {"a": 0, "k": f(props)}
    if len(keyed) == 1 and not bake:
        n = keyed[0]
        steps, baked = expand(anim[n], ctx.fps)
        if baked:
            kind = "colour mixes in linear light in ours, sRGB in Lottie" if "c" in anim[n][0] else "spring / bounce is not one bezier"
            ctx.bake(f'{what or n}: {kind}')
        return {"a": 1, "k": emit(steps, lambda v: f({**props, n: v}))}
    keys = {n: sorted(anim[n], key=lambda k: k["t"]) for n in keyed}
    t0 = min(k[0]["t"] for k in keys.values())
    t1 = max(k[-1]["t"] for k in keys.values())
    f0, f1 = int(t0 * ctx.fps), int(t1 * ctx.fps + 0.999)
    steps = []
    for fr in range(f0, f1 + 1):
        values = {**props, **{n: track_value(ks, fr / ctx.fps) for n, ks in keys.items()}}
        steps.append({"t": float(fr), "v": values, "seg": LINEAR if fr < f1 else None})
    ctx.bake(f'{what or "/".join(keyed)}: {" and ".join(keyed)} drive one Lottie value together')
    return {"a": 1, "k": emit(steps, f)}
