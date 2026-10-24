"""Poses: the values of some items' Position, Turn and Scale saved under a name (doc-level `poses`, one `pose` each),
and put back as keys at a time. `pose.save` reads the items as they are at `at` (their keys' values there, else
their settings); `pose.apply` keys every field the pose holds at `at`, or, given `share`, a breakdown: each of those
fields keyed `share` of the way from its key before `at` to its key after. Each is one step: one undo takes it back.
"""
from __future__ import annotations

from rostrum_core import Param
from rostrum_core.errors import codes
from rostrum_core.keys import keys_of, track_value

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


def value_at(item: dict, field: str, t: float) -> float:
    """A field's value at time t: its keys' there, else its setting (before stepped timing, which only shows)."""
    keys = keys_of(item, field)
    return float(track_value(keys, t)) if keys else float(item.get(field, F.param(item["type"], field).default))


def _held(item: dict) -> list[str]:
    """The fields a pose takes from this item: Position, Turn (unless it aims) and Scale, those it has and that apply."""
    names = {p.name for p in F.FIELDS[item["type"]]} & set(F.animatable(item["type"]))
    return [f for f in HELD if f in names and not F.not_valid(item["type"], item, [f])]


@R.operation("pose.save", "Save the selected items' Position, Turn and Scale as they are at `at` as a named pose "
             "(an aimed item's turn is left out: its aim decides it). Apply it later with pose.apply.",
             target=F.ITEMS, label="Save pose", params=[ID, NAME, AT])
def pose_save(ctx, targets, args):
    fields, values = [], []
    for t in targets:
        item = ctx.item(t)
        for f in _held(item):
            fields.append(f"{t}.{f}")
            values.append(round(value_at(item, f, args["at"]), 6))
    if not fields:
        ctx.fail(codes.BAD_ARGUMENT, "targets", "hold nothing a pose can keep (Position, Turn or Scale)")
    args = {**args, "name": args.get("name") or f"Pose {len(ctx.doc.get('poses', [])) + 1}"}
    ctx.insert("root", "poses", new_item(ctx, "pose", args, {"fields": fields, "values": values}))


def _neighbours(item: dict, field: str, t: float):
    keys = sorted(keys_of(item, field), key=lambda k: k["t"])
    before = [k for k in keys if k["t"] < t - 1e-9]
    after = [k for k in keys if k["t"] > t + 1e-9]
    return (before[-1]["v"], after[0]["v"]) if before and after else None


@R.operation("pose.apply", "Key every field a pose holds at `at` (an item no longer in the scene, or a field that no "
             "longer applies, is skipped and named in the reply). With `share`: a breakdown between the "
             "neighbouring keys instead.", target="pose", label="Apply pose", params=[AT, SHARE])
def pose_apply(ctx, targets, args):
    skipped, done = [], 0
    for pid in targets:
        pose = ctx.item(pid)
        for name, value in zip(pose["fields"], pose["values"]):
            id_, _, field = name.rpartition(".")
            item = _find(ctx, id_)
            if item is None or field not in _held(item):
                skipped.append(name)
                continue
            if "share" in args:
                pair = _neighbours(item, field, args["at"])
                if pair is None:
                    skipped.append(name)
                    continue
                value = pair[0] + args["share"] * (pair[1] - pair[0])
            put_key(ctx, id_, field, args["at"], {"v": value})
            done += 1
    if not done:
        ctx.fail(codes.BAD_ARGUMENT, "pose", f"has nothing to key here (skipped: {', '.join(skipped) or 'none'})",
                 hint="A breakdown needs keys before and after `at`; a pose needs its items in the scene.")
    return {"keyed": done, "skipped": skipped}


def _find(ctx, id_: str):
    """The scene item, or None when it is gone (skipped and named, never a crash)."""
    loc = ctx.idx.get(id_)
    return loc.item if loc and loc.item.get("type") in F.ITEMS else None


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
