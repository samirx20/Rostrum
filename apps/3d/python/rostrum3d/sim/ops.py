"""The simulation's operations (brief 25 + 26a): what the screen's Simulate menu, the Simulation group and agents call.

    sim.body    {kind: falls | still | cloth | off} on top-level items (cloth: shapes only)
    sim.set     the Simulation fields of items (Mass, Bounce …) and shots (Ground, Timing, Simplify), checked
    sim.run     compute the shot's simulation if needed and record it as the shot's stored result (simKey)
    sim.to_keys the stored result becomes ordinary keys on each falling item, which stops simulating (one undo step)

How it stands (stored, out of date …) is a read, not an operation: sim/state.py `state`, the inspect_simulation tool.
"""
from __future__ import annotations

from rostrum_core import Param
from rostrum_core.errors import codes
from rostrum_core.keys.evaluate import keys_of
from rostrum_core.keys.marked import same_time

from .. import copy_keys as CK, fields as F
from ..kind import REGISTRY as R
from . import fields as SF
from .compute import SimError, compute, needed
from .inputs import KIND, bodies, value
from .result import read, stylized, trs

_ENGINE = {"factory": None}           # what compute starts its engine with (None: rostrum3d.engine.Engine); tests swap it
TRS = ("x", "y", "z", "rx", "ry", "rz")
FROM = "Simulation"                   # a key's `from`: "Simulation · <shot> · <result>" (sim.to_keys)


def use_engine_factory(factory):
    """The engine maker sim.run and sim.to_keys compute with (a test's stand-in; None for the real one)."""
    _ENGINE["factory"] = factory


def _folder(ctx):
    return getattr(ctx.doc, "folder", None)


@R.operation("sim.body", "Make items part of the shot's simulation: kind falls (moved by gravity and bumps), still (others "
             "land on it and bounce off it; it never moves), cloth (a shape that drapes and folds over what is under it; a "
             "plane is made fine enough to fold) or off. Only items directly in the scene (not inside a group, copies or "
             "rig); a copies item makes every copy a falling thing; only a shape (mesh) can be cloth. Then sim.set for Mass, "
             "Bounce, Friction, Starts, Shape (cloth: clothWeight, stiffness, pinned, friction), and sim.run to compute.",
             target=SF.TYPES, label="Simulate",
             params=[Param.choice("kind", SF.KINDS, label="Simulate", required=True, labels=SF.WORDS)])
def sim_body(ctx, targets, args):
    for t in targets:
        loc = ctx.idx[t]
        if loc.parent != "root":
            ctx.fail(codes.BAD_ARGUMENT, f'target "{t}"', f'is inside "{loc.parent}"; only things directly in the scene can '
                     "fall, stay still or be cloth", hint="Move it out first (item.arrange), then try again.")
        if args["kind"] == "cloth" and ctx.item(t)["type"] not in SF.CLOTH_TYPES:
            ctx.fail(codes.BAD_ARGUMENT, f'target "{t}"', f'is a {ctx.item(t)["type"]}; only a shape can be cloth',
                     hint="Make a plane (or another shape) and set it to cloth.")
        ctx.set(t, "simulate", args["kind"])


_ITEM = [p for p in F.unconditional("mesh") if p.name in SF.NAMES and p.name != "simulate"]
_SHOT = [p for p in F.unconditional("shot") if p.name in SF.SHOT_NAMES and p.name != SF.KEY]


@R.operation("sim.set", "Change Simulation settings. On an item: massFromSize, mass (kg), bounce (0–1), friction (0–2), "
             "starts (moving | asleep: until something hits it), simShape (exact | box | sphere); on cloth: clothWeight "
             "(kg per m²: silk 0.05, cotton 0.2, denim 0.4), stiffness (0 silk … 1 thin card), pinned (none | top | bottom | "
             "left | right | front | back: that side, as seen in the scene at the first frame, held in place), friction. "
             "On a shot: simGround (a "
             "floor at height 0), simTiming (every | 2s | 3s: steps like hand animation), simSimplify (keep every nth "
             "frame, smooth between). Timing and Simplify never need a new simulation.", target=(*SF.TYPES, "shot"),
             label="Simulation settings", importance="secondary", params=[*_ITEM, *_SHOT])
