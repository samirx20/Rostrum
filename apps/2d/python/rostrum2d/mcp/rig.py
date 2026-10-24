"""look_rig and inspect_rig_motion: the agent's eyes on a rig. Both ask the engine for the posed bones (screen px, through the frame; FRAME.md)."""
from __future__ import annotations

import tempfile
from pathlib import Path

from rostrum_core.errors import RostrumError, codes
from rostrum_core.mcp import Reply, Tools
from rostrum_core.mcp.files import look_path

from . import render, rig_view
from .geometry import comp_size
from .pick import ITEM_COMP, TIME, doc_and_comp, time_of

tools = Tools()
MAX_FRAMES = 600


def _engine_fail(where: str, e: Exception) -> RostrumError:
    return RostrumError(codes.RENDER_FAILED, where, "the rig pose", f"could not be read: {e}", hint="The engine's log path, if any, is in the message.")


def _need_rig(ctx, comp: dict) -> dict:
    rigs = rig_view.rig_layers(comp)
    if not rigs:
        raise RostrumError(codes.NOT_FOUND, ctx.tool, "rig", f'{comp["id"]} has no rig layer', hint="Add one with layer.add type rig, or a rig() block in a script.")
    return rigs


@tools.tool("look_rig", {"properties": {**ITEM_COMP, **TIME}})
def look_rig(ctx, args):
    """One frame (composition size) with every rig's skeleton drawn over it: each bone a yellow line from its pivot to its tip with a
    white dot at the pivot, each IK target a red cross (green with a square while pinned). Returns the PNG and the posed bones in
    composition px."""
    doc, comp = doc_and_comp(ctx, args)
    t, frame = time_of(ctx, comp, args)
    _need_rig(ctx, comp)
    scene, comp_w = render.scene_of(doc, comp["id"]), comp_size(comp)[0]
    dest = look_path(f'{doc.item_id or "doc"}_{comp["id"]}_rig_f{frame}')

    def job_fn(job):
        from rostrum2d.engine import Engine
        with tempfile.TemporaryDirectory(prefix="rostrum_rig_") as tmp, Engine() as eng:
            eng.load(scene)
            raw = Path(tmp) / "raw.png"
            try:
                rigs = rig_view.posed(eng.bones(t), comp, ctx.tool)
                eng.still(t, raw)
            except RostrumError:
                raise
            except Exception as e:
                raise _engine_fail(ctx.tool, e) from e
            w, h = rig_view.draw_skeleton(raw, rigs, comp, t, dest, comp_w)
        n = sum(len(r["bones"]) for r in rigs.values())
        return Reply(f'Frame {frame} ({t:.3f} s) of {comp["id"]} with {n} bones in {len(rigs)} rig{"s" * (len(rigs) != 1)} drawn, {w}×{h}.',
                     {"time": t, "frame": frame, "width": w, "height": h, "rigs": rigs}, [dest], [dest])

    return ctx.long(f'look_rig {comp["id"]} f{frame}', job_fn)


@tools.tool("inspect_rig_motion", {"properties": {**ITEM_COMP, "start": {"type": "number", "minimum": 0, "description": "Seconds. Default 0."},
                                                   "end": {"type": "number", "minimum": 0, "description": "Seconds. Default: the last frame."}}})
def inspect_rig_motion(ctx, args):
    """Per IK chain over a time range, sampled at every frame: the tip's path (comp px, the frame undone), the largest IK gap (how far the tip misses its
    target) and when, and for each pinned span how far the tip moved during it (over 0.5 px is a sliding foot). Facts only."""
    doc, comp = doc_and_comp(ctx, args)
    fps, duration = comp.get("fps", 30), comp.get("duration", 5.0)
    last = (round(duration * fps) - 1) / fps
    start, end = args.get("start", 0.0), args.get("end", last)
    if not 0 <= start < end <= last + 1e-9 or round((end - start) * fps) + 1 > MAX_FRAMES:
        raise RostrumError(codes.BAD_ARGUMENT, ctx.tool, f"range {start}–{end} s", f"must satisfy 0 <= start < end <= {last:.3f} and span at most {MAX_FRAMES} frames")
    rigs_doc = _need_rig(ctx, comp)
    scene = render.scene_of(doc, comp["id"])
    times = [round(start * fps + i) / fps for i in range(round((end - start) * fps) + 1)]

    def job_fn(job):
        from rostrum2d.engine import Engine
        samples = []
        with Engine() as eng:
            eng.load(scene)
            try:
                for i, t in enumerate(times):
                    samples.append({"t": t, "rigs": rig_view.posed(eng.bones(t), comp, ctx.tool)})
                    job.progress(i + 1, len(times))
            except RostrumError:
                raise
            except Exception as e:
                raise _engine_fail(ctx.tool, e) from e
        chains = [rig_view.chain_facts(samples, layer, iid, rid, ctx.tool) for rid, layer in rigs_doc.items() for iid in rig_view.iks_of(layer)]
        sliding = [f'{c["ik"]} {s["start"]:g}–{s["end"]:g} s ({s["tip_moved_px"]} px)' for c in chains for s in c["pinned_spans"] if s["sliding"]]
        text = (f'{len(chains)} IK chain{"s" * (len(chains) != 1)} over {times[0]:.3f}–{times[-1]:.3f} s ({len(times)} frames). '
                + (f'Pinned tips that moved over {rig_view.SLIDE_PX} px: {"; ".join(sliding)}.' if sliding else "No pinned tip slid."))
        return Reply(text, {"start": times[0], "end": times[-1], "fps": fps, "chains": chains})

    return ctx.long(f'inspect_rig_motion {comp["id"]}', job_fn)
