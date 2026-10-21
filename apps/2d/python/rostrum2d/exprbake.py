"""Expressions on fields (expr.py is the one evaluator): the checks (field fits, references exist, no loops) and the
bake that `scene.describe` uses. A field with an expression is written into the scene as `anim` keys, one per
frame from 0 to the composition's length, ease `linear` (exact at every frame); the engine and every other reader
see plain keys, and the expression overrides the field's own keys and still value.

The document holds only data: an owner's `exprs` list, items `{"id": "title.x.expr", "type": "expr", "prop": "x",
"source": "logo.x * 2 + 10"}` (ops_expr.py).
"""
from __future__ import annotations

import functools
import math
import re

from . import fields as F
from .evaluate import value_at
from .expr import ExprError, parse, refs
from .expr_run import run

CHILDREN = ("layers", "effects", "masks", "bones", "iks", "binds")
HEX = re.compile(r"^#[0-9a-fA-F]{6}$")
parse_cached = functools.lru_cache(maxsize=512)(parse)


def items_of(node: dict) -> dict[str, dict]:
    """Every item of a composition by id (layers, effects, masks, bones, iks, binds, itself)."""
    out, stack = {}, [node]
    while stack:
        item = stack.pop()
        out[item["id"]] = item
        stack += [c for key in CHILDREN for c in item.get(key, [])]
    return out


def exprs_of(items: dict) -> dict[tuple[str, str], str]:
    return {(i["id"], e["prop"]): e["source"] for i in items.values() for e in i.get("exprs", [])}


def source_of(item: dict, prop: str) -> str:
    return next((e["source"] for e in item.get("exprs", []) if e["prop"] == prop), "")


def _own(items, exprs, key) -> list[str]:
    owner_id, prop = key
    where, src, owner = f"{owner_id}.{prop}", exprs[key], items[owner_id]
    p = F.param(owner["type"], prop)
    if p is None or prop not in F.animatable(owner["type"]):
        return [f'{where}: a {owner["type"]}\'s "{prop}" can\'t take an expression; fields that can: '
                f'{", ".join(F.animatable(owner["type"]))}']
    try:
        tree = parse_cached(src)
    except ExprError as e:
        return [e.at(where, src)]
    out = []        # marker("…") names are the project's (rostrum_core.markers): checked when baked, loudly
    for (item, field), col in sorted(refs(tree).items()):
        q = F.param(items[item]["type"], field) if item in items else None
        why = (f'no item "{item}" to read {item}.{field} from' if item not in items
               else f"{item}.{field} is not a number or colour field" if q is None or q.type not in ("number", "color")
               else f"{item}.{field} is a {q.type} field but {prop} is a {p.type} field"
               if (q.type == "color") != (p.type == "color") else "")
        if why:
            out.append(ExprError(why, col).at(where, src))
    return out


def _loops(exprs, starts) -> list[str]:
    deps, found, done = {}, {}, set()

    def of(key):
        if key not in deps:
            try:
                deps[key] = sorted(r for r in refs(parse_cached(exprs[key])) if r in exprs)
            except ExprError:
                deps[key] = []
        return deps[key]

    def visit(key, path):
        if key in path:
            loop = path[path.index(key):] + [key]
            found.setdefault(frozenset(loop), "loop: " + " <- ".join(f"{i}.{p}" for i, p in loop)
                             + "  (each reads the next; a field can't depend on itself)")
        elif key not in done:
            for d in of(key):
                visit(d, [*path, key])
            done.add(key)
    for s in starts:
        visit(s, [])
    return list(found.values())


def problems(items: dict, exprs: dict, only: tuple | None = None) -> list[str]:
    """Why these expressions can't be used (all of them, or `only` one and what it reads); [] when fine."""
    keys = [only] if only else sorted(exprs)
    out = [p for k in keys for p in _own(items, exprs, k)]
    return out + _loops(exprs, keys)


def problems_of_doc(data: dict) -> list[str]:
    out = []
    for comp in data.get("comps", []):
        items = items_of(comp)
        out += problems(items, exprs_of(items))
    return out


def comp_of(data: dict, item_id: str) -> dict:
    return next(c for c in data["comps"] if item_id in items_of(c))


class _Env:
    __slots__ = ("time", "frame", "fps", "duration", "markers", "get")

    def __init__(self, t, fps, duration, get, markers):
        self.time, self.frame, self.fps, self.duration, self.markers, self.get = t, round(t * fps), fps, duration, markers, get


def _final(owner: dict, prop: str, v):
    """The expression's result as a value of the field: held inside its range (as keys are), colours as #rrggbb."""
    p = F.param(owner["type"], prop)
    if p.type == "color":
        if not (isinstance(v, str) and HEX.match(v)):
            raise ExprError(f"gives a number, but {prop} is a colour field (use #rrggbb or lerp between colours)")
        return v.lower()
    if isinstance(v, str):
        raise ExprError(f"gives a colour, but {prop} is a number field")
    v = min(max(v, p.min if p.min is not None else -math.inf), p.max if p.max is not None else math.inf)
    return float(round(v)) if p.integer else v


def bake(comp: dict, fps: float, markers: dict | None = None) -> dict[str, dict[str, list]]:
    """{item id: {field: linear keys at every frame}} for every field of the composition with an expression.
    `markers`: the project's {name: seconds} (rostrum_core.markers.times); None = not in a project folder."""
    items = items_of(comp)
    exprs = exprs_of(items)
    if not exprs:
        return {}
    bad = problems(items, exprs)
    if bad:
        raise ValueError("expressions: " + "; ".join(bad))
    trees, memo = {k: parse_cached(s) for k, s in exprs.items()}, {}
    duration = comp.get("duration", F.defaults("comp")["duration"])

    def at(key, t):
        if (key, t) not in memo:
            try:
                memo[key, t] = _final(items[key[0]], key[1], run(trees[key], _Env(t, fps, duration, get, markers)))
            except ExprError as e:
                raise ValueError(e.at(f"{key[0]}.{key[1]}", exprs[key])) from None
        return memo[key, t]

    def get(item, field, t):
        return at((item, field), t) if (item, field) in trees else value_at(items[item], field, t)

    n = max(1, math.ceil(duration * fps - 1e-9))
    times = [min(i / fps, duration) for i in range(n + 1)]
    out: dict = {}
    for key in exprs:
        field = "c" if F.param(items[key[0]]["type"], key[1]).type == "color" else "v"
        out.setdefault(key[0], {})[key[1]] = [{"t": round(t, 6), field: at(key, t), "ease": "linear"} for t in times]
    return out
