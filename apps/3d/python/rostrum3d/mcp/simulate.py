"""simulate and inspect_simulation: a shot's rigid-body simulation for agents (brief 25, SPEC §10).

run_simulation is always a job (inspect_job shows "frame n of m"): it computes the shot's simulation when the scene as it is has no
stored result, records it as the shot's stored result (sim.run, one step), and says how it ended: how many things fell, how
many came to rest, how many end inside the shot camera's picture. Then look_sheet / look_frame show it.
"""
from __future__ import annotations

from rostrum_core.cache import CACHE
from rostrum_core.errors import RostrumError, codes
from rostrum_core.mcp import Reply, Tools

from rostrum3d import aim
from rostrum3d.compile import _shot
from rostrum3d.resolve import Frames
from rostrum3d.sim import ops as sim_ops
from rostrum3d.sim import cloth_check, fall_view
from rostrum3d.sim.cut_note import cut_lines
from rostrum3d.sim.compute import SimError, compute
from rostrum3d.sim.inputs import KIND, bodies, value
from rostrum3d.sim.result import read
from rostrum3d.sim.state import state
from .shot import ITEM_SHOT, doc_and_shot

tools = Tools()


def in_frame(data: dict, info: dict, res, folder=None) -> tuple[int, int]:
    """(things inside the shot camera's picture at the last frame, things that fell): positions through the camera's lens."""
    f = info["end"]
    fr = Frames(data, range(f, f + 1), info["fps"], folder)
    cam = fr.items[info["camera"]]
    back = aim.invert(fr.world(cam["id"], f))
    vals = fr.values(cam["id"], f)
    half_w = vals["sensorWidth"] / 2 / vals["focalLength"]
    half_h = half_w * info["height"] / info["width"]
    seen = total = 0
    falls = {b["id"]: b for b in bodies(data) if value(b, "simulate") == "falls"}
    for b in res.bodies:
        if b["item"] not in falls:
            continue
        p, _ = res.sample(f, b["row"])
        if falls[b["item"]]["type"] == "copies":                 # a copy's row is in its copies item's own space
            p = aim.point(fr.world(b["item"], f), p)
        x, y, z = aim.point(back, p)
        total += 1
        seen += z < 0 and abs(x / -z) <= half_w and abs(y / -z) <= half_h
    return seen, total


@tools.tool("run_simulation", {"properties": {**ITEM_SHOT}})
def run_simulation(ctx, args):
    """Simulate a shot: things set to Falls drop, bump and come to rest on things set to Stays still (and the ground, unless
    the shot's simGround is off), over the whole shot; shapes set to Cloth drape and fold over them (Weight, Stiffness, Air: how
    much the air slows its fall, a Pinned edge held in place). Set them up first with the sim.body and sim.set operations. Computed once
    and stored; nothing is computed again until something it depends on changes (a mass, a place, a key). Renders compute it
    first on their own when it is out of date. Always a job: returns a job id at once; inspect_job shows 'frame n of m'. When
    done: the stored result's key, frames, how many fell, came to rest and end inside the camera's picture, each cloth's point
    count and what it ends on (endsOn; a warning when it starts over nothing it can land on, or slides off what it started
    over), and the engine's time per frame (frameMs). A thing set to Falls with fallStart holds still until then, then
    falls. Whether each fall is seen: onScreen {item: [frames of its drop (until it first lands) the shot camera shows,
    frames of its drop]}, and a warning when the drop happens above or outside the picture, is on screen under 4 frames, or the thing starts
    already at rest, with the fix (sim.start_in_view raises it into the picture; fallStart gives the shot a moment first). A failure names the
    thing, the frame and what to do (e.g. it starts inside another one: move it up or set Starts: asleep). To nudge the result
    by hand, the sim.to_keys operation turns it into plain keys (a copies item: keys on every copy, copies.key nudges one);
    cloth stays a simulation (its folds are not keys). A cloth that tears apart, flies apart or falls past everything fails
    the same way, naming it and the frame."""
    doc, info = doc_and_shot(ctx, args)
    shot_id, folder = info["id"], ctx.app.folder

    def job_fn(job):
        n = info["end"] - info["start"] + 1
        job.progress(0, n, f"frame 0 of {n}")
        try:
            key = compute(doc.data, shot_id, folder, sim_ops._ENGINE["factory"],
                          progress=lambda i, of, frame: job.progress(i, of or n, f"frame {i} of {of or n}"),
                          cancel=job.cancel_requested.is_set)
        except SimError as e:
            raise RostrumError(codes.JOB_FAILED, ctx.tool, f'shot "{shot_id}"', f"could not be simulated: {e}") from e
        if _shot(doc.data, shot_id).get("simKey") != key:
            ctx.apply(doc, [{"op": "sim.run", "target": [shot_id]}], label="Simulate")
        where = CACHE.get(KIND, key)
        res = read(where)
        seen, total = in_frame(doc.data, info, res, folder)
        rest = res.reply.get("atRest", 0)
        drapes, warns, facts = cloth_check.report(doc.data, info, where)
        made = {c["item"]: c for c in res.reply.get("cloth", [])}
        seen_falls = fall_view.views(doc.data, info, folder)
        warns += [r["line"] for r in seen_falls if r["fix"]] + cut_lines(seen_falls, info["start"], info["end"], info["start"], info["fps"])
        cloth = [{**f, "triangles": made.get(f["item"], {}).get("triangles")} for f in facts]
        falls = (f'{total} falling, {rest} at rest at the end, {seen} of {total} inside the camera\'s picture at the last '
                 'frame') if total or not cloth else "nothing falls"
        return Reply(f'Simulated {shot_id}: {"; ".join([falls, *drapes])}; frames {res.start}–{res.end}, '
                     f'{res.reply.get("frameMs")} ms a frame, stored.',
                     {"key": key, "frames": [res.start, res.end], "bodies": total, "atRest": rest, "inFrame": seen,
                      "cloth": cloth,
                      "onScreen": {r["item"]: [r["onScreen"], r["onScreen"] + r["offScreen"]] for r in seen_falls}, "ms": res.reply.get("ms"), "frameMs": res.reply.get("frameMs")}, warnings=warns)

    return ctx.job(f"simulate {shot_id}", job_fn, key=f"simulate|{doc.item_id}|{shot_id}|{doc.seq}")


@tools.tool("inspect_simulation", {"properties": {**ITEM_SHOT}})
def inspect_simulation(ctx, args):
    """How a shot's simulation stands: none (nothing falls or is cloth), not computed, stored (up to date) or out of date
    (something it depends on changed, e.g. a cloth's Stiffness; renders compute it again first), how many things move (each
    cloth counts one), and any item set to simulate that can't
    because it sits inside a group or copies."""
    doc, info = doc_and_shot(ctx, args)
    st = state(doc.data, info["id"], ctx.app.folder)
    return Reply(st["line"] + (f'; inside a group, so not simulated: {", ".join(st["inside"])}' if st["inside"] else ""), st)
