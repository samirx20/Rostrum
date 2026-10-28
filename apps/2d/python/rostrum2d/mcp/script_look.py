"""run_script `look`: after the merge, one contact sheet of the moments asked for and the film's weakest moments (the
look_review faults, one line each with times), in the same reply. The rival's loop is "one program, look at stills, edit,
re-run" in ~13 calls; ours took ~40 (a look_frame after every run_script, then polling). App.script_look calls `after_run`.

One engine pass draws the sheet's tiles and the review's tiny samples (every 0.5 s); the document's facts come from
review.doc_faults. Seconds for a 30 s film, inside the call's budget; past it the reply names the job to ask."""
from __future__ import annotations

import tempfile
from pathlib import Path

from rostrum_core.errors import RostrumError
from rostrum_core.mcp import Reply, sheet
from rostrum_core.mcp.faults import fault
from rostrum_core.mcp.files import look_path

from . import edge_cut, look_empty, render, review
from .look import SHEET_WIDTH
from .pick import doc_and_comp

SPREAD = 6          # look: true -> this many moments, the middles of equal parts of the film
FAULTS = 8          # faults named in the summary (all of them are in the data)


def moments(look, duration: float, fps: float) -> tuple[list[float], list[str]]:
    """The times to look at: `look` seconds (each on a frame, the end on the last one), or SPREAD spread over the film;
    and a warning for times past the end (left out: the merge already happened, so the call is not failed for them)."""
    last = (round(duration * fps) - 1) / fps
    spread = [round(round((i + 0.5) * duration / SPREAD * fps) / fps, 4) for i in range(SPREAD)]
    if look is True:
        return spread, []
    past = [t for t in look if t > duration + 1e-9]
    out = sorted({round(min(round(t * fps) / fps, last), 4) for t in look if t <= duration + 1e-9})
    warn = [f'look: {", ".join(f"{t:g}" for t in past)} s {"is" if len(past) == 1 else "are"} past the end of the film ({duration:g} s), left out'
            + ("" if out else f"; looked at {SPREAD} moments spread over the film instead")] if past else []
    return out or spread, warn


def _line(r: dict) -> str:
    return f"- {r['text']}"


def after_run(ctx, doc, look, reply: Reply) -> Reply:
    """App.script_look: `reply` (the merge's) with the sheet and the faults added. The merge stands whatever happens to the
    look: a look that fails says so in the summary (never a silent gap, never an error over a merge that happened)."""
    try:
        return _looked(ctx, doc, look, reply)
    except RostrumError as e:
        reply.summary += f"\nLook FAILED, no sheet or faults: {e.line()} The script itself was merged; look_frame times [..] or look_review to look."
        reply.data["look"] = {"failed": e.line()}
        return reply


def _looked(ctx, doc, look, reply: Reply) -> Reply:
    _, comp = doc_and_comp(ctx, {})
    fps, duration = comp.get("fps", 30), comp.get("duration", 5.0)
    times, past = moments(look, duration, fps)
    reply.warnings += past
    every = look_empty.EVERY
    samples = [min(round(i * every, 4), (round(duration * fps) - 1) / fps) for i in range(int(duration / every + 1e-9))]
    faults, notes = review.doc_faults(doc.data, comp, None, ctx.tool)
    rigs, more = edge_cut.rig_boxes(doc.data, comp, samples)
    cuts = review._cuts(edge_cut.scan(comp, samples, rigs, every))
    frames = sorted({round(t * fps) for t in times + samples})
    scene = render.scene_of(doc, comp["id"], (frames[0] / fps, frames[-1] / fps), frames)
    cols = 3 if len(times) in (5, 6, 9) else min(4, len(times))
    tile_w = sheet.tile_width(SHEET_WIDTH, cols)
    dest = look_path(f'{doc.item_id or "doc"}_{comp["id"]}_script_look', project=doc.folder)

    def job_fn(job):
        with tempfile.TemporaryDirectory(prefix="rostrum_script_look_") as tmp:
            tiles = [(t, Path(tmp) / f"t{i}.png") for i, t in enumerate(times)]
            tiny = [(t, Path(tmp) / f"s{i}.png") for i, t in enumerate(samples)]
            step = lambda done, total: job.progress(done, len(tiles) + len(tiny))
            render.small_stills(ctx.tool, scene, tiles, tile_w, step)
            render.small_stills(ctx.tool, scene, tiny, look_empty.SAMPLE_W, lambda d, n: step(len(tiles) + d, n))
            w, h = sheet.contact_sheet([(png, f"{t:.2f} s   f{round(t * fps)}") for t, png in tiles], tile_w, cols, dest)
            pixels = look_empty.scan_pngs(tiny, every, duration)
        rows = review.ranked(pixels + cuts + faults, duration)
        return Reply("", {"times": times, "sheet": str(dest), "width": w, "height": h, "comp": comp["id"],
                          "faults": [{k: r[k] for k in ("kind", "start", "end", "text", "id", "ids") if k in r} for r in rows],
                          "info": [r["text"] for r in review.info(faults)]},
                     [dest], [dest], scene.get("warnings", []) + notes + more)

    got = ctx.long(f'run_script look {comp["id"]}', job_fn)
    reply.warnings += [w for w in got.warnings if w not in reply.warnings]
    if got.data.get("status") != "done":
        reply.summary += (f'\nLook: still drawing (job {got.data.get("job_id")}); inspect_job with wait_s gives the sheet and the faults.')
        reply.data["look"] = {"job_id": got.data.get("job_id"), "status": got.data.get("status")}
        return reply
    seen = got.data["result"]
    rows = seen["faults"]
    said = (f'\nLook at {comp["id"]}: contact sheet of {len(times)} moments ({", ".join(f"{t:g}" for t in times)} s), {seen["width"]}×{seen["height"]}. '
            + (f"Weakest moments, most visible first ({len(rows)}):\n" + "\n".join(map(_line, rows[:FAULTS]))
               + (f"\n({len(rows) - FAULTS} more in data.look.faults.)" if len(rows) > FAULTS else "")
               + "\nLayout faults (a device cut, a text crossed, a pointer on a label, a tiny end card) come first and name the fix. "
                 "Fix in the script and re-run it under the same name with look." if rows else
               "No weak moment found (blank, held, cut-off, faint leftovers, stray specks, crowded lock-ups, texts crossed or on texts, "
               "a pointer on a label, a device cut by the edge, a tiny end card). Judge the sheet for the rest."))
    reply.summary += said
    reply.data["look"] = seen
    reply.files += got.files
    reply.images += got.images
    reply.faults = [fault(f'{r["kind"]}:{r["id"]}' if r.get("id") else r["kind"], r["text"], "change it in the script and re-run under the same name", f'{r["start"]:g} s' if "start" in r else None) for r in rows]   # faults first (shared faults.py)
    return reply
