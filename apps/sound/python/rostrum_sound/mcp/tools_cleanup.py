"""render_cleanup (a job: makes the missing cleaned takes of a document's clips) and look_cleanup (the agent's ears on a
cleanup: before vs after, and the stems). The document holds the settings; the takes live in the cache, so making
them never edits the document. Guide: inspect_guide 'cleanup' (apps/sound/CLEANUP.md)."""
from __future__ import annotations

from pathlib import Path

from rostrum_core import RostrumError, codes
from rostrum_core.mcp import Reply, Tools

from .. import clean_clips, cleanup, listen

ITEM = {"item": {"type": "string", "description": "The Sound document's item id. Optional when only one is open."}}
FILES = {"type": "object", "additionalProperties": {"type": "string"},
         "description": "{stem name: absolute WAV path}, e.g. {\"vocals\": \"C:\\\\...\\\\v.wav\", \"drums\": ...}."}


def _file(path, where):
    if not Path(path).is_file():
        raise RostrumError(codes.NOT_FOUND, where, f'"{path}"', "is not a file")
    return str(path)


def _dB(x):
    return "n/a" if x is None else f"{x:+.1f} dB"


def _made(media, recipe, clip_id, what):
    f = cleanup.cached(media, recipe)
    if f is None:
        raise RostrumError(codes.NOT_FOUND, "look_cleanup", f'clip "{clip_id}"\'s {what}', "is not made yet",
                           hint="Run the render_cleanup tool first.")
    return f


def _from_clip(doc, clip_id):
    """(before, after or None, stems or None) for a clip: its file, its cleaned take, and its four stems when it
    plays a stem or all four are already made."""
    c = doc.item(clip_id)
    if c.get("type") != "clip":
        raise RostrumError(codes.BAD_ARGUMENT, "look_cleanup", f'"{clip_id}"', "is not a clip")
    media, recipe = c["media"], cleanup.recipe_of(c)
    after = _made(media, recipe, clip_id, "cleaned take") if recipe else None
    found = {s: cleanup.cached(media, {"stem": s}) for s in cleanup.STEMS}
    stems = None
    if recipe.get("stem") or all(found.values()):
        stems = {s: _made(media, {"stem": s}, clip_id, f"{s} stem") for s in cleanup.STEMS}
    if after is None and stems is None:
        raise RostrumError(codes.BAD_ARGUMENT, "look_cleanup", f'clip "{clip_id}"', "has no cleanup step set and no stems made",
                           hint="Set stem, isolate, denoise or dereverb (clip.set), run render_cleanup, then look.")
    return media, after, stems


def register(tools: Tools):
    @tools.tool("render_cleanup", {"properties": {**ITEM, "ids": {"type": "array", "items": {"type": "string"},
        "description": "Only these clip ids; left out = every clip that plays a cleaned take."}}})
    def render_cleanup(ctx, args):
        """Make the missing cleaned takes of the document's clips (their stem / isolate / denoise / dereverb settings; each step's model loads for it and is released). Answers per clip: id, media (the original), file (the cleaned take), generated or cached, steps. Then look_cleanup to hear the difference, and render_mix."""
        doc = ctx.document(args.get("item"))
        ids = args.get("ids") or None

        def work(job):
            made = clean_clips.make_clips(doc, ids, progress=lambda note: job.progress(note=note))
            new = sum(1 for m in made if m["generated"])
            return Reply(f"{len(made)} cleaned takes ready ({new} made now, {len(made) - new} from the cache).",
                         {"clips": made}, [m["file"] for m in made])

        return ctx.long(f"cleanup {doc.item_id}", work, key=f"cleanup:{doc.item_id}:{ids}")

    @tools.tool("look_cleanup", {"properties": {**ITEM,
        "clip": {"type": "string", "description": "A clip id: its file before vs its cleaned take, and its stems when made."},
        "before": {"type": "string", "description": "A WAV before cleanup (absolute path; with after)."},
        "after": {"type": "string", "description": "The same WAV after cleanup (absolute path)."},
        "stems": {**FILES, "description": "Stems to check for leakage and level: " + FILES["description"]},
        "reference": {**FILES, "description": "Reference stems (the true parts) to score the stems against (SDR): " + FILES["description"]}}})
    def look_cleanup(ctx, args):
        """Hear a cleanup. Before vs after: noise floor (quiet 10th percentile of 50 ms frames), speech level (90th), their gap and the reverb tail (how far the level falls in the 200 ms after speech stops), with stacked before / after spectrograms marking floor and level. Stems: each one's level, leakage (correlation of every pair's level envelopes) and, with reference stems, SDR in dB, with a level-over-time picture."""
        doc = ctx.document(args.get("item"))
        where, look = "look_cleanup", ctx.app.state.look_dir(doc.item_id)
        before, after, stems = args.get("before"), args.get("after"), args.get("stems")
        if args.get("clip"):
            before, after, clip_stems = _from_clip(doc, args["clip"])
            stems = stems or clip_stems
        if bool(before) != bool(after) and not args.get("clip"):
            raise RostrumError(codes.BAD_ARGUMENT, where, "before / after", "must be given together")
        if not (after or stems):
            raise RostrumError(codes.BAD_ARGUMENT, where, "the files", "are missing",
                               hint="Pass clip, or before and after, or stems.")
        facts, pngs, said = {}, [], []
        if after:
            name = args.get("clip") or Path(after).stem
            r = listen.clean_compare(_file(before, where), _file(after, where), str(look / f"{name}-cleanup.png"))
            facts["compare"], c = r, r["change"]
            pngs.append(r["png"])
            said.append(f"change after - before: floor {_dB(c['floor_db'])}, gap {_dB(c['gap_db'])}, "
                        f"tail drop {_dB(c['tail_drop_db'])}")
        if stems:
            name = args.get("clip") or Path(next(iter(stems.values()))).stem
            r = listen.stems_check({k: _file(v, where) for k, v in stems.items()}, str(look / f"{name}-stems.png"),
                                   {k: _file(v, where) for k, v in (args.get("reference") or {}).items()} or None)
            facts["stems"] = r
            pngs.append(r["png"])
            worst = max(r["leakage"], key=lambda x: x["correlation"] or 0)
            said.append(f"{len(stems)} stems, most leakage {'/'.join(worst['pair'])} ({worst['correlation']})"
                        + (f", SDR {r['sdr_db']}" if "sdr_db" in r else ""))
        return Reply("; ".join(said) + ".", facts, pngs, pngs)
