"""Facts about a composition's motion that an agent should know before it looks: overlapping entrances, stretches
where nothing moves, layers not showing at the end, keys that do nothing. Each finding is a plain sentence plus
the numbers; there is no score and no opinion about taste.
"""
from __future__ import annotations

from rostrum_core.keys import key_value, keys_of

from .geometry import comp_size, flatten, problems_showing
from .motion_screen import Screen
from .motion_facts import HOLD_MIN_S, all_layers, r, windows


def finding(kind: str, text: str, **data) -> dict:
    return {"kind": kind, "text": text, **data}


def entrance_overlaps(facts: list[dict]) -> list[dict]:
    """Runs of layers whose first moving stretches overlap (each one starts before the run so far has finished): one
    finding a run, never one a pair (a staggered grid of 200 dots was 11,000+ pair findings, critic r10). Two layers
    keep the pair's sentence; a longer run says its span, how many start together and how far apart the starts are."""
    ent = sorted(((f["entrance"], f["id"]) for f in facts if f["entrance"] and f["type"] != "camera"), key=lambda e: e[0])
    runs, cur, end = [], [], 0.0
    for (a0, a1), a in ent:
        if cur and a0 < end:
            cur.append(((a0, a1), a))
            end = max(end, a1)
        else:
            runs.append(cur)
            cur, end = [((a0, a1), a)], a1
    runs.append(cur)
    return [_run(run) for run in runs if len(run) > 1]


def _run(run: list) -> dict:
    ids, starts = [a for _, a in run], [s for (s, _), _ in run]
    t0, t1 = starts[0], max(e for (_, e), _ in run)
    if len(run) == 2:
        ((a0, a1), a), ((b0, b1), b) = run
        both = round(min(a1, b1) - b0, 3)
        how = "start together" if abs(a0 - b0) < 1e-6 else f"start {r(b0 - a0, 2)} s apart"
        return finding("entrances_overlap", f"{a} ({a0}–{a1} s) and {b} ({b0}–{b1} s) move at the same time for {both} s; they {how}.",
                       layers=ids, overlap_s=both, apart_s=r(b0 - a0))
    gaps = [r(y - x, 3) for x, y in zip(starts, starts[1:])]
    apart = [g for g in gaps if g >= 0.001]
    together = len(gaps) - len(apart)
    if not apart:
        how = "they all start together"
    elif min(apart) == max(apart) and not together:
        how = f"each starts {apart[0]} s after the one before"
    else:
        how = f"{together + 1 if together else 0} start together, the others start {min(apart)}–{max(apart)} s apart"
    shown = ", ".join(ids[:3]) + f" … {ids[-1]}" if len(ids) > 4 else ", ".join(ids)
    return finding("entrances_overlap", f"{len(ids)} layers ({shown}) move in one overlapping run from {r(t0, 2)} to {r(t1, 2)} s; {how}.",
                   layers=ids, start=r(t0), end=r(t1), apart_s=r(min(apart) if apart else 0.0))


def quiet_spans(facts: list[dict], duration: float) -> list[dict]:
    """Stretches of the whole composition where nothing at all moves (the end counts)."""
    wins = windows([{"start": a, "end": b} for f in facts for a, b in f["moving"]])
    edges = [0.0, *[x for w in wins for x in w], duration]
    return [finding("nothing_moves", f"Nothing moves from {r(a, 2)} to {r(b, 2)} s ({r(b - a, 2)} s).", start=r(a), end=r(b))
            for a, b in zip(edges[::2], edges[1::2]) if b - a >= HOLD_MIN_S]


def _drawn_ids(comp: dict, t: float, w: float, h: float, only: set | None = None) -> tuple[list[str], dict[str, list[str]]]:
    """(layers nothing but the frame could hide at t, why each other one is not drawn). Whether the frame shows them is the engine's."""
    drawn, why = [], {}
    for node in flatten(comp, t, only=only):
        if node["type"] == "group" or (only is not None and node["id"] not in only):
            continue
        reasons = problems_showing(node, w, h, frame=False)
        if reasons:
            why[node["id"]] = reasons
        else:
            drawn.append(node["id"])
    return drawn, why


