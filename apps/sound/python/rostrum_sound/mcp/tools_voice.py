"""render_voice: makes the spoken audio of a document's voice lines (a job; one line at a time). The document holds the
words; the audio lives in the cache, so making a take never edits the document."""
from __future__ import annotations

from rostrum_core.mcp import Reply, Tools

from .. import voice_lines

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
