"""A path's varied stroke (taperStart / taperEnd / widthProfile) as Lottie shapes.

Lottie has no variable-width stroke, so it is carried as a FILLED OUTLINE. The outline's geometry is the engine's own
(`Engine.outline`, engine scene/outline_cmd.rs): nothing of it is worked out here. A still stroke is one outline; when
the path, trim, width, taper or dashes are keyed, the outline is asked for at every frame of the keyed range and each
frame is a hold keyframe (a morph between two outlines of different point counts would be wrong). The engine is opened
on the first varied path and closed at the end of the export.
"""
from __future__ import annotations

import math

from .lottie_shapes import _subpaths, shape_value

AFFECTS = ("d", "trimStart", "trimEnd", "strokeWidth", "taperStart", "taperEnd", "widthProfile", "dash", "gap", "dashOffset")


def varied(props: dict) -> bool:
    return bool(props.get("stroke")) and props.get("strokeWidth", 0) > 0 and (
        props.get("taperStart", 0) > 0 or props.get("taperEnd", 0) > 0 or props.get("widthProfile", "") != "")


class Outlines:
    def __init__(self, scene: dict):
        self.scene, self._eng, self._failed = scene, None, False

    def close(self) -> None:
        if self._eng:
            self._eng.close()
            self._eng = None

    def _engine(self, ctx):
        if self._failed:
            return None
        if self._eng is None:
            try:
                from ..engine import Engine, EngineError
                eng = Engine()
                try:
                    eng.load(self.scene)
                except EngineError:
                    eng.close()
                    raise
                self._eng = eng
            except Exception as e:           # no engine built, or it refused the scene: said once, the stroke is even
                self._failed = True
                ctx.say(f"tapered / width-profile stroke: the engine is not available ({e}); exported as an even stroke")
        return self._eng

    def shapes(self, node: dict, ctx) -> list[dict] | None:
        """The Lottie `sh` items of the node's varied stroke, or None when it has none (or no engine)."""
        if not varied(node["props"]):
            return None
        eng = self._engine(ctx)
        if eng is None:
            return None
        anim = node.get("anim", {})
        keyed = [n for n in AFFECTS if n in anim]
        if not keyed:
            frames = [(0.0, eng.outline(node["id"], 0.0))]
        else:
            keys = [sorted(anim[n], key=lambda k: k["t"]) for n in keyed]
            f0 = math.floor(min(k[0]["t"] for k in keys) * ctx.fps)
            f1 = math.ceil(max(k[-1]["t"] for k in keys) * ctx.fps)
            frames = [(float(f), eng.outline(node["id"], f / ctx.fps)) for f in range(f0, f1 + 1)]
            ctx.say(f'varied stroke: {" and ".join(keyed)} change it; the outline is baked as a keyframe every frame')
        return _items(frames)


def _shape(d: str | None) -> dict:
    return shape_value(d) if d else {"c": True, "v": [], "i": [], "o": []}


def _items(frames: list[tuple[float, str]]) -> list[dict]:
    """[(frame, outline d)] → one `sh` per subpath. A frame with fewer subpaths than the most gets an empty shape."""
    per = [(f, _subpaths(d) if d else []) for f, d in frames]
    n = max((len(s) for _, s in per), default=0)
    if len(frames) == 1:
        return [{"ty": "sh", "nm": "outline", "ks": {"a": 0, "k": _shape(s)}} for s in per[0][1]]
    items = []
    for i in range(n):
        kf = [{"t": f, "s": [_shape(subs[i] if i < len(subs) else None)], "h": 1} for f, subs in per]
        items.append({"ty": "sh", "nm": "outline", "ks": {"a": 1, "k": kf}})
    return items
