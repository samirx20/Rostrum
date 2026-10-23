"""After the last key (UX_SPEC 3.18): what a field does past its last key, written on that key as `after`:
`stay` (it holds, the default), `repeat` (the keys play again from the first), `pingpong` ("Back and forth": forwards,
then backwards, and again) or `carry` (a number keeps going at the speed it arrived with; other values stay).

`extend` writes it out as ordinary keys up to a time: the ONE place it is worked out. Python's evaluation
(`track_value`) and the scene each app sends its engine both read the extended list, so the engine needs no notion
of it and the picture, the export and the settings panel agree (preview = export).
"""
from __future__ import annotations

from .easing import BEZIERS, ease
from .spatial import between

AFTER = ["stay", "repeat", "pingpong", "carry"]
WORDS = {"stay": "Stay", "repeat": "Repeat", "pingpong": "Back and forth", "carry": "Carry on"}
JUMP = 1e-4                 # seconds: a repeat starts over this long after the last key (a jump, under any frame)
MOST = 20000                # keys written out at most: more is refused loudly, never cut short


def after_of(keys: list[dict]) -> str:
    return keys[-1].get("after", "stay") if keys else "stay"


def _mirror(key: dict) -> dict:
    """The ease that runs the stretch ending at `key`'s neighbour backwards: a cubic is turned end for end; linear and
    the overshooting ones (spring, bounce: no cubic can say them backwards) keep their own shape."""
    name = key.get("ease", "smooth")
    if name in BEZIERS or name == "custom":
        x1, y1, x2, y2 = BEZIERS.get(name) or (key.get("x1", 0.25), key.get("y1", 0.1), key.get("x2", 0.25), key.get("y2", 1.0))
        return {"ease": "custom", "x1": round(1 - x2, 6), "y1": round(1 - y2, 6), "x2": round(1 - x1, 6), "y2": round(1 - y1, 6)}
    return {k: key[k] for k in ("ease", "stiffness", "damping", "bounce", "speed") if k in key}


_SHAPE = ("ease", "x1", "y1", "x2", "y2", "stiffness", "damping", "bounce", "speed")


def _at(key: dict, t: float, shape: dict | None = None) -> dict:
    out = {k: v for k, v in key.items() if k not in _SHAPE and k != "after"}
    out["t"] = round(t, 9)
    out.update(shape if shape is not None else {k: key[k] for k in _SHAPE if k in key})
    return out


def _flip(key: dict) -> dict:
    """A key played backwards: its spatial handles change ends (the way in becomes the way out)."""
    out = {k: v for k, v in key.items() if k not in ("out", "in")}
    return out | ({"out": key["in"]} if "in" in key else {}) | ({"in": key["out"]} if "out" in key else {})


def _turn(key: dict, nxt: dict) -> dict:
    """`key` where a cycle turns: it arrives as itself and leaves with the way out of `nxt`, the next cycle's copy."""
    out = {k: v for k, v in key.items() if k != "out"}
    return out | ({"out": nxt["out"]} if "out" in nxt else {})


def _backwards(keys: list[dict], start: float) -> list[dict]:
    """The keys played backwards from `start` (the first is the last key, which is where the cycle turns)."""
    last, out = keys[-1]["t"], []
    keys = [_flip(k) for k in keys]
    for i in range(len(keys) - 1, -1, -1):
        k = keys[i]
        shape = _mirror(keys[i - 1]) if i else {"ease": "linear"}
        if i and keys[i - 1].get("ease") == "hold":        # a jump played backwards jumps at the start of its stretch
            out.append(_at(k, start + last - k["t"], {"ease": "hold"}))
            k, shape = keys[i - 1], {"ease": "hold"}
            out.append(_at(k, start + last - keys[i]["t"] + JUMP, shape))
            continue
        out.append(_at(k, start + last - k["t"], shape))
    return out


def _carry(keys: list[dict], until: float) -> list[dict]:
    a, b = keys[-2], keys[-1]
    if "v" not in b or "v" not in a or b["t"] <= a["t"]:
        return keys
    d = 1e-3                    # the speed it arrives with: the last stretch's own slope at its end
    speed = (b["v"] - between(a, b, ease(a, 1 - d))) / d / (b["t"] - a["t"])
    straight = {k: v for k, v in b.items() if k != "out"}               # carrying on is a straight line
    return [*keys[:-1], _at(straight, b["t"], {"ease": "linear"}),
            _at({k: v for k, v in straight.items() if k != "in"}, until, {"ease": "linear"}) | {"v": b["v"] + speed * (until - b["t"])}]


def extend(keys: list[dict], until: float) -> list[dict]:
    """Sorted keys (seconds) with the last key's `after` written out as plain keys up to `until` (the list itself when
    it stays, or `until` is not past the last key). Every key of the result has seconds; `after` is dropped."""
    how = after_of(keys)
    if how not in AFTER:
        raise ValueError(f'after="{how}" is not one of {", ".join(AFTER)}')
    if how == "stay" or len(keys) < 2 or until <= keys[-1]["t"]:
        return keys
    if how == "carry":
        return _carry(keys, until)
    first, span = keys[0]["t"], keys[-1]["t"] - keys[0]["t"]
    if span <= JUMP:
        return keys
    out, n = [_at(k, k["t"]) for k in keys], 1
    while out[-1]["t"] < until:
        start = first + n * span
        if how == "repeat":
            out[-1] = _at(out[-1], out[-1]["t"], {"ease": "hold"})
            out += [_at(keys[0], start + JUMP)] + [_at(k, start + k["t"] - first) for k in keys[1:]]
        elif n % 2:
            back = _backwards(keys, start)
            out[-1] = _turn(_at(out[-1], out[-1]["t"], {k: v for k, v in back[0].items() if k in _SHAPE}), back[0])
            out += back[1:]
        else:
            out[-1] = _turn(_at(out[-1], out[-1]["t"], {k: keys[0][k] for k in _SHAPE if k in keys[0]}), keys[0])
            out += [_at(k, start + k["t"] - first) for k in keys[1:]]
        n += 1
        if len(out) > MOST:
            raise ValueError(f"after the last key: more than {MOST} keys to write out up to {until} s; the keys span "
                             f"{span:.4f} s, too short a cycle for so long")
    return out
