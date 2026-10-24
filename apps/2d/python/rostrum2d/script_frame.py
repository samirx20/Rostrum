"""The script's framing calls (`f = frame()`; `f.fit(["hills", "tree"], at=4)`, `f.fit(rect=(x, y, w, h), at=…)`,
`f.cut(at=6, to="rect", rect=(3200, 0, 1920, 1080))`, `f.cut(at="#logo lands")`, `f.home(at=…)`). They run the same
operations as the screen and agents (ops_frame_fit.py) on the tree the script is building, with the same argument
checks and refusals; the keys they write are ordinary keys with the usual ids, so a re-run finds them again."""
from __future__ import annotations

from rostrum_core.conditions import describe, holds
from rostrum_core.run import Context, _check_args


def _ids(items) -> list[str]:
    return [getattr(i, "id", i) for i in ([items] if isinstance(items, str) or hasattr(items, "id") else items)]


def args_of(items=None, *, at=None, to=None, rect=None, pad=None, cut=None, keep_rotation=None) -> dict:
    """An operation's args from a script call: `to` is "items" with layers, "rect" with a rectangle, unless given."""
    out = {"to": to or ("items" if items is not None else "rect" if rect is not None else None),
           "ids": None if items is None else _ids(items), "rect": None if rect is None else [float(v) for v in rect],
           "at": at, "pad": pad, "cut": cut, "keepRotation": keep_rotation}
    return {k: v for k, v in out.items() if v is not None}


def run(build, frame: dict, op_name: str, args: dict) -> None:
    """Run `op_name` on the script's frame now, in place on the tree being built (one script = one change)."""
    from .kind import KIND
    op = KIND.registry.get(op_name)
    where = f"{frame['id']}.{op_name.split('.')[1]}()"
    args = _check_args(op, args, where)
    if not holds(op.valid_when, frame, KIND.facts(frame)):
        raise ValueError(f"{where}: the frame can't take {op_name} now: it needs {describe(op.valid_when)}")
    op.fn(Context(KIND, build.root, where), [frame["id"]], args)
