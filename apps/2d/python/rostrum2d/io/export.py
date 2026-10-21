"""Export through the engine's one render path (the same as the video / preview), then read the result back."""
from __future__ import annotations

from pathlib import Path

from ..engine import Engine, EngineError
from . import formats, readback


def _engine_request(eng: Engine, req: dict, **kw) -> dict:
    # The one private use: Team Sam is asked for a public Engine method (export with encode / alpha / depth).
    return eng._request(req, **kw)


def _png_pattern(out: Path) -> str:
    """A png export writes many files: `out` is a pattern holding {frame}, or a folder / stem it is made from."""
    s = str(out)
    if "{frame}" in s:
        return s
    stem = out.with_suffix("") if out.suffix.lower() == ".png" else out
    return f"{stem}_{{frame}}.png"


def export(eng: Engine, fmt: str, out, alpha: bool | None = None, depth: int | None = None,
           start: float = 0.0, end: float | None = None, progress=None) -> dict:
    """Export the engine's loaded scene (seconds `start`..`end`) as `fmt`; returns the facts read back from the file."""
    f = formats.get(fmt)
    if eng.scene is None:
        raise EngineError("no scene loaded (Engine.load)")
    alpha = f.alpha if alpha is None else alpha
    if alpha and not f.alpha:
        raise ValueError(f"{fmt} cannot carry alpha; use one of "
                         f"{', '.join(n for n, x in formats.FORMATS.items() if x.alpha)}")
    depth = f.depths[0] if depth is None else depth
    if depth not in f.depths:
        raise ValueError(f"{fmt} takes {' or '.join(map(str, f.depths))} bits per channel, not {depth}")
    p = eng.scene["comp"]["props"]
    w, h, fps = p["width"], p["height"], p["fps"]
    end = p["duration"] if end is None else end
    out = Path(out)
    target = _png_pattern(out) if fmt == "png" else str(out)
    Path(target).parent.mkdir(parents=True, exist_ok=True)
    first = round(start * fps)
    req = {"start": start, "end": end, "alpha": alpha, "progress": progress is not None,
           "encode": f.build(target, w, h, fps, depth, first)}
    if f.video:
        req["file"] = target
    if depth != 8:                                   # the engine sends 16-bit frames only while loaded that way
        _engine_request(eng, {"scene": eng.scene, "depth": depth})
    try:
        reply = _engine_request(eng, {"export": req}, timeout_s=3600.0, progress=progress)
    finally:
        if depth != 8:
            _engine_request(eng, {"scene": eng.scene, "depth": 8})
    facts = readback.check(fmt, target, reply["frames"], w, h, alpha, depth)
    return {"file": target, "frames": reply["frames"], "fps": fps, "alpha": alpha, "depth": depth, "checked": facts}
