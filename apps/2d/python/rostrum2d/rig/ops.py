"""Rig operations: bones, IK chains and binds (RIG.md § Operations). A rig is added with `layer.add`
(type "rig"); each field change is the generated `bone.set` / `ik.set` / `bind.set`. References between the
parts are checked by `model.problems_of` after every call, so these only fill in the starting values."""
from __future__ import annotations

from dataclasses import replace

from rostrum_core import Param
from rostrum_core.tree import index

from .. import fields as F
from ..kind import REGISTRY as R
from ..ops_items import ID, NAME, new_item
from .model import binds_to_drop, start_bone, start_ik


def _p(type_, name, **over) -> Param:
    return replace(F.param(type_, name), **over)


def _ref(name, kind, label, **kw) -> Param:
    return Param.id(name, kind=kind, label=label, **kw)


def _rig_of(ctx, id_) -> dict:
    return ctx.item(index(ctx.doc, ctx.kind.lists)[id_].parent)


def _each(ctx, targets, args, type_, make):
    """Add one `type_` item to each target rig (ids are left to count when there are several targets)."""
    for t in targets:
        item = new_item(ctx, type_, args if len(targets) == 1 else {**args, "id": None})
        item.update(make(ctx.item(t), {k: v for k, v in args.items() if k not in ("id", "name")}))
        ctx.insert(t, {"bone": "bones", "ik": "iks", "bind": "binds"}[type_], item)


@R.operation("bone.add", "Add a bone to a rig. With a parent and no x / y it starts at the parent's rest tip.",
             target="rig", label="Add bone",
             params=[ID, NAME, *(F.param("bone", n) for n in ("parent", "x", "y", "angle", "length"))])
def bone_add(ctx, targets, args):
    _each(ctx, targets, args, "bone", lambda rig, a: start_bone(rig["bones"], a))


@R.operation("bone.remove", "Delete bones. Their child bones move up to the parent; binds and IK chains that use "
             "them go too.", target="bone", label="Delete bone", importance="secondary")
def bone_remove(ctx, targets, args):
    for t in targets:
        rig, bone = _rig_of(ctx, t), ctx.item(t)
        upper = {b["id"]: b["parent"] for b in rig["bones"]}
        gone = [k["id"] for k in rig["iks"] if t in (k["bone"], upper.get(k["bone"]))]
        gone += [b["id"] for b in rig["binds"] if t in (b["bone"], b["bone2"])]
        for b in rig["bones"]:
            if b["parent"] == t:
                ctx.set(b["id"], "parent", bone["parent"])
        for id_ in gone:
            ctx.remove(id_)
        ctx.remove(t)


@R.operation("ik.add", "Add an IK chain to a rig: the lower bone's tip reaches for a target; its parent is the "
             "upper bone. The target starts at the tip's rest place.", target="rig", label="Add IK chain",
             params=[ID, NAME, _ref("bone", "bone", "Lower bone", required=True, help="The shin or forearm"),
                     _p("ik", "mode", valid_when=None), _p("ik", "bend", valid_when=None),
                     _p("ik", "targetX", valid_when=None), _p("ik", "targetY", valid_when=None)])
def ik_add(ctx, targets, args):
    _each(ctx, targets, args, "ik", lambda rig, a: start_ik(rig["bones"], a))


@R.operation("ik.remove", "Delete IK chains (the bones stay, posed by their own turns).", target="ik",
             label="Delete IK chain", importance="secondary")
def ik_remove(ctx, targets, args):
    for t in targets:
        ctx.remove(t)


@R.operation("bind.add", "Bind a layer of the rig to a bone: it follows the bone (rigid), or with bone2 (a child "
             "of bone) it bends across the joint.", target="rig", label="Bind layer",
             params=[ID, NAME, _ref("layer", "layer", "Layer", required=True, help="A layer inside the rig"),
                     _ref("bone", "bone", "Bone", required=True),
                     _p("bind", "bone2"), _p("bind", "grid"), _p("bind", "soft")])
def bind_add(ctx, targets, args):
    _each(ctx, targets, args, "bind", lambda rig, a: a)


@R.operation("bind.remove", "Delete binds (the layers stay where they are at rest).", target="bind",
             label="Unbind", importance="secondary")
def bind_remove(ctx, targets, args):
    for t in targets:
        ctx.remove(t)


def drop_binds(ctx, layer_ids):
    """A layer that is deleted or leaves its rig takes its bind with it."""
    for id_ in binds_to_drop(ctx.doc, set(layer_ids)):
        ctx.remove(id_)
