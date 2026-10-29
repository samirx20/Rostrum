"""Auto layout into the scene (layout.py is the solver): for a composition with any laid-out group, the x / y (and
w / h, a text's boxWidth) the layout gives each layer, solved at every frame from 0 to the composition's length and
written as `anim` keys, ease `linear` (exact at every frame), as expressions are (exprbake.py). The frames' layout trees
go to the engine together (FRAMES a request); a frame whose trees are the same as one before is not asked again. The engine sees plain keys and never
the layout fields; a field the layout sets overrides that field's own keys and any expression on it. A value that
never changes is one key. Layout reads the layers' values with their expressions applied (a card whose height is
an expression re-flows the others).

Each top-level layer's layout is solved on its own and kept (_KEPT) while it is the very same object (documents are
copy on write: an edit makes new objects only for what it touched), in the same composition settings, with the same
expression keys inside it: a script re-run that changed one section solves only that section again (a 70 s film:
~4 s for every frame of every section, before).
"""
from __future__ import annotations

import math
from bisect import bisect_left, bisect_right

from rostrum_core.keys import animated, keys_of, track_value
from rostrum_core.keys.after import after_of

from . import fields as F, textsize
from .evaluate import placed, resolve
from .exprbake import items_of
from .layout import Plan, has_layout, laid_out, lay_out, prime_texts

FRAMES = 60                 # frames' layout trees a request: one round trip a couple of seconds of film
KEEP = 512                  # top-level layers' solved layouts kept (oldest dropped)
_KEPT: dict[str, tuple] = {}   # top-level layer id -> (the layer object, comp settings, its expression keys, its tracks)
# Fields no part of a layout reads (layout.py, sizes.own_size, boxes.matrix, textsize.FIELDS): a fade or a colour
# change never moves a box, so its keys don't make a frame solved again. Add a field here only if none of those read it.
UNREAD = frozenset({"opacity", "fill", "color"})


def uses_layout(comp: dict) -> bool:
    return any(has_layout(i) for i in items_of(comp).values())


def bake(comp: dict, fps: float, baked: dict | None = None) -> dict[str, dict[str, list]]:
    """{item id: {field: keys}} for every field an auto layout sets; `baked` = the expressions' keys (exprbake)."""
    if not uses_layout(comp):
        return {}
    baked = baked or {}
    settings = (fps, {k: v for k, v in comp.items() if k != "layers"})
    out: dict[str, dict[str, list]] = {}
    for layer in comp.get("layers", []):
        if not laid_out(layer):
            continue
        mine = {i: baked[i] for i in items_of(layer) if i in baked}
        kept = _KEPT.get(layer["id"])
        if not (kept and kept[0] is layer and kept[1] == settings and kept[2] == mine):
            kept = (layer, settings, mine, _solve({**comp, "layers": [layer]}, fps, baked))
            _KEPT.pop(layer["id"], None)
            _KEPT[layer["id"]] = kept
            while len(_KEPT) > KEEP:
                _KEPT.pop(next(iter(_KEPT)))
        out.update({i: dict(fields) for i, fields in kept[3].items()})
    return out


