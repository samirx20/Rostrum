"""`item.sample(field, values, start=, end=, every=)`: a field keyed from plain Python, the script's own function of time
or a list of values, written as ordinary keys (one per frame, linear between), so anything a script can compute (a
spring it wrote, a noise walk, a value read from a table) drives a field without a formula language.

    dot.sample("y", lambda t: 540 + 80 * math.sin(t * 3), start=2, end=6)      # a function of comp seconds
    bar.sample("h", heights, start=4)                                          # a list: one value per frame from 4 s
    glow.sample("radius", wobble, start=0, end=30, every=2)                    # a key every 2 frames

item.expr keeps a formula in the document (a person reads and edits the formula); sample keeps keys (a person drags
them). Both draw the same in look_frame and the export. Times are the scene's frames, so a key lands on every frame.
"""
from __future__ import annotations

MOST = 5000                 # keys from one call: 30 s at 60 fps is 1800; more is almost always a mistake (a wrong end)


def _comp(build, node) -> dict:
    """The scene the item is in (its fps and length)."""
    for c in build.root["comps"]:
        stack = [c]
        while stack:
            n = stack.pop()
            if n is node:
                return c
            stack += [k for v in n.values() if isinstance(v, list) for k in v if isinstance(k, dict)]
    return build.holders[0] if build.holders else {}


def sample(item, prop, values, start=0.0, end=None, every=1, ease="linear"):
    """Key `prop` from `values` (a function of seconds, or a list: one value per `every` frames from `start`)."""
    from . import fields as F
    where = f"{item.id}.sample({prop!r}, …)"
    if not isinstance(start, (int, float)) or (end is not None and not isinstance(end, (int, float))):
        raise ValueError(f"{where}: start and end are seconds (numbers); a marker time like \"#drop\" works in .key()")
    if not isinstance(every, int) or every < 1:
        raise ValueError(f"{where}: every={every!r} is a whole number of frames, 1 or more")
    comp = _comp(item._b, item.node)
    fps = float(comp.get("fps") or F.defaults("comp")["fps"])
    step = every / fps
    if callable(values):
        last = float(comp.get("duration") or F.defaults("comp")["duration"]) if end is None else float(end)
        if last < start:
            raise ValueError(f"{where}: end {last} s is before start {start} s")
        n = int((last - start) / step + 1e-6) + 1
        times = [start + i * step for i in range(n)]
    elif isinstance(values, (list, tuple)):
        if end is not None:
            raise ValueError(f"{where}: a list sets its own length (one value per {every} frame(s)); leave end out")
        if not values:
            raise ValueError(f"{where}: the list is empty")
        times = [start + i * step for i in range(len(values))]
    else:
        raise ValueError(f"{where}: values is a function of time (lambda t: …, or a def) or a list of values, "
                         f"not a {type(values).__name__}")
    if len(times) > MOST:
        raise ValueError(f"{where}: {len(times)} keys; at most {MOST} from one call (check end, or use every=)")
    keys = {}
    for i, t in enumerate(times):
        t = round(t, 6)
        try:
            v = values(t) if callable(values) else values[i]
        except Exception as e:      # the script's own function failed: say at which time, with its own message
            raise ValueError(f"{where}: the function failed at t={t} s: {type(e).__name__}: {e}") from None
        keys[t] = (v, ease)
    return item.key(prop, keys)
