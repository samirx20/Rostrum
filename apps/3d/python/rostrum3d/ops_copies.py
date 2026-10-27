"""Copies (brief 24): make an item many times over a line, a grid, a circle or a surface, change the copies near an
item, and keep a copy where someone put it. The screen and agents use these same operations. `copies.set` (every field of
the item) is the generated field operation (kind.py); the layout itself is computed by the core, one place.

A copy someone put by hand (`copies.hold`, the gizmo's drop) is held: its row is [copy index, x, y, z, rx, ry, rz, scale] in the
copies item's own space. A layout change (count, spacing, a re-run of the script's `copies.make`) never moves a held copy;
only `copies.release` lets it go back to its place in the layout.
"""
from __future__ import annotations

import dataclasses

from rostrum_core import Param
from rostrum_core.errors import codes
from rostrum_core.tree import index, subtree_ids

from . import copies_fields as CF, fields as F
from .kind import REGISTRY as R
from .ops_items import ID, NAME, new_item

HOLD_KEYS = ("x", "y", "z", "rx", "ry", "rz", "s")
FIELDS = [p for p in F.unconditional("copies") if p.group in ("Copies", "Vary") and p.name != CF.HELD]
SOURCES = tuple(CF.SOURCES)


def _apply(ctx, copies_id: str, given: dict) -> None:
    """Write copies fields onto an existing copies item, checked like any field change; its held copies stay."""
    for k, v in given.items():
        p = F.param("copies", k)
        ctx.set(copies_id, k, p.check(v, f"{ctx.where} › {copies_id}.{k}"))
    bad = F.not_valid("copies", ctx.item(copies_id), given)
    if bad:
        from rostrum_core.conditions import describe
        ctx.fail(codes.BAD_ARGUMENT, f"{copies_id}.{bad[0]}", f"only applies when {describe(F.param('copies', bad[0]).valid_when)}",
                 hint=f"Set that too to use {bad[0]} (the layout decides which fields apply).")


def _given(args: dict) -> dict:
    return {p.name: args[p.name] for p in FIELDS if p.name in args}


def _make(ctx, targets, args, layout: str | None = None):
    given = _given(args)
    if layout:
        given["layout"] = layout
    again = ctx.idx.get(args.get("id") or "")
    if again is not None and again.item.get("type") == "copies":        # a re-run: same item, never a second one
        _apply(ctx, again.item["id"], given)
        return again.item
    locs = index(ctx.doc, ctx.kind.lists)
    for t in targets:
        if locs[t].item["type"] not in SOURCES:
            ctx.fail(codes.BAD_ARGUMENT, f'target "{t}"', f"is a {locs[t].item['type']}; copies repeat a mesh, combine, import, group or clay")
    if len(set(targets)) != len(targets):
        ctx.fail(codes.BAD_ARGUMENT, "targets", "name the same item twice")
    base = locs[targets[0]]
    for t in targets:
        if (locs[t].parent, locs[t].key) != (base.parent, base.key):
            ctx.fail(codes.BAD_ARGUMENT, f'target "{t}"', f'is not in the same list as "{targets[0]}"',
                     hint="Move them into the same group first (item.arrange), so their positions mean the same.")
        if any(o != t and (o in subtree_ids(locs[t].item, ctx.kind.lists)) for o in targets):
            ctx.fail(codes.BAD_ARGUMENT, f'target "{t}"', "holds another target")
    if (surface := given.get("surface")) is not None:
        if surface not in locs or locs[surface].item["type"] not in F.ITEMS:
            ctx.fail(codes.BAD_ARGUMENT, f'surface "{surface}"', "is not an item in the scene")
        if any(surface in subtree_ids(locs[t].item, ctx.kind.lists) for t in targets):
            ctx.fail(codes.BAD_ARGUMENT, f'surface "{surface}"', "is one of the items being copied (or inside one)")
    given.setdefault("layout", "line")
    if given["layout"] == "surface" and not given.get("surface"):
        ctx.fail(codes.BAD_ARGUMENT, '"surface"', "is needed for a surface layout: the id of the item the copies stand on")
    here = [[locs[t].item.get(k, 0.0) for k in "xyz"] for t in targets]
    mid = {k: round(sum(h[i] for h in here) / len(here), 6) for i, k in enumerate("xyz")}
    name = args.get("name") or f'{base.item.get("name") or targets[0]} copies'
    item = new_item(ctx, "copies", {"id": args.get("id"), "name": name}, {**given, **mid})
    ctx.insert(base.parent, base.key, item, base.index)
    for t in targets:                                  # the sources stand at the middle; turn and size stay
        ctx.move(t, item["id"], "children")
        for k in "xyz":
            ctx.set(t, k, 0.0)
    return item


@R.operation("copies.make", "Repeat items many times: a new copies item takes the targets' place and holds them as its source "
             "(they move to the copies item's origin, keeping their turn and size; several sources: each copy picks one, by "
             "the seed). layout line (step spacingX/Y/Z), grid (columns, spacingX/Z; count is the total), circle (radius, "
             "faceOut) or surface (surface = item id; amountBy count|density, density, minSpacing, alongSurface, onlySeen). "
             "Vary with seed, varyMove, varyTurn, varyScale. With the id of a copies item that exists it works like copies.set: a "
             "re-run never makes a second one and never moves a held copy. The core draws the copies as instances "
             "(10000 at most); the reply of look / inspect says how many the camera saw.",
             target=SOURCES, label="Make copies", params=[ID, NAME, *FIELDS])