def sim_set(ctx, targets, args):
    from rostrum_core.conditions import describe
    for t in targets:
        item = ctx.item(t)
        mine = SF.SHOT_NAMES if item["type"] == "shot" else SF.NAMES
        if wrong := [k for k in args if k not in mine]:
            ctx.fail(codes.BAD_ARGUMENT, f'"{wrong[0]}"', f"is not a Simulation setting of a {item['type']}",
                     sorted(mine - {SF.KEY, "simulate"}))
        for k, v in args.items():
            ctx.set(t, k, v)
        if item["type"] != "shot" and (bad := F.not_valid(item["type"], ctx.item(t), args)):
            ctx.fail(codes.BAD_ARGUMENT, f"{t}.{bad[0]}", f"only applies when {describe(F.param(item['type'], bad[0]).valid_when)}",
                     hint="Set Simulate first (sim.body), or Mass from size off to give a mass.")


def _compute(ctx, shot: str) -> str:
    try:
        return compute(ctx.doc, shot, _folder(ctx), _ENGINE["factory"])
    except SimError as e:
        ctx.fail(codes.JOB_FAILED, f'shot "{shot}"', f"could not be simulated: {e}")


@R.operation("sim.run", "Simulate a shot: computes it (a second or two for a dozen things; nothing when the result for the "
             "scene as it is is already stored) and records it as the shot's stored result. Renders and the viewport then "
             "read it; nothing recomputes on its own. A failure names the thing, the frame and what to do. After sim.to_keys, with nothing falling any more, it changes nothing.",
             target="shot", label="Simulate")
def sim_run(ctx, targets, args):
    for t in targets:
        if not needed(ctx.doc) and _turned(ctx, t):
            continue                                     # turned into keys already: a script's re-run changes nothing
        ctx.set(t, SF.KEY, _compute(ctx, t))


# --- 26a: turn into keys ----------------------------------------------------------------------------------------------

def _tag(shot: str, key: str) -> str:
    return f"{FROM} · {shot} · {key[:8]}"


def _ours(k: dict, shot: str) -> bool:
    return str(k.get("from") or "").startswith(f"{FROM} · {shot} · ")


def _turned(ctx, shot: str) -> bool:
    """Something carries keys this shot's simulation wrote (sim.to_keys ran): an item's, or a copies item's keyed copies."""
    return any(_ours(k, shot) for i in ctx.doc.get("items", []) for k in i.get("keys", [])) or any(
        _ours({"from": i.get(CK.FROM)}, shot) and i.get(CK.KEYS) for i in ctx.doc.get("items", []))


def _key_frames(res, s0: int, s1: int, step: int, simplify: int) -> tuple[list[int], str]:
    if step > 1:
        return list(range(s0, s1 + 1, step)), "hold"
    if simplify > 1:
        kept = [f for f in range(s0, s1 + 1) if (min(max(f, res.start), res.end) - res.start) % simplify == 0]
        return sorted({*kept, s1}), "linear"
    return list(range(s0, s1 + 1)), "linear"


@R.operation("sim.to_keys", "Turn a shot's simulation into ordinary keys: each falling item gets keys on x y z rx ry rz "
             "(every frame; with Timing On 2s / On 3s a held key every 2 or 3 frames; with Simplify every nth frame) and "
             "stops simulating, in one undo step; then nudge any key by hand. Running it again never changes a key it "
             "already wrote for that result (a nudge stays) and never touches keys a person made. Computes first when "
             "needed. A falling copies item gets keys on each copy instead (copies.key nudges one) and stops "
             "simulating. Cloth is left as it is (its folds are not keys: it stays a simulation); a shot whose only "
             "simulated thing is cloth fails with that reason.",
             target="shot", label="Turn into keys")