def _solve(comp: dict, fps: float, baked: dict) -> dict[str, dict[str, list]]:
    """bake's work for the layers of `comp`, every frame. A frame whose layout inputs are the same as the frame before
    (`_same_as_before`: no key of any layer in it moves between the two, no layer comes or goes) has the same layout:
    its values are the frame before's, not solved again (a 30 s film of mostly still rows: 900 solves -> a few dozen)."""

    def props(item, t):
        p = resolve(item, t)
        for prop, keys in baked.get(item["id"], {}).items():
            p[prop] = track_value(keys, t)
        return p

    duration = comp.get("duration", F.defaults("comp")["duration"])
    n = max(1, math.ceil(duration * fps - 1e-9))
    times = [round(min(i / fps, duration), 6) for i in range(n + 1)]
    same = _same_as_before(comp, baked, times)
    solved = [i for i in range(len(times)) if not same[i]]
    results: dict[int, dict] = {}
    for at in range(0, len(solved), FRAMES):
        with textsize.kept_keys():                                     # a frame's text dicts are never changed
            _solve_some(comp, times, solved[at:at + FRAMES], props, results)
    tracks: dict[str, dict[str, list]] = {}
    last: dict = {}
    for i, t in enumerate(times):
        last = results.get(i, last)
        for item_id, values in last.items():
            for prop, v in values.items():
                tracks.setdefault(item_id, {}).setdefault(prop, []).append({"t": t, "v": v, "ease": "linear"})
    items = items_of(comp)
    for item_id, fields in tracks.items():
        for prop, keys in fields.items():
            if len(keys) < n + 1:                # set at some frames only (a text narrowed for a while): its own
                have = {k["t"] for k in keys}    # value at the others, so no key reaches across them
                keys += [{"t": t, "v": props(items[item_id], t)[prop], "ease": "linear"} for t in times if t not in have]
                keys.sort(key=lambda k: k["t"])
            if len(keys) == n + 1 and all(k["v"] == keys[0]["v"] for k in keys):
                fields[prop] = keys[:1]
    return tracks


def _solve_some(comp: dict, times: list[float], frames: list[int], props, results: dict) -> None:
    """Solve these frames (numbers into `times`) together, into `results` {frame: Plan.result}."""
    plans = [Plan(comp, times[i], props) for i in frames]
    answers = lay_out([tree for plan in plans for tree in plan.trees])
    pairs, i = [], 0
    for plan in plans:
        pairs.append((plan, answers[i:i + len(plan.trees)]))
        i += len(plan.trees)
    prime_texts(pairs)                                              # the frames' texts in two engine trips
    for frame, (plan, got) in zip(frames, pairs):
        results[frame] = plan.result(got, primed=True)


def _same_as_before(comp: dict, baked: dict, times: list[float]) -> list[bool]:
    """For each frame: True when every layout input is the same as at the frame before, so its layout is too. Inputs
    are the items' fields at t (evaluate.resolve, plus the expressions' keys) and whether each layer shows (start <= t <
    end). A key track holds still before its first key, after its last (when it stays) and between two keys of the
    same plain value with no bend in space; anything else counts as moving (careful: a frame said to move is only
    solved again). Keys timed on a marker or start / end keys: every frame is solved."""
    same = [False] + [True] * (len(times) - 1)

    def moving(lo: float, hi: float) -> None:      # frames after `lo` up to `hi` may differ from the frame before
        for i in range(max(1, bisect_right(times, lo)), min(len(times), bisect_left(times, hi) + 1)):
            same[i] = False

    def track(keys: list[dict]) -> bool:
        if not keys or any(not isinstance(k["t"], (int, float)) for k in keys):
            return False
        if after_of(keys) != "stay":
            moving(keys[0]["t"], math.inf)
            return True
        for k0, k1 in zip(keys, keys[1:]):
            plain = "v" in k0 and "v" in k1 and not any(f in k for k in (k0, k1) for f in ("out", "in"))
            if not (plain and k0["v"] == k1["v"] and type(k0["v"]) is type(k1["v"])) or k1["t"] < k0["t"]:
                moving(k0["t"], k1["t"])
        return True

    for item in items_of(comp).values():
        own = baked.get(item["id"], {})
        for prop in (animated(item) | set(own)) - UNREAD:
            if prop in ("start", "end", "hidden") or not track(own.get(prop) or keys_of(item, prop)):
                return [False] * len(times)
        if item is not comp and item.get("type") in F.FIELDS:
            p = resolve(item, times[0])
            for edge in (p.get("start"), p.get("end")):          # shows from start, until end: the frame that crosses it
                if isinstance(edge, (int, float)) and 1 <= (i := bisect_left(times, edge)) < len(times):
                    same[i] = False
    return same
