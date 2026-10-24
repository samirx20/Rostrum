"""One lip-sync job, shared by the operation, the script call and the MCP tool: phones (cached) → mouth cues → keys.
Times in the answer are comp seconds; `at` is where the clip's `start` lands in the comp."""
from __future__ import annotations

from rostrum_core import RostrumError, codes

from . import keys as K, phonemes, visemes

TIMING = {"lead_frames": 1.0, "min_frames": 1.0, "rest_gap": 0.25, "tail": 0.08}


def track(source, at: float, fps: float, shapes: dict | None = None, text: str | None = None, start: float = 0.0,
          end: float | None = None, language: str = "english", pronounce: dict | None = None,
          where: str = "lipsync", **timing) -> dict:
    unknown = set(timing) - set(TIMING)
    if unknown:
        raise RostrumError(codes.BAD_ARGUMENT, where, f"{sorted(unknown)}", "are not timing settings", list(TIMING))
    if at < 0:
        raise RostrumError(codes.BAD_ARGUMENT, where, "at", f"is {at}; the clip must start at 0 s or later")
    a = phonemes.analyse(source, start, end, text or None, language, pronounce, where)
    cues = visemes.cues(a["phones"], fps, start=start, end=a["end"], grid=start - at, **{**TIMING, **timing})
    out = {"source": str(source), "at": at, "clip": [start, a["end"]], "mode": a["mode"], "device": a["device"],
           "computed": a["computed"], "phones": [_comp(p, at, start) for p in a["phones"]],
           "words": [_comp(w, at, start) for w in a["words"]],
           "cues": [_comp(c, at, start) for c in cues]}
    if shapes:
        try:
            out["keys"], out["shown"] = K.plan(cues, K.check_shapes(shapes, where), at, start)
        except ValueError as e:
            raise RostrumError(codes.BAD_ARGUMENT, where, "shapes", str(e)) from e
    return out


def _comp(x: dict, at, start) -> dict:
    return {**x, "start": round(at + x["start"] - start, 4), "end": round(at + x["end"] - start, 4)}
