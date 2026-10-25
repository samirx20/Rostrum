"""Export through the engine's one render path (the same as the video / preview), then read the result back."""
from __future__ import annotations

from pathlib import Path

from ..engine import Engine, EngineError
from . import formats, readback


def _engine_request(eng: Engine, req: dict, **kw) -> dict:
    # The one private use (reloading at another depth); the export itself goes through Engine.export, which watches it.
    return eng._request(req, **kw)


def export(eng: Engine, fmt: str, out, alpha: bool | None = None, depth: int | None = None,
           start: float = 0.0, end: float | None = None, progress=None, quality: str | None = None,
           bitrate: float | None = None, gif: dict | None = None) -> dict:
    """Export the engine's loaded scene (seconds `start`..`end`) as `fmt`; returns the facts read back from the file.
    `quality` (formats.QUALITY) or an exact `bitrate` (Mbit/s): for the formats that take one (mp4). `gif`: its {size, rate}
    (formats.GIF_SIZES, GIF_RATES; the defaults when left out)."""
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
    rate = formats.rate(f, w, h, fps, quality, bitrate)
    out = Path(out)
    target = str(out) if f.video else formats.pattern(f, out)
    Path(target).parent.mkdir(parents=True, exist_ok=True)
    first = f.first + round(start * fps)
    n = max(1, round((end - start) * fps))                       # the engine's own count of the frames it sends
    shape = formats.gif_shape(w, h, fps, n, **{**formats.GIF_DEFAULTS, **(gif or {})}) if fmt == "gif" else None
    encode = formats.gif_encode(target, w, h, fps, **{**formats.GIF_DEFAULTS, **(gif or {})}) if fmt == "gif"         else f.build(target, w, h, fps, depth, first, rate)
    req = {"start": start, "end": end, "alpha": alpha, "encode": encode}
    if f.video:
        req["file"] = target
    if depth != 8:                                   # the engine sends 16-bit frames only while loaded that way
        _engine_request(eng, {"scene": eng.scene, "depth": depth})
    try:
        reply = eng.export(req, progress)                     # watched: a frame stuck over FRAME_LIMIT_S fails it, named
    finally:
        if depth != 8:
            _engine_request(eng, {"scene": eng.scene, "depth": 8})
    if shape:                                        # a GIF has its own size, rate and frame count
        w, h, fps, count = shape
    else:
        count = reply["frames"]
    facts = readback.check(fmt, target, count, w, h, alpha, depth, seconds=(end - start) if shape else None)
    return {"file": target, "frames": count, "fps": fps, **({"seconds": end - start} if shape else {}), "alpha": alpha, "depth": depth, "checked": facts,
            **({"kbps": rate.kbps} if rate.kbps and rate.quality is None else {}),
            **({"quality": quality or formats.DEFAULT_QUALITY} if rate.quality is not None else {}),
            **(encoded(reply["encoder"]) if reply.get("encoder") else {})}


def encoded(encoder: dict) -> dict:
    """Which encoder made the MP4 (the engine's reply `encoder`: its name, on the graphics card or not), in words."""
    return {"encoded": "on the graphics card" if encoder["gpu"] else "on the processor", "encoder": encoder["name"]}
