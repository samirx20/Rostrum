"""Which parts of an MP4 export need drawing again: the film is cut into segments of SEGMENT_S seconds (the encoder's
picture group, so segments drawn together split apart without re-encoding; a cut at a layer's start or end would
need its own engine request, ~1.5 s each), and each segment gets a key from everything that can change its pictures. A segment whose key is in the cache (export_cache.py) is reused as it is; only the others are drawn.

A segment's key: the engine build, the composition's own props and everything on it but its layers, the encoder
settings, the segment's frames, and every top-level layer whose time window (its start / end, widened by what reaches
across frames: motion blur, trails, smears) could touch the segment. The frame (camera) counts for every segment, as
does a layer with no start / end or one that reaches over time in a way not read here. Files a layer names (pictures,
videos, painted frames) count by their size and date, so a file changed on disk under the same name is drawn again.
When unsure, a layer counts for every segment: a wrong reuse would be a silent wrong frame.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

from rostrum2d import settings

SEGMENT_S = 2.0              # seconds per segment: a one-section change redraws a few seconds, not the film
EPS = 1e-6                   # frames: a layer time this close to a frame's time is on it
EVERY = None                 # a window that touches every segment


def plan(scene: dict, start: float, end: float) -> list[tuple[int, int]]:
    """[(first frame, end frame)] of the export (frames counted from `start`), covering it with no gap: SEGMENT_S each,
    the encoder's picture group (engine encode_mp4.rs: a key picture every fps × 2 frames), so a run of segments drawn
    in one go splits into them without re-encoding (export_cache.py)."""
    fps = scene["comp"]["props"]["fps"]
    total = max(1, round((end - start) * fps))
    seg = max(1, round(SEGMENT_S * fps))
    return [(a, min(a + seg, total)) for a in range(0, total, seg)]


def keys(scene: dict, cuts: list[tuple[int, int]], start: float, encode: dict) -> list[str]:
    """One key per segment of `cuts` (see the module's words)."""
    comp, fps = scene["comp"], scene["comp"]["props"]["fps"]
    base = _hash({"engine": engine_stamp(), "format": scene.get("format"), "version": scene.get("version"),
                  "comp": {k: v for k, v in comp.items() if k != "layers"}, "encode": encode, "start": start})
    every, timed = [], []
    for lay in comp.get("layers", []):
        h = _hash({"node": lay, "files": _files(lay)})
        win = None if lay.get("type") == "camera" else window(lay, fps, start)
        (every if win is EVERY else timed).append((h, win))
    out = []
    for a, b in cuts:
        touching = [h for h, _ in every] + [h for h, (lo, hi) in timed if lo <= b - 1 and hi >= a]
        out.append(_hash([base, a, b, touching]))
    return out


def window(node: dict, fps: float, start: float):
    """(first, last) frame of the export the layer may show in, widened by its reach; EVERY when not known. The engine
    shows a layer in a frame when start <= the frame's time < end (scene/eval.rs); a time within EPS frames of a frame
    counts as on it (the frame times and the layer's own are the same sums in both)."""
    p = node.get("props") or {}
    if not isinstance(p.get("start"), (int, float)) or not isinstance(p.get("end"), (int, float)):
        return EVERY
    reach = _reach(node, fps)
    lo = math.ceil((p["start"] - start) * fps - EPS) - reach
    hi = math.ceil((p["end"] - start) * fps - EPS) - 1 + reach
    return lo, hi


def _reach(node: dict, fps: float):
    """Frames a layer's look reaches across in time (the most in its whole tree): motion blur's shutter, a trail's copies
    × spacing, a smear's frames either side. A video's or a loop's own clock is a function of the time, so it needs none."""
    most = 0
    for n in _walk(node):
        p = n.get("props") or {}
        if n.get("type") == "trail":
            most = max(most, math.ceil(p.get("copies", 32) * p.get("spacing", 30)))
        elif n.get("type") == "smear":
            most = max(most, 2)
        if isinstance(p.get("shutter"), (int, float)) and p["shutter"] > 0:
            most = max(most, math.ceil(p["shutter"] / 360) + 1)
    return most


def _walk(node):
    """Every node dict in a layer's tree (its effects, masks, layers, rig, stops …)."""
    if isinstance(node, dict):
        if "type" in node:
            yield node
        for v in node.values():
            if isinstance(v, (dict, list)):
                yield from _walk(v)
    elif isinstance(node, list):
        for v in node:
            yield from _walk(v)


def _files(node) -> list:
    """(path, size, date) of every existing file a layer's description names."""
    found = []

    def look(v):
        if isinstance(v, dict):
            for x in v.values():
                look(x)
        elif isinstance(v, list):
            for x in v:
                look(x)
        elif isinstance(v, str) and len(v) < 1024 and ("/" in v or "\\" in v):
            try:
                st = Path(v).stat()
            except (OSError, ValueError):
                return
            if Path(v).is_file():
                found.append((v, st.st_size, st.st_mtime_ns))
    look(node)
    return sorted(found)


def engine_stamp() -> list:
    """The engine builds that may draw (their size and date): a rebuilt engine draws every segment again."""
    out = []
    for p in settings.engine_candidates():
        try:
            st = p.stat()
        except OSError:
            continue
        out.append((str(p), st.st_size, st.st_mtime_ns))
    return out


def _hash(v) -> str:
    return hashlib.sha256(json.dumps(v, sort_keys=True, separators=(",", ":"), default=str).encode()).hexdigest()[:32]
