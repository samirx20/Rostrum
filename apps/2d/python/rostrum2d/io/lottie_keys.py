"""Our keys → Lottie keyframes (bodymovin 5.x). A key's ease shapes the stretch that starts at it.

Named eases, `custom` and `linear` become the keyframe's bezier handles (`o` out, `i` in); `hold` is `h: 1`.
`spring` and `bounce` are not one bezier, nor is a stretch bent by spatial handles (a number key's `out` / `in`,
rostrum_core.keys.spatial): they are baked, one keyframe per frame over that stretch. Colours mix in
linear light in ours and in sRGB in Lottie: colour stretches are baked per frame too, so the picture matches.
`expand` gives the keys in OUR value space; `emit` turns them into Lottie keyframes through a value mapper.
"""
from __future__ import annotations

import math

from rostrum_core.keys import BEZIERS, ease
from rostrum_core.keys import mix_color
from rostrum_core.keys.spatial import between

LINEAR = (0.0, 0.0, 1.0, 1.0)


def handles(key: dict) -> tuple | None:
    """The key's ease as bezier points (x1, y1, x2, y2); None when it is not one bezier (hold, spring, bounce)."""
    name = key.get("ease", "smooth")
    if name == "linear":
        return LINEAR
    if name in BEZIERS:
        return BEZIERS[name]
    if name == "custom":
        return tuple(key.get(k, d) for k, d in (("x1", 0.25), ("y1", 0.1), ("x2", 0.25), ("y2", 1.0)))
    return None


def _value(key: dict):
    return key["c"] if "c" in key else key["v"]


def _mix(ka: dict, kb: dict, p: float, color: bool):
    return mix_color(ka["c"], kb["c"], min(1.0, max(0.0, p))) if color else between(ka, kb, p)


def expand(keys: list[dict], fps: float) -> tuple[list[dict], bool]:
    """Sorted keys → [{"t": frame, "v": value, "seg": (x1, y1, x2, y2) | "hold" | None}], and whether anything was baked.
    `seg` describes the stretch from this keyframe to the next."""
    keys, out, baked = sorted(keys, key=lambda k: k["t"]), [], False
    color = "c" in keys[0]
    for a, b in zip(keys, keys[1:]):
        name, va = a.get("ease", "smooth"), _value(a)
        if name == "hold":
            out.append({"t": a["t"] * fps, "v": va, "seg": "hold"})
            continue
        bez = handles(a)
        if bez is not None and not color and "out" not in a and "in" not in b:
            out.append({"t": a["t"] * fps, "v": va, "seg": bez})
            continue
        baked = True                                           # spring, bounce, or any colour stretch: a keyframe per frame
        fa, fb = a["t"] * fps, b["t"] * fps
        out.append({"t": fa, "v": va, "seg": LINEAR})
        for f in range(math.floor(fa) + 1, math.ceil(fb)):
            p = ease(a, (f - fa) / (fb - fa))
            out.append({"t": float(f), "v": _mix(a, b, p, color), "seg": LINEAR})
    out.append({"t": keys[-1]["t"] * fps, "v": _value(keys[-1]), "seg": None})
    return out, baked


def _s(v) -> list:
    return v if isinstance(v, list) else [v]


def emit(steps: list[dict], mapper) -> list[dict]:
    """The expanded keys → Lottie keyframes; `mapper` turns our value into Lottie's (number, list or shape dict)."""
    frames = []
    for st in steps:
        kf = {"t": round(st["t"], 4), "s": _s(mapper(st["v"]))}
        if st["seg"] == "hold":
            kf["h"] = 1
        elif st["seg"]:
            x1, y1, x2, y2 = st["seg"]
            kf["o"] = {"x": [x1], "y": [y1]}
            kf["i"] = {"x": [x2], "y": [y2]}
        frames.append(kf)
    return frames
