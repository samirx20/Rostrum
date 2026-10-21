"""Expressions and bindings on one field: a number (or colour) field is driven by a small safe expression
(expr.py) instead of its own value or keys. The expression is an item the owner holds, its id from owner and field
(`title.x.expr`), so a script re-run finds it and every change is one operation in the one history.
The bake that turns it into per-frame keys for the scene is exprbake.py. (`bind.set` is the rig's own, RIG.md;
ours is `link.set`.)

    expr.set  {prop, source}                         title.x = `sin(time * 3) * 40 + logo.x`
    link.set  {prop, of, field, scale, offset}       value = other·scale + offset, the same as an expression
    expr.clear {prop}                                the field goes back to its own value / keys
"""
from __future__ import annotations

import re

from rostrum_core import Param
from rostrum_core.errors import codes

from . import exprbake as X, fields as F
from .expr import ExprError, parse
from .kind import REGISTRY as R

OWNERS = F.ANIMATED_OWNERS
PROP = Param.text("prop", label="Field", required=True, help="The field the expression drives (x, opacity, fill …)")
PLAIN = re.compile(r"^[A-Za-z_]\w*(\.[A-Za-z_]\w*)*$")


def expr_id(owner: str, prop: str) -> str:
    return f"{owner}.{prop}.expr"


def link_source(of: str, field: str, scale: float = 1.0, offset: float = 0.0) -> str:
    """`logo.x * 2 + 10`: the expression a binding is."""
    ref = f"{of}.{field}" if PLAIN.match(of) else f'ref("{of}.{field}")'
    s = ref if scale == 1 else f"{ref} * {scale:g}"
    return s if offset == 0 else f"{s} {'+' if offset > 0 else '-'} {abs(offset):g}"


def put(ctx, owner_id: str, prop: str, source: str):
    """Set (or replace) the field's expression, refusing anything that couldn't be evaluated or would loop."""
    owner = ctx.item(owner_id)
    allowed = F.animatable(owner["type"])
    where = f"{owner_id}.{prop}"
    if prop not in allowed:
        ctx.fail(codes.BAD_ARGUMENT, f'prop "{prop}"', f"is not a field of a {owner['type']} that can take an "
                 "expression", allowed)
    try:
        parse(source)
    except ExprError as e:
        ctx.fail(codes.BAD_ARGUMENT, "expression", e.at(where, source))
    existing = next((e for e in owner.get("exprs", []) if e["prop"] == prop), None)
    if existing:
        ctx.set(existing["id"], "source", source)
    else:
        ctx.insert(owner_id, "exprs", {"id": expr_id(owner_id, prop), "type": "expr", "prop": prop, "source": source})
    items = X.items_of(X.comp_of(ctx.doc, owner_id))
    bad = X.problems(items, X.exprs_of(items), (owner_id, prop))
    if bad:
        ctx.fail(codes.BAD_ARGUMENT, "expression", bad[0])


@R.operation("expr.set", "Drive a field with a small expression: time, frame, fps, duration, sin cos abs sqrt floor "
             "ceil round min max clamp lerp noise, + - * / % ^, comparisons, `a if c else b`, and other items' fields "
             "(`logo.x`, `ref(\"logo.x\", time - 0.2)`). It overrides the field's own value and keys; "
             "`expr.clear` takes it away.", target=OWNERS, label="Drive by expression", importance="secondary",
             params=[PROP, Param.text("source", label="Expression", required=True,
                                      help='For example: sin(time * 3) * 40 + 960')])
def expr_set(ctx, targets, args):
    for t in targets:
        put(ctx, t, args["prop"], args["source"])


@R.operation("link.set", "Bind a field to another item's field: value = other · scale + offset (an expression). "
             "It overrides the field's own value and keys; `expr.clear` takes it away.",
             target=OWNERS, label="Bind to a field", importance="secondary",
             params=[PROP, Param.text("of", label="Item", required=True, help="The item to read (its id)"),
                     Param.text("field", label="Its field", required=True, help="x, opacity, fill …"),
                     Param.number("scale", label="Scale", min=-1e6, max=1e6, step=0.01, default=1.0),
                     Param.number("offset", label="Offset", min=-1e9, max=1e9, step=0.1, default=0.0)])
def link_set(ctx, targets, args):
    scale, offset = args.get("scale", 1.0), args.get("offset", 0.0)
    for t in targets:
        p = F.param(ctx.item(t)["type"], args["prop"])
        if p is not None and p.type == "color" and (scale != 1 or offset != 0):
            ctx.fail(codes.BAD_ARGUMENT, "scale / offset", f"don't apply to a colour field ({t}.{args['prop']})",
                     hint="Bind a colour as it is, or write an expression with lerp(#rrggbb, #rrggbb, …).")
        put(ctx, t, args["prop"], link_source(args["of"], args["field"], scale, offset))


@R.operation("expr.clear", "Take an expression or binding off a field: it goes back to its own value and keys.",
             target=OWNERS, label="Clear expression", importance="secondary", params=[PROP])
def expr_clear(ctx, targets, args):
    for t in targets:
        e = next((e for e in ctx.item(t).get("exprs", []) if e["prop"] == args["prop"]), None)
        if e is None:
            ctx.fail(codes.BAD_ARGUMENT, f'prop "{args["prop"]}"', f"has no expression on {t}")
        ctx.remove(e["id"])