def seen_words(layer: str, t: float, reasons: list[str]) -> str:
    """What is true of a layer that is not drawn at t. Fully see-through (a fade out or a fade to dark) is a state, not a fault."""
    if reasons == ["opacity 0"]:
        return f"{layer} is fully see-through (opacity 0) at {r(t, 2)} s: nothing is drawn for it then (as expected after a fade out)."
    return f'{layer} is not on screen at {r(t, 2)} s: {", ".join(reasons)}.'


def not_showing(comp: dict, t: float, screen: Screen) -> list[dict]:
    """Layers that should be there at `t` (in their times) but are not seen: see-through, or outside the picture. A layer whose
    own end came before is not listed: it left on purpose."""
    w, h = comp_size(comp)
    drawn, why = _drawn_ids(comp, t, w, h)
    out = [finding("not_showing", seen_words(i, t, x), layer=i, at=r(t), reasons=x)
           for i, x in why.items() if "outside its start/end times" not in x]
    seen = screen.seen(t, drawn)
    out += [finding("not_showing", f"{i} is not on screen at {r(t, 2)} s: outside the frame.", layer=i, at=r(t), reasons=["outside the frame"])
            for i in drawn if i not in seen]
    return out


SAMPLES = 48            # moments looked at in all (each is a full frame laid out by the engine: ~0.2 s on a busy scene)
FIRST = 24              # of them with every layer; the layers still unseen are then followed on the rest


def _spread(n: int, k: int) -> list[int]:
    return sorted({min(n - 1, round(i * n / k)) for i in range(k)} | {n - 1})


def never_shown(comp: dict, fps: float, duration: float, screen: Screen) -> list[dict]:
    """Layers the engine does not draw into the picture at any sampled frame (evenly spread, at most SAMPLES; the ones not yet seen after the
    first frames are followed on the rest)."""
    w, h = comp_size(comp)
    n = max(1, round(duration * fps))
    at = lambda f: min(f / fps, duration - 1e-6)   # noqa: E731
    groups = {layer["id"]: within for layer, within in all_layers(comp) if layer["type"] not in ("group", "camera")}
    unseen, drawn_ever, done = set(groups), set(), set()

    def look(frames: list[int], only: set | None):
        for f in frames:
            if not unseen:
                return
            drawn, _ = _drawn_ids(comp, at(f), w, h, only)
            drawn_ever.update(drawn)
            unseen.difference_update(screen.seen(at(f), [i for i in drawn if i in unseen]))
            done.add(f)

    look(_spread(n, min(n, FIRST)), None)
    if unseen:
        more = [f for f in _spread(n, min(n, SAMPLES)) if f not in done]
        look(more, {*unseen, *(g for i in unseen for g in groups[i])})
    return [finding("never_shown", f"{i} is never on screen between 0 and {r(duration, 2)} s.", layer=i,
                    why="it is hidden, see-through or out of its times the whole time" if i not in drawn_ever else "it is always outside the frame")
            for i in sorted(unseen)]


def dead_keys(comp: dict, duration: float) -> list[dict]:
    out = []
    for layer, _ in all_layers(comp):
        for owner in (layer, *layer.get("effects", []), *layer.get("masks", [])):
            label = layer["id"] if owner is layer else f'{layer["id"]}.{owner["id"]}'
            for prop in sorted({k["prop"] for k in owner.get("keys", [])}):
                keys = keys_of(owner, prop)
                vals = [key_value(k) for k in keys]
                if len(keys) == 1:
                    out.append(finding("key_does_nothing", f"{label}.{prop} has one key (at {keys[0]['t']} s): a single key never moves; the value is held at {vals[0]} the whole time.", owner=label, field=prop))
                elif len(set(vals)) == 1:
                    out.append(finding("key_does_nothing", f"{label}.{prop} has {len(keys)} keys that all say {vals[0]}: it never changes.", owner=label, field=prop))
                for k in keys:
                    if k["t"] > duration:  # a key on the last frame, or at the end itself, is reached
                        out.append(finding("key_after_end", f"{label}.{prop} has a key at {k['t']} s, after the composition ends ({r(duration, 2)} s); it is never reached.", owner=label, field=prop, at=k["t"]))
                    elif owner is layer and k["t"] > layer.get("end", 36000.0):
                        out.append(finding("key_after_end", f"{label}.{prop} has a key at {k['t']} s, after the layer's own end ({layer['end']} s).", owner=label, field=prop, at=k["t"]))
    return out