def copies_make(ctx, targets, args):
    return _make(ctx, targets, args)


@R.operation("copies.scatter", "Scatter items over another item's surface: copies.make with layout surface. `surface` is the "
             "item the copies stand on (a plane, a mesh, a clay, an import). By default only the copies the shot camera sees "
             "are drawn (onlySeen); amountBy density gives a count per square metre; minSpacing keeps them apart; "
             "alongSurface stands each one along the surface's direction there.",
             target=SOURCES, label="Scatter on a surface", params=[ID, NAME, *(dataclasses.replace(p, required=p.name == "surface") for p in FIELDS if p.name != "layout")])
def copies_scatter(ctx, targets, args):
    return _make(ctx, targets, args, "surface")


EFFECTOR = [ID, NAME,
            *(p for p in F.unconditional("effector") if p.name != "name")]


@R.operation("effector.add", "Change the copies near an item: an effector inside the copies item whose centre follows "
             "`near` (move or key that item and the change moves with it; none: the copies item's own origin). kind scale "
             "(amount = extra size at the centre, 0.5 = half again bigger, −1 = gone), turn (degrees round `axis`), push "
             "(metres away from the centre) or colour (`colour`, amount = 0–1 mix); radius says how far it reaches, falloff "
             "smooth or linear. Key amount, radius or colour on the effector for change over time. An existing effector id "
             "is changed instead.", target="copies", label="Change near", params=EFFECTOR)
def effector_add(ctx, targets, args):
    names = [p.name for p in F.FIELDS["effector"]]
    given = {k: v for k, v in args.items() if k in names}
    if (near := given.get("near")) and (near not in ctx.idx or ctx.idx[near].item.get("type") not in F.ITEMS):
        ctx.fail(codes.BAD_ARGUMENT, f'near "{near}"', "is not an item in the scene")
    out = []
    for t in targets:
        again = ctx.idx.get(args.get("id") or "")
        if again is not None and again.item.get("type") == "effector" and len(targets) == 1:
            for k, v in given.items():
                ctx.set(again.item["id"], k, F.param("effector", k).check(v, f"{ctx.where} › {again.item['id']}.{k}"))
            out.append(again.item)
            continue
        kind = given.get("kind", "scale")
        item = new_item(ctx, "effector", {"id": args.get("id") if len(targets) == 1 else None,
                                          "name": args.get("name") or f"{kind.capitalize()} near {near or t}"},
                        {"amount": CF.STARTING_AMOUNT[kind], **given})
        ctx.insert(t, "children", item)
        out.append(item)
    return out[0] if len(out) == 1 else out


@R.operation("copies.hold", "Put one copy somewhere and keep it there: a held copy never moves when the layout changes (count, "
             "spacing, re-running a script). `copy` is its number (0 = the first); x y z are in the copies item's own space "
             "(metres), rx ry rz its turn, s its size (1 = the source's own). Fields left out keep what a held copy already "
             "had (a copy not held yet: no turn, size 1). copies.release lets it go back.",
             target="copies", label="Keep this copy here",
             params=[Param.number("copy", label="Copy", min=0, max=CF.MAX_COUNT - 1, integer=True, required=True,
                                  help="The copy's number, counted from 0"),
                     *(Param.number(k, label=k, min=-1e5, max=1e5, unit="m" if k in "xyz" else "°" if k.startswith("r") else "×")
                       for k in HOLD_KEYS)])
def copies_hold(ctx, targets, args):
    n = int(args["copy"])
    for t in targets:
        item = ctx.item(t)
        if item["layout"] != "surface" or item["amountBy"] != "density":
            if n >= item["count"]:
                ctx.fail(codes.BAD_ARGUMENT, f"copy {n}", f"is past the last copy of {t} ({item['count']} copies, numbered 0–{item['count'] - 1})")
        held = CF.held_map(item)
        row = held.get(n, {"x": None, "y": None, "z": None, "rx": 0.0, "ry": 0.0, "rz": 0.0, "s": 1.0})
        row = {**row, **{k: float(args[k]) for k in HOLD_KEYS if k in args}}
        if None in (row["x"], row["y"], row["z"]):
            ctx.fail(codes.BAD_ARGUMENT, "x y z", f"are needed to hold copy {n}: where it goes, in the copies item's own space")
        held[n] = row
        ctx.set(t, CF.HELD, CF.held_rows(held))


@R.operation("copies.release", "Let a held copy go back to its place in the layout (`copy`), or every held copy (no `copy`).",
             target="copies", label="Release copies",
             params=[Param.number("copy", label="Copy", min=0, max=CF.MAX_COUNT - 1, integer=True,
                                  help="Left out: every held copy")])
def copies_release(ctx, targets, args):
    for t in targets:
        held = CF.held_map(ctx.item(t))
        if "copy" in args:
            held.pop(int(args["copy"]), None)
        else:
            held = {}
        ctx.set(t, CF.HELD, CF.held_rows(held))
