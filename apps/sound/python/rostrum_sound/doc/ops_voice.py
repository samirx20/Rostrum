"""The lines of a voice track: line.add / line.set / line.remove. A line is words and a time; the audio is made
from it on request (`voice_lines.make_lines`, the `render_voice` tool, the screen's Make voice) and lives in the cache."""
from __future__ import annotations

from rostrum_core import Param, codes
from rostrum_core import ids as core_ids

from . import fields as FD
from .registry import REGISTRY, set_fields, taken

ID = Param.text("id", label="Id", help="Optional; counted when left out (<track>.line_1 …).")


@REGISTRY.operation("line.add", "Add a spoken line to a voice track: its words and when it starts (seconds, a beat "
                    "or a marker like \"#drop+0.5\"). Make the audio afterwards with the render_voice tool.",
                    target="track", params=[ID, *FD.params("line", required=True)], label="Add line")
def line_add(ctx, targets, args):
    for track in targets:
        args = dict(args)
        have = taken(ctx)
        id_ = args.pop("id", None) or core_ids.counted(have, f"{track}.line")
        if id_ in have:
            ctx.fail(codes.BAD_ARGUMENT, f'id "{id_}"', "is already used in this document")
        ctx.insert(track, "lines", {"id": id_, "type": "line", **FD.DEFAULTS["line"], **args})


REGISTRY.operation("line.set", "Change a voice line's words, time, take (seed), level or fades. New words or a new "
                   "take need their audio made again (render_voice).", target="line", params=FD.params("line"),
                   label="Edit line", fields=True)(set_fields)


@REGISTRY.operation("line.remove", "Delete voice lines (their audio stays in the cache).", target="line",
                    label="Delete line", importance="secondary")
def line_remove(ctx, targets, args):
    for t in targets:
        ctx.remove(t)
