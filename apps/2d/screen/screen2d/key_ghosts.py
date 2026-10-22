"""What a field does past its keys, as faint marks on its timeline row (UX_SPEC 3.18). No Qt.

- **Faint copies** (`ghosts`): the times of the keys that Repeat or Back and forth write out after the last key, read
  from `rostrum_core.keys.after.extend`, the one function playback and the export read too (one per frame, at most
  `MOST` per row). Carry on and Stay write no copies.
- **A spring's tail** (`tails`): a spring that is still moving when its next key comes (the key's stretch is shorter
  than the spring needs to settle): from that key to where the spring would have settled. The value jumps to the next
  key there; the tail says how much later the key would have to be for the spring to settle on its own. Read from
  `easing.spring` with the key's own `physics_of`, the evaluator's.
"""
from __future__ import annotations

from rostrum_core.keys import after
from rostrum_core.keys.easing import spring
from rostrum_core.keys.spring import physics_of

MOST = 200                  # faint copies per row at most (a fast repeat over a long scene: the first ones say it)
SETTLED = 0.005             # a spring is settled once it stays this close to its end (0.5 % of the move)
STEP = 0.01                 # of the stretch: how finely the settle point is found
LONGEST = 20.0              # stretches: a spring that needs longer is shown to there


def ghosts(keys: list[dict], until: float, fps: float) -> list[float]:
    """Times (seconds, as the keys are) of the faint copies past the last key, up to `until`."""
    if len(keys) < 2 or after.after_of(keys) not in ("repeat", "pingpong"):
        return []
    try:
        written = after.extend(keys, until)
    except ValueError:
        return []                           # too many to write out: playback reports it loudly
    last, frames, out = keys[-1]["t"], {round(k["t"] * fps) for k in keys}, []
    for k in written:
        f = round(k["t"] * fps)
        if k["t"] > last and f not in frames and k["t"] <= until:
            frames.add(f)
            out.append(k["t"])
            if len(out) >= MOST:
                break
    return out


def settle(key: dict) -> float:
    """How many of its stretches a spring key needs to settle (1 or less: it settles before the next key)."""
    stiffness, damping = physics_of(key)
    x, last_moving = 0.0, 0.0
    while x < LONGEST:
        x += STEP
        if abs(1 - spring(x, stiffness, damping)) > SETTLED:
            last_moving = x
        elif x - last_moving > 1.0:         # still for a whole stretch: it has settled
            break
    return last_moving


def tails(keys: list[dict]) -> list[dict]:
    """{t0, t1}: from a spring's next key to where the spring would have settled, for each spring cut short."""
    out = []
    for a, b in zip(keys, keys[1:]):
        if a.get("ease") == "spring" and b["t"] > a["t"]:
            need = settle(a)
            if need > 1.0:
                out.append({"t0": b["t"], "t1": a["t"] + need * (b["t"] - a["t"])})
    return out


def marks(fields: list[tuple[list[dict], float]], fps: float) -> dict:
    """{"ghosts": [t …], "tails": [{t0, t1} …]} for a row showing these fields' keys ([(keys, until)])."""
    seen, ghost, tail = set(), [], []
    for keys, until in fields:
        for t in ghosts(keys, until, fps):
            if round(t * fps) not in seen:
                seen.add(round(t * fps))
                ghost.append(t)
        tail += tails(keys)
    return {"ghosts": sorted(ghost)[:MOST], "tails": tail}
