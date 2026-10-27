"""render_voice: makes the spoken audio of a document's voice lines (a job; one line at a time). The document holds the
words; the audio lives in the cache, so making a take never edits the document."""
from __future__ import annotations

from rostrum_core.mcp import Reply, Tools

from .. import voice_estimate, voice_lines, voice_words

ITEM = {"item": {"type": "string", "description": "The Sound document's item id. Optional when only one is open."}}


def register(tools: Tools):
    @tools.tool("render_voice", {"properties": {**ITEM, "ids": {"type": "array", "items": {"type": "string"},
        "description": "Only these line ids; left out = every voice line of the document."}}})
    def render_voice(ctx, args):
        """Make the missing takes of the document's voice lines (loads the voice model per line, about twice the line's length each). To fit a line to the music before making it, ask `render_voice` (what \"estimate\"). Answers per line: id, file, seconds, generated or cached, start and end in seconds (so the next line can be timed). Then render_mix and listen with the look_* tools. On a busy computer each line waits its turn (one model job at a time on the machine) and for free memory, up to 5 min, then fails plainly saying what was free."""
        doc = ctx.document(args.get("item"))
        ids = args.get("ids") or None

        def work(job):
            made = voice_lines.make_lines(doc, ids, progress=lambda note: job.progress(note=note))
            new = sum(1 for m in made if m["generated"])
            return Reply(f"{len(made)} voice lines ready ({new} made now, {len(made) - new} from the cache).",
                         {"lines": made}, [m["file"] for m in made])

        return ctx.long(f"voice {doc.item_id}", work, key=f"voice:{doc.item_id}:{ids}")

    @tools.tool("render_voice_words", {"properties": {**ITEM, "ids": {"type": "array", "items": {"type": "string"},
        "description": "Only these line ids; left out = every voice line of the document."},
        "read_only": {"type": "boolean", "description": "true = only read the stored words, never listen (fails loudly for a line not heard yet)."}}})
    def render_voice_words(ctx, args):
        """Each spoken word's start and end, in song seconds, for the voice lines (lip sync, captions, timing a cut to a word). The made take is listened to once by the speech model (CPU, a few seconds per line) and the words are stored by content, so asking again reads them; read_only never runs the model. Make the takes first with render_voice. The first time, it installs the program that runs the model (sherpa-onnx, Apache-2.0, ~19 MB) by itself. Answers per line: id, text, start, end and words [{word, start, end}]."""
        doc = ctx.document(args.get("item"))
        ids = args.get("ids") or None
        if args.get("read_only"):
            rows = voice_words.read(doc, ids)
            return Reply(f"Stored words of {len(rows)} voice line(s).", {"lines": rows})

        def work(job):
            rows = voice_words.compute(doc, ids, progress=lambda note: job.progress(note=note))
            new = sum(1 for r in rows if r["heard_now"])
            return Reply(f"Words of {len(rows)} voice line(s) ready ({new} heard now, {len(rows) - new} from storage).", {"lines": rows})

        return ctx.long(f"voice words {doc.item_id}", work, key=f"voice-words:{doc.item_id}:{ids}")

    @tools.tool("render_voice_estimate", {"properties": {**ITEM, "ids": {"type": "array", "items": {"type": "string"},
        "description": "Only these line ids; left out = every voice line of the document."},
        "text": {"type": "string", "description": "Words to estimate without a document line (then no document is needed)."},
        "language": {"type": "string", "description": "With `text`: the language, as on a voice track (default auto)."}}})
    def render_voice_estimate(ctx, args):
        """How long spoken words will take BEFORE they are made, so a line can be fitted to the music: `estimated_seconds` with a range (low-high; the same words differ 10-25 % between takes, and a style like "slow" moves it more). For the document's lines (or `ids`) it also gives `made_seconds` (exact, once the take exists) and `ends_about` (the line's start plus its length); or give `text` (and `language`) alone. Counted from syllables and pauses and measured on the real voice; the exact length comes only from render_voice."""
        if args.get("text"):
            e = voice_estimate.estimate(args["text"], args.get("language", "auto"))
            return Reply(f"{args['text'][:40]!r}: {voice_estimate.said(e)}.", {"estimate": {"estimated_seconds": e["seconds"], "low": e["low"], "high": e["high"]}})
        rows = voice_lines.estimates(ctx.document(args.get("item")), args.get("ids") or None)
        return Reply("; ".join(f"{r['id']}: " + (f"{r['made_seconds']:.2f} s (made)" if r["made_seconds"] is not None else voice_estimate.said(
            {"seconds": r["estimated_seconds"], "low": r["low"], "high": r["high"]})) for r in rows) or "No voice lines.", {"lines": rows})
