"""inspect_lipsync: the agent's ears on lip sync. Phones, words and mouth cues of a voice clip, in comp seconds."""
from __future__ import annotations

from pathlib import Path

from rostrum_core.mcp import Reply, Tools

from rostrum_core.lipsync.track import TIMING, track
from rostrum_core.lipsync.visemes import SHAPES
from .pick import ITEM_COMP, doc_and_comp

tools = Tools()
NUM = {"type": "number", "minimum": 0}


@tools.tool("inspect_lipsync", {"properties": {
    **ITEM_COMP,
    "source": {"type": "string", "description": "The voice clip: a WAV file (absolute, or inside the project folder)."},
    "text": {"type": "string", "description": "The words said in the clip (English). Without: the model's own hearing."},
    "at": {**NUM, "description": "Comp seconds where the clip starts. Default 0."},
    "start": {**NUM, "description": "Seconds into the file where the clip starts. Default 0."},
    "end": {**NUM, "description": "Seconds into the file where the clip ends. Default: the file's end."},
    "pronounce": {"type": "object", "description": 'Sounds for words CMUdict lacks: {"rostrum": "R AA1 S T R AH0 M"}.'},
    "shapes": {"type": "object", "description": f"Optional {{shape: mouth layer id}} (shapes {', '.join(SHAPES)}): "
                                                "the answer then says which layer shows when."},
    **{k: {**NUM, "description": f"Timing tool (LIPSYNC.md). Default {v}."} for k, v in TIMING.items()}},
    "required": ["source"]})
def inspect_lipsync(ctx, args):
    """Hear a voice clip as lip sync does: every phone (IPA, and ARPAbet when the text is given) and word with start and end, and
    the mouth cues (shapes X A B C D E F G H) after the timing tools, all in composition seconds at the comp's frame rate. The first
    call on a clip runs the phone model (a few seconds, GPU); the answer is cached, so calls after it (and lipsync.apply /
    lipsync() on the same clip) are instant. Facts only: changes nothing."""
    _, comp = doc_and_comp(ctx, args)
    src = Path(args["source"])
    if not src.is_absolute() and getattr(ctx.app, "folder", None):
        src = Path(ctx.app.folder) / src
    timing = {k: args[k] for k in TIMING if k in args}

    def job_fn(job):
        out = track(src, args.get("at", 0.0), comp.get("fps", 30), args.get("shapes"), args.get("text"),
                    args.get("start", 0.0), args.get("end"), pronounce=args.get("pronounce"), where=ctx.tool, **timing)
        out.pop("keys", None)
        words = ", ".join(f'{w["word"]} {w["start"]:.2f}–{w["end"]:.2f}' for w in out["words"][:40])
        changes = len(out["cues"])
        text = (f'{len(out["phones"])} phones ({out["mode"]}, {"computed on " + out["device"] if out["computed"] else "from the cache"}), '
                f'{changes} mouth cue{"s" * (changes != 1)} over {out["cues"][0]["start"]:.2f}–{out["cues"][-1]["end"]:.2f} s.'
                + (f" Words: {words}." if words else ""))
        return Reply(text, out)

    return ctx.long(f"inspect_lipsync {src.name}", job_fn)
