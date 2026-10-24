"""Several older cameras (or one that doesn't show all the time) turned into one frame's track, shot by shot (format
2 → 3, convert.py). At each frame the camera showing is the later one in the list (the old rule); no camera showing
holds home. For each run of frames one camera shows (a shot), its keys inside the run are copied; at the run's start
a key with the value it has there; the run's last key holds (ease hold) up to the next shot's first key: a cut. The
cameras come with their times in scene seconds (retime.py); a shot whose camera was timed on a shared marker gets its
keys back on that marker, and the cut into it too, so moving the marker still moves the cut.

A stretch of a camera's move that a run cuts in two is split exactly when its ease is linear, hold or a curve (a
curve's part is a curve again: split.py); a spring, a bounce, a bent path and a camera riding a path get a key per
frame there, said in the label."""
from __future__ import annotations

import math

from rostrum_core.keys import marked
from rostrum_core.keys.ops import key_id
from rostrum_core.marker_times import lookup

from .. import fields as F
from ..evaluate import value_at
from .split import curve_of, sub

MOVE = ("x", "y", "zoom", "rotation")
SPLITS = ("linear", "hold")
SHAPE = ("x1", "y1", "x2", "y2", "stiffness", "damping", "bounce", "speed")     # a key's own curve, copied with it


def _showing(cams: list[dict], t: float) -> dict | None:
    return next((c for c in reversed(cams) if c.get("start", 0.0) <= t < c.get("end", F.param("shape", "end").default)), None)


def _runs(cams, n_frames, fps):
    """[(camera or None, first frame, last frame)] over the scene."""
    runs = []
    for n in range(n_frames + 1):
        cam = _showing(cams, n / fps)
        if runs and runs[-1][0] is cam:
            runs[-1][2] = n
        else:
            runs.append([cam, n, n])
    return runs


def _keys(cam: dict, prop: str) -> list[dict]:
    return sorted((k for k in cam.get("keys", []) if k.get("prop") == prop and isinstance(k.get("t"), (int, float))),
                  key=lambda k: k["t"])


def _value(cam, prop, t, comp):
    if cam.get("ridePath"):
        from ..follow import ride
        got = ride(cam, comp["layers"], t, value_at)
        if got and prop in got:
            return float(got[prop])
    return float(value_at(cam, prop, t))


def _part(k0: dict | None, k1: dict | None, prop: str, t: float, nxt: float) -> tuple | None:
    """The ease and curve of the part t..nxt of the stretch from k0 to k1 (None: before the first key or after the
    last, where the value holds), or None when it can't be written exactly (a spring, a bounce, a bent path)."""
    if k0 is None or k1 is None:
        return "linear", {}
    if prop in ("x", "y") and ("out" in k0 or "in" in k1):
        return None
    if k0.get("ease", "smooth") in SPLITS:
        return k0.get("ease", "smooth"), {}
    curve = curve_of(k0)
    if curve is None:
        return None
    span = k1["t"] - k0["t"]
    got = sub(curve, (t - k0["t"]) / span, (nxt - k0["t"]) / span)
    return ("linear", {}) if got is None else ("custom", dict(zip(("x1", "y1", "x2", "y2"), got[0])))


def _run_keys(cam, prop, a, b, fps, comp, baked: list) -> list[tuple]:
    """(t, value, ease, curve) for one field over one shot's frames a..b (seconds), copied where exact, else baked."""
    ks = _keys(cam, prop)
    if cam.get("ridePath") or any(k.get("after", "stay") != "stay" for k in ks):
        baked.append(f'{cam["id"]}.{prop}: {a:g} s to {b:g} s, a key per frame')
        return [(n / fps, _value(cam, prop, n / fps, comp), "linear", {}) for n in range(round(a * fps), round(b * fps) + 1)]
    times = [a, *[k["t"] for k in ks if a < k["t"] < b], *([b] if b > a else [])]
    out, carry = [], None            # carry: the key whose `in` handle ends a stretch copied whole
    for i, t in enumerate(times):
        k0 = next((k for k in reversed(ks) if k["t"] <= t), None)
        k1 = next((k for k in ks if k["t"] > t), None)
        nxt = times[i + 1] if i + 1 < len(times) else None
        ends = {"in": carry["in"]} if carry is not None and carry["t"] == t and "in" in carry else {}
        carry = None
        if k0 is not None and k0["t"] == t and (nxt is None or (k1 is not None and nxt == k1["t"])):
            out.append((t, k0["v"], k0.get("ease", "smooth"), {**ends, **{s: k0[s] for s in (*SHAPE, "out") if s in k0}}))
            carry = k1                                   # a whole stretch: as it was
        elif nxt is None:
            out.append((t, _value(cam, prop, t, comp), "linear", ends))
        elif (part := _part(k0, k1, prop, t, nxt)) is not None:
            out.append((t, _value(cam, prop, t, comp), part[0], {**ends, **part[1]}))
        else:
            baked.append(f'{cam["id"]}.{prop}: {t:g} s to {nxt:g} s, a key per frame')
            out.append((t, _value(cam, prop, t, comp), "linear", ends))
            out += [(n / fps, _value(cam, prop, n / fps, comp), "linear", {})
                    for n in range(math.floor(t * fps) + 1, math.ceil(nxt * fps)) if t < n / fps < nxt]
    return out


def _written(t: float, tie: str | None, markers: dict):
    """A key time as written: on the shot's marker when its camera was timed on one, else seconds."""
    at = lookup(markers, tie) if tie else None
    return t if at is None else marked.write(tie, round(t - at, 6))


def track(comp: dict, cams: list[dict], frame: dict, markers: dict | None = None) -> list[str]:
    """Fill `frame`'s keys from the cameras (times in scene seconds); returns what was baked or left out, in words."""
    d = F.defaults("comp")
    fps, dur = float(comp.get("fps", d["fps"])), float(comp.get("duration", d["duration"]))
    home = {"x": frame["homeX"], "y": frame["homeY"], "zoom": 1.0, "rotation": 0.0}
    runs, baked, notes = _runs(cams, max(1, math.ceil(dur * fps - 1e-9)), fps), [], []
    keys = []
    for prop in MOVE:
        track_ = []                                          # (t, value, ease, curve, the marker it sits on)
        for cam, n0, n1 in runs:
            a, b = n0 / fps, n1 / fps
            got = [(a, home[prop], "linear", {})] if cam is None else _run_keys(cam, prop, a, b, fps, comp, baked)
            tie = (cam or {}).get("marker") or None
            if track_:
                t, v, _, curve, before = track_[-1]
                track_[-1] = (t, v, "hold", {}, tie or before)   # the cut: the shot before holds up to this one
            track_ += [(*g, tie) for g in got]
        if len({v for _, v, *_ in track_}) > 1:
            for t, v, e, curve, tie in track_:
                w = _written(t, tie, markers or {})
                keys.append({"id": key_id(frame["id"], prop, w), "type": "key", "prop": prop, "t": w, "v": v, "ease": e, **curve})
        else:
            frame[prop] = track_[0][1]
    frame["keys"] = keys
    if any(c.get("exprs") for c in cams):
        notes.append("expressions on the cameras were left out (set them on the frame)")
    shots_ = sum(1 for r in runs if r[0] is not None)
    return [f"{shots_} shot{'s' * (shots_ != 1)} with cuts", *dict.fromkeys(baked), *notes]
