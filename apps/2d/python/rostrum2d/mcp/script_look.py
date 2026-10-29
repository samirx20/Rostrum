"""run_script `look`: after the merge, one contact sheet of the moments asked for, in the same reply; with `notes: true`
also what look_frame what "review"'s checks measured (notes, never a verdict). The rival's loop is "one program, look at
stills, edit, re-run" in ~13 calls; ours took ~40 (a look_frame after every run_script, then polling). App.script_look
calls `after_run`.

One engine pass draws the sheet's tiles and, with notes, the review's tiny samples (every 0.5 s); the document's facts
come from review.doc_faults. Seconds for a 30 s film, inside the call's budget; past it the reply names the job to ask."""
from __future__ import annotations

import tempfile
from pathlib import Path

from rostrum_core.errors import RostrumError
from rostrum_core.mcp import Reply, sheet
from rostrum_core.mcp.files import look_path

from . import film_faults, look_empty, look_quality, render, review
from .look import SHEET_WIDTH
from .pick import doc_and_comp

SPREAD = 6          # look: true -> this many moments, the middles of equal parts of the film


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


def after_run(ctx, doc, look, reply: Reply) -> Reply:
    """App.script_look: `reply` (the merge's) with the sheet added (and the notes, when the call asked: ctx.asked_notes). The merge stands whatever happens to the
    look: a look that fails says so in the summary (never a silent gap, never an error over a merge that happened)."""
    try:
        return _looked(ctx, doc, look, reply)
    except RostrumError as e:
        reply.summary += f"\nLook FAILED, no sheet: {e.line()} The script itself was merged; look_frame times [..] to look."
        reply.data["look"] = {"failed": e.line()}
        return reply


def _looked(ctx, doc, look, reply: Reply) -> Reply:
    _, comp = doc_and_comp(ctx, {})
    fps, duration = comp.get("fps", 30), comp.get("duration", 5.0)
    times, past = moments(look, duration, fps)
    reply.warnings += past
    every = look_empty.EVERY
    noting = bool(getattr(ctx, "asked_notes", False))
    samples = [min(round(i * every, 4), (round(duration * fps) - 1) / fps) for i in range(int(duration / every + 1e-9))] if noting else []
    found, measured, notes = film_faults.collect(doc.data, comp, samples, ctx.tool) if noting else ([], [], [])
    scene = render.look_scene(doc, comp["id"], times=[*times, *samples])
    cols = 3 if len(times) in (5, 6, 9) else min(4, len(times))
    tile_w = sheet.tile_width(SHEET_WIDTH, cols)
    dest = look_path(f'{doc.item_id or "doc"}_{comp["id"]}_script_look', project=doc.folder)

    def job_fn(job):
        with tempfile.TemporaryDirectory(prefix="rostrum_script_look_") as tmp:
            tiles = [(t, Path(tmp) / f"t{i}.png") for i, t in enumerate(times)]
            tiny = [(t, Path(tmp) / f"s{i}.png") for i, t in enumerate(samples)]
            step = lambda done, total: job.progress(done, len(tiles) + len(tiny))
            preview = look_quality.samples(look_quality.PREVIEW)      # the canvas's picture: quick on any film
            render.small_stills(ctx.tool, scene, tiles, tile_w, step, preview)
            render.small_stills(ctx.tool, scene, tiny, look_empty.SAMPLE_W, lambda d, n: step(len(tiles) + d, n), preview)
            w, h = sheet.contact_sheet([(png, f"{t:.2f} s   f{round(t * fps)}") for t, png in tiles], tile_w, cols, dest)
            pixels = look_empty.scan_pngs(tiny, every, duration) if noting else []
        rows = review.ranked(pixels + found, duration)
        return Reply("", {"times": times, "sheet": str(dest), "width": w, "height": h, "comp": comp["id"],
                          **({"notes": [{k: r[k] for k in ("kind", "rank_kind", "start", "end", "text", "id", "ids") if k in r} for r in rows],
                              "info": [r["text"] for r in measured]} if noting else {})},
                     [dest], [dest], scene.get("warnings", []) + notes)

    got = ctx.long(f'run_script look {comp["id"]}', job_fn)
    reply.warnings += [w for w in got.warnings if w not in reply.warnings]
    if got.data.get("status") != "done":
        reply.summary += (f'\nLook: still drawing (job {got.data.get("job_id")}); inspect_job with wait_s gives the sheet.')
        reply.data["look"] = {"job_id": got.data.get("job_id"), "status": got.data.get("status")}
        return reply
    seen = got.data["result"]
    said = f'\nLook at {comp["id"]}: contact sheet of {len(times)} moments ({", ".join(f"{t:g}" for t in times)} s), {seen["width"]}×{seen["height"]}. '
    said += look_quality.line(comp, look_quality.PREVIEW) + (' (look_frame with quality "final" for one moment.)' if look_quality.blurred(comp) else "")
    reply.summary += said
    reply.data["look"] = seen
    reply.files += got.files
    reply.images += got.images
    if noting:                  # asked for: what the checks measured closes the reply (shared faults.py)
        reply.faults = film_faults.as_notes(seen["notes"])
    return reply
