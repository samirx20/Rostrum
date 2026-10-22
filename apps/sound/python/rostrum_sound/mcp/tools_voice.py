"""render_voice: makes the spoken audio of a document's voice lines (a job; one line at a time). The document holds the
words; the audio lives in the cache, so making a take never edits the document."""
from __future__ import annotations

from rostrum_core.mcp import Reply, Tools

from .. import voice_lines, voice_words

ITEM = {"item": {"type": "string", "description": "The Sound document's item id. Optional when only one is open."}}


def register(tools: Tools):
    @tools.tool("render_voice", {"properties": {**ITEM, "ids": {"type": "array", "items": {"type": "string"},
        "description": "Only these line ids; left out = every voice line of the document."}}})
    def render_voice(ctx, args):
        """Make the missing takes of the document's voice lines (loads the voice model per line, about twice the line's length each). Answers per line: id, file, seconds, generated or cached, start and end in seconds (so the next line can be timed). Then render_mix and listen with the look_* tools."""
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
        """Each spoken word's start and end, in song seconds, for the voice lines (lip sync, captions, timing a cut to a word). The made take is listened to once by the speech model (CPU, a few seconds per line) and the words are stored by content, so asking again reads them; read_only never runs the model. Make the takes first with render_voice. Answers per line: id, text, start, end and words [{word, start, end}]."""
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
