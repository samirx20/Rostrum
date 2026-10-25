"""look_frame (what: world) and look_frame (what: in_frame): the agent's eyes on the whole canvas. look_frame (what: world) draws the world the way the world view does
(the engine's world picture, so layers beside the frame show where they are) and marks the frame on it: its outline now, its
path, an outline at each key, the part outside veiled. look_frame (what: in_frame) says in numbers what is in, partly in or out of the
frame at a moment or over a span (camera spec § 6)."""
from __future__ import annotations

import math
import tempfile
from pathlib import Path

from rostrum_core.errors import RostrumError, codes
from rostrum_core.mcp import Reply, Tools
from rostrum_core.mcp.files import look_path

from rostrum2d.frame import view

from . import render, world_facts as wf
from .pick import ITEM_COMP, TIME, doc_and_comp, time_of
from .world_picture import AREAS, area_rect, draw_overlay, world_png

tools = Tools()


@tools.tool("look_world", {"properties": {**ITEM_COMP, **TIME, **AREAS,
        "width": {"type": "integer", "minimum": 200, "maximum": 2560, "default": 1280, "description": "Picture width in px. Default 1280."},
        "path": {"type": "boolean", "default": True, "description": "Draw the frame's whole path: a dot per frame, a faint outline at each key, a cut as a dashed line. Default true."}}})
def look_world(ctx, args):
    """The whole world at a time, as the world view shows it, with the frame on it: its outline now, its path (a dot per frame, a
    faint outline at each key, cuts dashed), the part outside the frame veiled, and a ruler of world px along the edges. `area`:
    "all" (every layer and the frame's whole path), "frame" (just the frame's own box), or {x, y, w, h} in world px. Use it to
    see layers that sit beside the frame, where the frame goes, and to pick an area to look_at or export. The reply gives the
    frame's corners in world px and the rectangle shown."""
    doc, comp = doc_and_comp(ctx, args)
    t, frame = time_of(ctx, comp, args)
    rect = area_rect(ctx.tool, comp, args.get("area", "all"), t)
    scene, width = render.scene_of(doc, comp["id"], (t, t)), args.get("width", 1280)
    dest = look_path(f'{doc.item_id or "doc"}_{comp["id"]}_world_f{frame}', project=doc.folder)
    path = args.get("path", True)

    def job_fn(job):
        with tempfile.TemporaryDirectory(prefix="rostrum_world_") as tmp:
            raw = Path(tmp) / "world.png"
            shown = world_png(ctx.tool, scene, t, rect, width, raw)
            w, h = draw_overlay(raw, dest, comp, t, shown, path)
        q = wf.quad(comp, t)
        moves = view.leaves_home(view.of(comp), comp)
        say = (f'The world of {comp["id"]} at {t:.3f} s (frame {frame}): world px {shown["x"]:.0f},{shown["y"]:.0f} to '
               f'{shown["x"] + shown["w"]:.0f},{shown["y"] + shown["h"]:.0f}, {w}×{h} picture. The frame is outlined '
               f'({"and its path drawn" if path and moves else "it never leaves home" if not moves else "path off"}); outside it is veiled.')
        if moves:
            keys, cuts = ", ".join(f"{k:.2f}" for k in wf.key_times(comp)), ", ".join(f"{c:.2f}" for c in wf.cuts(comp))
            say += f" Frame keys at {keys} s" + (f"; it jumps (a cut) at {cuts} s" if cuts else "") + "."

        return Reply(say, {"time": t, "frame": frame, "world": shown, "frame_corners": [[round(x, 1), round(y, 1)] for x, y in q],
                           "keys": wf.key_times(comp), "width": w, "height": h}, [dest], [dest], scene.get("warnings", []))

    return ctx.long(f'look_frame (what: world) {comp["id"]} f{frame}', job_fn)


def _spans(times: list[float], flags: list[bool], step: float) -> list[dict]:
    """The runs of times where a flag holds, as {from, to}; a run ends at the next time it doesn't hold (to within a step)."""
    out, start = [], None
    for i, (t, on) in enumerate(zip(times, flags)):
        if on and start is None:
            start = t
        if start is not None and (not on or i == len(times) - 1):
            out.append({"from": round(start, 3), "to": round(t if on else times[i - 1], 3)})
            start = None
    return out


