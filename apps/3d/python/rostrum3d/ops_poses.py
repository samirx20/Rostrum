"""Poses: the values of some items' Position, Turn and Scale saved under a name (doc-level `poses`, one `pose` each),
and put back as keys at a time. `pose.save` reads the items as they are at `at` (their keys' values there, else
their settings); `pose.apply` keys every field the pose holds at `at`, or, given `share`, a breakdown: each of those
fields keyed `share` of the way from its key before `at` to its key after. Each is one step: one undo takes it back.
Values are read as shown (the animation layers laid over the Base); `layer` puts the keys on an animation layer, each
the key that shows the pose's value there (layers.key_for). `put_shown` is that rule for the pose ops (ops_pose.py too).
"""
from __future__ import annotations

from rostrum_core import Param
from rostrum_core.errors import codes
from rostrum_core.keys import layers

from . import fields as F
from .kind import REGISTRY as R
from .ops_items import ID, NAME, new_item
from .ops_keys import put_key

HELD = ("x", "y", "z", "rx", "ry", "rz", "sx", "sy", "sz")     # what a pose holds of each item (when it applies)
AT = Param.number("at", label="At", min=0, max=36000, unit="s", required=True, help="The time, in seconds")
SHARE = Param.number("share", label="Share", min=0, max=1, step=0.05,
                     help="A breakdown: each field keyed this share of the way from its key before `at` (0) to its "
                          "key after (1); fields without a key on both sides are left as they are. Left out: the "
                          "pose's own values")
LAYER = Param.text("layer", label="Layer", importance="deep", help="An animation layer's id: the keys go on that layer, "
                   "each the key that makes the field show the pose (add: an offset); left out: the Base")


def put_shown(ctx, owner_id: str, field: str, t: float, v: float, layer: str = "", still: float = 0.0):
    """Key `v` as the value the field shows at t: on `layer` the key that shows it, on the Base the Base value that
    shows it under the layers (layers.base_for; no layers: `v` as given)."""
    owner, stack = ctx.item(owner_id), layers.stack_of(ctx.doc)
    if layer:
        v = layers.key_for(owner, field, t, stack, layer, v, layers.base_at(owner, field, t, still))
    elif stack:
        v = layers.base_for(owner, field, t, stack, v, still)
    put_key(ctx, owner_id, field, t, {"v": v, **({"layer": layer} if layer else {})})


def _still(item: dict, field: str) -> float:
    return float(F.param(item["type"], field).default)


def value_at(item: dict, field: str, t: float, stack=()) -> float:
    """A field's value at time t as shown: its keys' there, else its setting, with the animation layers `stack` laid
    over (before stepped timing, which only shows)."""
    return float(layers.shown_at(item, field, t, list(stack), _still(item, field)))


def _held(item: dict) -> list[str]:
    """The fields a pose takes from this item: Position, Turn (unless it aims) and Scale, those it has and that apply."""
    names = {p.name for p in F.FIELDS[item["type"]]} & set(F.animatable(item["type"]))
    return [f for f in HELD if f in names and not F.not_valid(item["type"], item, [f])]


@R.operation("pose.save", "Save the selected items' Position, Turn and Scale as they are at `at` as a named pose "
             "(an aimed item's turn is left out: its aim decides it). Apply it later with pose.apply.",
             target=F.KEYED, label="Save pose", params=[ID, NAME, AT])
def pose_save(ctx, targets, args):
    fields, values = [], []
    for t in targets:
        item = ctx.item(t)
        for f in _held(item):
            fields.append(f"{t}.{f}")
            values.append(round(value_at(item, f, args["at"], layers.stack_of(ctx.doc)), 6))
    if not fields:
        ctx.fail(codes.BAD_ARGUMENT, "targets", "hold nothing a pose can keep (Position, Turn or Scale)")
    args = {**args, "name": args.get("name") or f"Pose {len(ctx.doc.get('poses', [])) + 1}"}
    ctx.insert("root", "poses", new_item(ctx, "pose", args, {"fields": fields, "values": values}))


def _neighbours(item: dict, field: str, t: float, stack: list, layer: str):
    """The values shown at the keys before and after t (of `layer`, else the Base), or None."""
    keys = layers.layer_keys(item, field, layer) if layer else layers.keys_of(item, field)
    before = [k["t"] for k in keys if k["t"] < t - 1e-9]
    after = [k["t"] for k in keys if k["t"] > t + 1e-9]
    if not (before and after):
        return None
    return tuple(value_at(item, field, T, stack) for T in (before[-1], after[0]))


@R.operation("pose.apply", "Key every field a pose holds at `at` (an item no longer in the scene, or a field that no "
             "longer applies, is skipped and named in the reply). With `share`: a breakdown between the "
             "neighbouring keys instead. `layer`: on that animation layer.", target="pose", label="Apply pose",
             params=[AT, SHARE, LAYER])
def pose_apply(ctx, targets, args):
    skipped, done, layer, stack = [], 0, args.get("layer") or "", layers.stack_of(ctx.doc)
    for pid in targets:
        pose = ctx.item(pid)
        for name, value in zip(pose["fields"], pose["values"]):
            id_, _, field = name.rpartition(".")
            item = _find(ctx, id_)
            if item is None or field not in _held(item):
                skipped.append(name)
                continue
            if "share" in args:
                pair = _neighbours(item, field, args["at"], stack, layer)
                if pair is None:
                    skipped.append(name)
                    continue
                value = pair[0] + args["share"] * (pair[1] - pair[0])
            put_shown(ctx, id_, field, args["at"], value, layer, _still(item, field))
            done += 1
    if not done:
        ctx.fail(codes.BAD_ARGUMENT, "pose", f"has nothing to key here (skipped: {', '.join(skipped) or 'none'})",
                 hint="A breakdown needs keys before and after `at`; a pose needs its items in the scene.")
    return {"keyed": done, "skipped": skipped}


def _find(ctx, id_: str):
    """The scene item, or None when it is gone (skipped and named, never a crash)."""
    loc = ctx.idx.get(id_)
    return loc.item if loc and loc.item.get("type") in F.KEYED else None


@R.operation("pose.rename", "Rename a pose.", target="pose", label="Rename pose",
             params=[Param.text("name", label="Name", required=True)])
def pose_rename(ctx, targets, args):
    for t in targets:
        ctx.set(t, "name", args["name"])


@R.operation("pose.remove", "Delete poses (their keys already written stay).", target="pose", label="Delete pose",
             importance="secondary")
def pose_remove(ctx, targets, args):
    for t in targets:
        ctx.remove(t)
