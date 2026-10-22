"""The pose library of a rig (RIG.md › Poses): a pose is a named snapshot of the rig's pose fields (bones' turn,
scale and move, IK targets and amounts, which drawing each swap set shows), stored on the rig in `poses`. Saving reads
the values at a time; applying keys them at a time, blended with a second pose and with what is there already. Each
call is one operation, so one undo step, and only puts keys: nothing else on the rig changes.
"""
from __future__ import annotations

from rostrum_core import Param
from rostrum_core.errors import codes

from ..evaluate import value_at
from ..kind import REGISTRY as R
from ..ops_items import ID, NAME, new_item
from ..ops_keys import adds_nothing, put_key

POSED = {"bone": ("rotation", "scale", "moveX", "moveY"), "ik": ("targetX", "targetY", "mix")}
CHOICE = ("show",)                          # a swap set's drawing: picked, never blended (swap.py)
TIME = Param.number("t", label="At", default=0.0, min=0, max=36000, unit="s", help="The time to read or key the pose")
PARTS = Param.list("parts", "text", label="Only these", importance="secondary",
                   help="Bone, IK or swap-set ids; empty = the whole rig (save an arm or a face on its own)")


def _swaps(rig: dict):
    stack = list(rig.get("layers", []))
    while stack:
        item = stack.pop()
        if item.get("type") == "group" and item.get("swap"):
            yield item
        stack += item.get("layers", [])


def owners(rig: dict) -> dict[str, tuple[dict, tuple]]:
    """{id: (item, its pose fields)} of everything a pose of this rig holds."""
    out = {i["id"]: (i, POSED[i["type"]]) for key in ("bones", "iks") for i in rig.get(key, [])}
    out.update({s["id"]: (s, CHOICE) for s in _swaps(rig)})
    return out


def snapshot(rig: dict, t: float, parts=None) -> dict:
    """{id: {field: value}} of the rig's pose at t."""
    return {id_: {f: value_at(item, f, t) for f in fields} for id_, (item, fields) in owners(rig).items()
            if not parts or id_ in parts}


def blend(a: dict, b: dict | None, mix: float) -> dict:
    """Pose a, mix of the way to pose b (a choice jumps at the half)."""
    if not b:
        return a
    out = {}
    for id_ in a.keys() | b.keys():
        va, vb = a.get(id_, {}), b.get(id_, {})
        out[id_] = {f: (vb.get(f, va.get(f)) if mix >= 0.5 else va.get(f, vb.get(f))) if f in CHOICE
                    else va.get(f, vb.get(f)) + mix * (vb.get(f, va.get(f)) - va.get(f, vb.get(f)))
                    for f in va.keys() | vb.keys()}
    return out


def _pose(ctx, rig: dict, id_: str) -> dict:
    found = next((p for p in rig.get("poses", []) if id_ in (p["id"], p.get("name"))), None)
    if found is None:
        ctx.fail(codes.BAD_ARGUMENT, f'pose "{id_}"', f"is not a pose of {rig['id']}",
                 [p["id"] for p in rig.get("poses", [])], hint="Save one first: pose.save.")
    return found["values"]


@R.operation("pose.save", "Save the rig's pose at a time as a named pose in its library (bones, IK targets, which "
             "drawing each swap set shows).", target="rig", label="Save pose", params=[ID, NAME, TIME, PARTS])
def pose_save(ctx, targets, args):
    for t in targets:
        rig = ctx.item(t)
        item = new_item(ctx, "pose", args if len(targets) == 1 else {**args, "id": None})
        item["values"] = snapshot(rig, args.get("t", 0.0), args.get("parts"))
        ctx.insert(t, "poses", item)


@R.operation("pose.apply", "Key a saved pose at a time; with a second pose, a blend of the two; `amount` below 1 "
             "goes only part of the way from the pose already there.", target="rig", label="Apply pose",
             params=[Param.id("pose", kind="pose", label="Pose", required=True), TIME,
                     Param.id("with", kind="pose", label="Blend with", importance="secondary"),
                     Param.number("mix", label="Blend", default=0.5, min=0, max=1, step=0.01, importance="secondary",
                                  valid_when={"not": {"is": ["with", None]}}, help="0 = the first pose, 1 = the second"),
                     Param.number("amount", label="Amount", default=1.0, min=0, max=1, step=0.01, importance="secondary",
                                  help="1 = all the way to the pose; less = part of the way from what is there"),
                     Param.choice("ease", ["smooth", "linear", "hold", "easeIn", "easeOut"], label="Ease",
                                  default="smooth", importance="secondary")])
def pose_apply(ctx, targets, args):
    at, amount = args.get("t", 0.0), args.get("amount", 1.0)
    for t in targets:
        rig = ctx.item(t)
        goal = blend(_pose(ctx, rig, args["pose"]), _pose(ctx, rig, args["with"]) if args.get("with") else None,
                     args.get("mix", 0.5))
        now, known = snapshot(rig, at), owners(rig)
        for id_, values in goal.items():
            if id_ not in known:
                continue                          # a bone deleted since the pose was saved: skipped
            for f, v in values.items():
                if f in CHOICE:
                    v, ease = (round(v) if amount >= 0.5 else now[id_][f]), "hold"
                else:
                    v, ease = now[id_][f] + amount * (v - now[id_][f]), args.get("ease", "smooth")
                if not adds_nothing(ctx.item(id_), f, v):     # the one K rule: never a flat field
                    put_key(ctx, id_, f, at, {"v": v, "ease": ease})


@R.operation("pose.remove", "Delete saved poses (keys already made from them stay).", target="pose",
             label="Delete pose", importance="secondary")
def pose_remove(ctx, targets, args):
    for t in targets:
        ctx.remove(t)