def sim_to_keys(ctx, targets, args):
    from ..compile import _shot, shot_info
    from ..ops_keys import put_key
    from rostrum_core.cache import CACHE
    for shot_id in targets:
        if not needed(ctx.doc):
            if _turned(ctx, shot_id):
                continue                                     # already turned into keys: a re-run changes nothing
            ctx.fail(codes.BAD_ARGUMENT, f'shot "{shot_id}"', "has nothing that falls", hint="Simulate › Falls first.")
        if not any(value(b, "simulate") == "falls" for b in bodies(ctx.doc)):
            if _turned(ctx, shot_id):
                continue                                     # the falling things are keys already; the cloth stays
            ctx.fail(codes.BAD_ARGUMENT, f'shot "{shot_id}"', "has only cloth simulated, and cloth never becomes keys (its "
                     "folds are not keys: it stays a simulation)", hint="Nothing to turn into keys; set something to "
                     "Simulate › Falls for that.")
        key = _compute(ctx, shot_id)
        res, shot, info = read(CACHE.get(KIND, key)), _shot(ctx.doc, shot_id), shot_info(ctx.doc, shot_id)
        step, simplify = SF.TIMINGS[shot.get("simTiming", "every")], int(shot.get("simSimplify", 1))
        s0, s1, fps, tag = info["start"], info["end"], info["fps"], _tag(shot_id, key)
        frames, ease = _key_frames(res, s0, s1, step, simplify)
        for item in [b for b in bodies(ctx.doc) if value(b, "simulate") == "falls"]:
            rows = res.rows_of(item["id"])
            if not rows:
                continue
            if item["type"] == "copies":
                _copies_to_keys(ctx, item["id"], res, (s0, s1, fps), frames, ease, (step, simplify), tag)
                continue
            per = trs(stylized(res, rows[0], range(s0, s1 + 1), s0, step, simplify))
            for prop in TRS:
                times = [round(f / fps, 4) for f in frames]
                for f, t in zip(frames, times):
                    owner = ctx.item(item["id"])
                    there = next((k for k in keys_of(owner, prop) if same_time(k["t"], t)), None)
                    if there is not None and (not _ours(there, shot_id) or there.get("from") == tag):
                        continue                             # a person's key, or this result's (maybe nudged): kept
                    put_key(ctx, item["id"], prop, t, {"v": per[prop][f - s0], "ease": ease, "from": tag})
                for k in list(keys_of(ctx.item(item["id"]), prop)):         # an older result's keys between the new ones
                    if _ours(k, shot_id) and k.get("from") != tag:
                        ctx.remove(k["id"])
            ctx.set(item["id"], "simulate", "off")


def _copies_to_keys(ctx, copies_id: str, res, shot: tuple, frames: list[int], ease: str, style: tuple, tag: str):
    """Every copy of a falling copies item gets keys on x y z rx ry rz (copy_keys.py), by the same rule as an item's: a
    key already there that a person made, or that this result wrote (maybe nudged since), is kept; an older result's go."""
    s0, s1, fps = shot
    owner = ctx.item(copies_id)
    keyed, mine = CK.keys_map(owner), owner.get(CK.FROM) == tag
    times = [round(f / fps, 4) for f in frames]
    new = set(times)
    for body in (b for b in res.bodies if b["item"] == copies_id):
        per = trs(stylized(res, body["row"], range(s0, s1 + 1), s0, *style))
        props = keyed.setdefault(int(body["copy"]), {})
        for prop in TRS:
            there = {k["t"]: k for k in props.get(prop, [])}
            if not mine:                                     # an older result's keys go; a person's stay
                there = {t: k for t, k in there.items() if not k["sim"] or t in new}
            for f, t in zip(frames, times):
                k = there.get(t)
                if k is not None and (not k["sim"] or mine):
                    continue                                 # a person's key, or this result's (maybe nudged): kept
                there[t] = {"t": t, "v": per[prop][f - s0], "ease": ease, "sim": True}
            props[prop] = sorted(there.values(), key=lambda k: k["t"])
    ctx.set(copies_id, CK.KEYS, CK.rows(keyed))
    ctx.set(copies_id, CK.FROM, tag)
    ctx.set(copies_id, "simulate", "off")