@tools.tool("look_in_frame", {"properties": {**ITEM_COMP, **TIME,
        "from": {"type": "number", "minimum": 0, "description": "Start of a span, seconds (with `to`, instead of `time`)."},
        "to": {"type": "number", "minimum": 0, "description": "End of the span, seconds."},
        "step": {"type": "number", "exclusiveMinimum": 0, "description": "Seconds between looks over a span. Default: the span over 48 (and always the frame's keys and each layer's start and end)."}}})
def look_in_frame(ctx, args):
    """What is in, partly in or out of the frame. At one time (`time` or `frame`): every top-level layer as `in` (all of its box in
    the picture), `partly` (with the share of its box inside, in %) or `out`, whether it is showing at all (opacity, start / end
    times, mattes: `why_not_showing`), its box in output px and in world px. Over a span (`from`, `to`, optionally `step`): for each
    layer the time spans it shows in the frame, when it enters and leaves. Boxes only (effects and masks aren't counted;
    look_frame shows the real picture). Answers "what is in the frame at 3 s?" and "does this layer ever come into shot?"."""
    doc, comp = doc_and_comp(ctx, args)
    if "from" in args or "to" in args:
        if "time" in args or "frame" in args:
            raise RostrumError(codes.BAD_ARGUMENT, ctx.tool, '"time" with "from" / "to"', "were both given", hint="Give one time, or a span.")
        fps, last = comp.get("fps", 30), (round(comp.get("duration", 5.0) * comp.get("fps", 30)) - 1) / comp.get("fps", 30)
        a, b = args.get("from", 0.0), args.get("to", last)
        b = last if last < b <= comp.get("duration", 5.0) + 1e-9 else b
        if not 0 <= a < b <= last + 1e-9:
            raise RostrumError(codes.BAD_ARGUMENT, ctx.tool, f"span {a}–{b} s", f"must satisfy 0 <= from < to <= {last:.3f} (the last frame)")
        step = args.get("step", (b - a) / 48)
        grid = [a + i * step for i in range(int((b - a) / step) + 1)] + [b]
        extra = {t for k in wf.key_times(comp) for t in (k, k - 1 / fps) if a <= t <= b}
        extra |= {n[f] for n in comp.get("layers", []) if n["type"] != "camera" for f in ("start", "end") if isinstance(n.get(f), (int, float)) and a <= n[f] <= b}
        times = sorted({round(round(t * fps) / fps, 4) for t in [*grid, *extra]})
        times = [t for t in times if round(t * fps) < round(comp.get("duration", 5.0) * fps)]
        seen = [{r["id"]: r for r in wf.in_frame(comp, t)} for t in times]
        rows = []
        for lid in seen[0]:
            on = [s[lid]["state"] != "out" and s[lid]["showing"] for s in seen]
            spans = _spans(times, on, step)
            rows.append({"id": lid, "type": seen[0][lid]["type"], "spans": spans, "ever": bool(spans), "always": all(on),
                         "enters": [s["from"] for s in spans if s["from"] > times[0]], "leaves": [s["to"] for s in spans if s["to"] < times[-1]]})
        words = [f'{r["id"]}: ' + ("never in shot" if not r["ever"] else "in shot the whole span" if r["always"] else
                 "; ".join(f'{s["from"]:g}–{s["to"]:g} s' for s in r["spans"])) for r in rows]
        return Reply(f'In the frame of {comp["id"]}, {a:g}–{b:g} s ({len(times)} looks): ' + " | ".join(words) + ". Boxes only; spans are exact to the looks.",
                     {"from": a, "to": b, "looks": len(times), "layers": rows})
    t, frame = time_of(ctx, comp, args)
    rows = wf.in_frame(comp, t)
    show = lambda r: f'{r["id"]}' + (f' ({r["share"]} %)' if r["state"] == "partly" else "")
    got = {s: [show(r) for r in rows if r["state"] == s and r["showing"]] for s in ("in", "partly", "out")}
    hidden = [f'{r["id"]} ({", ".join(r["why_not_showing"])})' for r in rows if not r["showing"]]
    say = (f'In the frame of {comp["id"]} at {t:.3f} s (frame {frame}) — in: {", ".join(got["in"]) or "nothing"}; partly in: {", ".join(got["partly"]) or "nothing"}; '
           f'out (showing, but beside the frame): {", ".join(got["out"]) or "nothing"}' + (f'; not showing at all: {"; ".join(hidden)}' if hidden else "") + ". Boxes only.")
    return Reply(say, {"time": t, "frame": frame, "frame_corners": [[round(x, 1), round(y, 1)] for x, y in wf.quad(comp, t)], "layers": rows})
