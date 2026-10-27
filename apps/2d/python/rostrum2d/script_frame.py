"""The script's framing calls (`f = frame()`; `f.fit(["hills", "tree"], at=4)`, `f.fit(rect=(x, y, w, h), at=…, ease="easeInOut")` (the move into it eased),
`f.cut(at=6, to="rect", rect=(3200, 0, 1920, 1080))`, `f.cut(at="#logo lands")`, `f.home(at=…)`) and a layer's
`pin(title)` / `set_depth(hills, 3)` (ops_depth.py, keeping where it shows). They run the same
operations as the screen and agents (ops_frame_fit.py) on the tree the script is building, with the same argument
checks and refusals; the keys they write are ordinary keys with the usual ids, so a re-run finds them again."""
from __future__ import annotations

from rostrum_core.conditions import holds
from rostrum_core.run import Context, _check_args, refusal


def _ids(items) -> list[str]:
    return [getattr(i, "id", i) for i in ([items] if isinstance(items, str) or hasattr(items, "id") else items)]


def args_of(items=None, *, at=None, to=None, rect=None, pad=None, cut=None, keep_rotation=None, ease=None) -> dict:
    """An operation's args from a script call: `to` is "items" with layers, "rect" with a rectangle, unless given."""
    out = {"to": to or ("items" if items is not None else "rect" if rect is not None else None),
           "ids": None if items is None else _ids(items), "rect": None if rect is None else [float(v) for v in rect],
           "at": at, "pad": pad, "cut": cut, "keepRotation": keep_rotation, "ease": ease}
    return {k: v for k, v in out.items() if v is not None}


def run(build, node: dict, op_name: str, args: dict) -> None:
    """Run `op_name` on `node` (the script's frame, or a layer for pin / set_depth) now, in place on the tree being
    built (one script = one change)."""
    from .kind import KIND
    op = KIND.registry.get(op_name)
    where = f"{node['id']}.{op_name.split('.')[1]}()"
    args = _check_args(op, args, where)
    ctx = Context(KIND, build.root, where)
    if not holds(op.valid_when, node, ctx.facts(node)):
        raise ValueError(f"{where}: {node['id']} {refusal(op)}")
    op.fn(ctx, [node["id"]], args)


def pin(build, layer, on=True, at=0, keep="shown") -> None:
    """`pin(title)`: the layer pinned to the frame where it shows at `at` (layer.pin); `pin(title, False)` unpins."""
    run(build, _node(build, layer), "layer.pin", {"on": on, "at": at, "keep": keep})


def set_depth(build, layer, depth, at=0, keep="shown") -> None:
    """`set_depth(hills, 3)`: the layer's depth, keeping where it shows at `at` (layer.set_depth)."""
    run(build, _node(build, layer), "layer.set_depth", {"depth": depth, "at": at, "keep": keep})


def _node(build, layer) -> dict:
    from rostrum_core.tree import index
    from .kind import LISTS
    id_ = getattr(layer, "id", layer)
    idx = index(build.root, LISTS)
    if id_ not in idx:
        raise ValueError(f'pin / set_depth: no layer "{id_}" made yet in this script')
    return idx[id_].item
