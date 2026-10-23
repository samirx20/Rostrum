"""The song's music map as operations: tempo changes, time signature changes, key changes and sections (add / set / remove), and
`section.move` (a section and everything inside it, one undo step: `sections.py`)."""
from __future__ import annotations

from rostrum_core import Param, codes
from rostrum_core import ids as core_ids

from . import fields as FD
from . import sections
from . import values as V
from .registry import REGISTRY, set_fields, taken

ID = Param.text("id", label="Id", help="Optional; counted (tempo_1 …) or made from the name when left out.")
LABELS = {"tempo": ("tempos", "tempo change", "Add a tempo change: the tempo from that beat (or moment) on. With ramp on it glides evenly to the next "
                                                        "change's tempo instead (\"Glide to next\"; the ruler flag reads ♩ 100 ↗)."),
          "meter": ("meters", "time signature change", "Add a time signature change: the beats per bar and the beat "
                                                       "unit (6 and 8: 6/8) from that beat (or moment) on, starting a new bar there."),
          "key": ("keys", "key change", 'Add a key change ("D minor") from a time on: for agents and the screen, '
                                        "not heard."),
          "section": ("sections", "section", 'Add a named part of the song ("verse"): where it starts and ends.')}


def _id(type_, args, ctx):
    have = taken(ctx)
    id_ = args.get("id") or (f"section.{args['name']}" if type_ == "section" else core_ids.counted(have, type_))
    if id_ in have:
        ctx.fail(codes.BAD_ARGUMENT, f'id "{id_}"', "is already used in this document")
    return id_


def register(type_):
    key, label, summary = LABELS[type_]

    @REGISTRY.operation(f"{type_}.add", summary, label=f"Add {label}",
                        params=[ID, *FD.params(type_, required=True)], importance="secondary")
    def add(ctx, targets, args):
        args = dict(args)
        id_ = _id(type_, args, ctx)
        args.pop("id", None)
        ctx.insert("root", key, {"id": id_, "type": type_, **FD.DEFAULTS[type_], **args})

    REGISTRY.operation(f"{type_}.set", f"Change {label}s.", target=type_, params=FD.params(type_),
                       label=f"Edit {label}", fields=True)(set_fields)

    @REGISTRY.operation(f"{type_}.remove", f"Delete {label}s.", target=type_, label=f"Delete {label}",
                        importance="secondary")
    def remove(ctx, targets, args):
        for t in targets:
            ctx.remove(t)


for _t in LABELS:
    register(_t)


def _by(p, v, where):
    why = sections.by_problem(v)
    if why:
        V._bad(p, v, where, why, ["2.5", "-1", '{"beats": 8}', '{"beats": -4}'])
    return v


BY = V.Value("by", "number", rule=_by, required=True, unit="s", group="Section", label="Move by",
             schema={"anyOf": [{"type": "number"}, {"type": "object", "properties": {"beats": {"type": "number"}},
                                                    "required": ["beats"]}]},
             help='Seconds (2.5, -1) or {"beats": 8}: later is positive.')


@REGISTRY.operation("section.move", "Move sections and everything that starts inside them (notes, hits, clips, "
                    "sounds, lines, markers, tempo and key changes, automation points) by an amount, as one step.",
                    target="section", params=[BY], label="Move section")
def section_move(ctx, targets, args):
    plan: dict = {}
    for t in targets:                                 # every new value from the song as it was, then all set
        for id_, k, v in sections.moves(ctx.doc, ctx.item(t), args["by"]):
            plan.setdefault((id_, k), v)
    for (id_, k), v in plan.items():
        ctx.set(id_, k, v)
