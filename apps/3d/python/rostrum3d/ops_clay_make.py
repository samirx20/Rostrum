"""Making clay by drawing (CL3): join a drawn outline or a spun profile to a clay, and Turn into clay. Each is one
operation, so one undo step. What the step holds is clay_steps.py (the same for scripts); the geometry is
clay_shapes.py; a new clay from a drawing is clay.add's `draw` / `spin` (ops_clay.py).
"""
from __future__ import annotations

import dataclasses

from rostrum_core.errors import codes

from . import clay_shapes, clay_steps as CS
from .clay_fields import SOURCES
from .kind import REGISTRY as R
from .ops_clay import AXIS, BLEND, FACING, MODE, NAME, PTS, PUFF, SYM, add_step, clay_material, grain
from .ops_items import new_item

OUTLINE = dataclasses.replace(PTS("outline", "Outline", "[[x, y, z], …] the outline (4 points or more; closed last → "
                                  "first) in the clay's own space"), required=True)
PROFILE = dataclasses.replace(PTS("profile", "Profile", "[[x, y, z], …] half a profile (2 points or more) in the "
                                  "clay's own space, starting at the axis"), required=True)


@R.operation("clay.draw", "Join a drawn shape to a clay (or carve it out, mode=carve): `outline` points in the clay's "
             "own space are fitted to a plane (`facing` is its normal, pointing at the viewer, when given; else the "
             "outline's own plane) and puffed up both ways: as thick in the middle as the outline is wide there "
             "(`puff` 1; 0.5 flatter, 2 fatter; claystep.set puff changes it later). To join, start the outline on "
             "or touching the clay's surface, at the depth where it should sit. Blend: 0.3 × how fat it is (at most "
             "5 cm) when left out. A tiny outline (under 4 points, or thinner than 1.5 grains) joins a lump the "
             "brush's size instead. Mirrored by the clay's own Mirror unless `symmetry` says.", target="clay",
             label="Draw a shape", params=[OUTLINE, FACING, PUFF, MODE, BLEND, SYM, NAME])
def clay_draw(ctx, targets, args):
    for t in targets:
        clay = ctx.item(t)
        add_step(ctx, t, CS.draw_values(clay, args, args["outline"], grain(ctx, clay)))


@R.operation("clay.spin", "Join a spun shape to a clay (a vase, a bottle, a head's base): `profile` points (the clay's "
             "own space) are turned round `axis` (two points; left out: straight up, the clay's +Y, through the "
             "first profile point). Each point counts by its distance from the axis and its height along it; the "
             "profile's ends close to the axis. Blend: 0.3 × its widest (at most 5 cm) when left out; a profile "
             "thinner than 1.5 grains joins a lump instead.", target="clay", label="Spin a shape",
             params=[PROFILE, AXIS, MODE, BLEND, SYM, NAME])
def clay_spin(ctx, targets, args):
    if args.get("axis") and len(args["axis"]) != 2:
        ctx.fail(codes.BAD_ARGUMENT, '"axis"', f"has {len(args['axis'])} points", ["two points [[x, y, z], [x, y, z]]"])
    for t in targets:
        clay = ctx.item(t)
        add_step(ctx, t, CS.spin_values(clay, args, args["profile"], grain(ctx, clay)))


def _beside(ctx, item_id: str) -> tuple[dict, str, str]:
    """Where a clay made from an item goes: beside it (a part: beside its import), never inside a combine."""
    place = ctx.item(ctx.idx[item_id].parent) if ctx.item(item_id)["type"] == "part" else ctx.item(item_id)
    loc = ctx.idx[place["id"]]
    while loc.parent != "root" and ctx.item(loc.parent)["type"] == "combine":
        place, loc = ctx.item(loc.parent), ctx.idx[loc.parent]
    return place, loc.parent, loc.key


@R.operation("clay.from_item", "Turn into clay: for each exact part or import, a clay copy to sculpt beside it "
             '(named "<its name> clay", detail following the cameras, Mirror off, its material kept, else the '
             "project's \"Clay\" one), its first "
             "step the item's shape (shape=item, source=the item). The original is hidden (visible=false), not "
             "deleted: showing it again or deleting the clay brings it back. One undo step for all.",
             target=SOURCES, label="Turn into clay")
def clay_from_item(ctx, targets, args):
    made = []
    for t in targets:
        src = ctx.item(t)
        place, parent, key = _beside(ctx, t)
        fields = {k: place.get(k, 0.0) for k in ("x", "y", "z", "rx", "ry", "rz")}
        fields.update(symmetry="off", detailMode="auto",
                      material=src.get("material") or place.get("material") or clay_material(ctx))
        clay = new_item(ctx, "clay", {"name": f"{src.get('name') or t} clay"}, fields)
        ctx.insert(parent, key, clay, ctx.idx[place["id"]].index + 1)
        add_step(ctx, clay["id"], {"step": "piece", "shape": "item", "source": t, "mode": "add", "blend": 0.0,
                                   "sourceKey": clay_shapes.source_key(src), "symmetry": "off"})
        ctx.set(t, "visible", False)
        made.append(ctx.item(clay["id"]))
    return made
