"""lipsync.make(mouth, line): key a mouth group's shapes to a voice line from RostrumSound (SPEC §9 Lip sync from Sound).

A mouth is a group whose children are the mouth shapes (mouths.py). The phones of the line are heard once (cached),
become mouth shapes in time (rostrum_core.lipsync: the same timing as 2D), and every child gets Scale keys, held:
its own Scale while its shape shows, nearly nothing (mouths.HIDDEN) while another does. One shows at a time. It is
one change (one undo); the keys are ordinary keys on the timeline, so a person moves or deletes them afterwards, and
a second run only adds keys where there is none at that time (a key already there is left as it is).
"""
from __future__ import annotations

from rostrum_core import Param
from rostrum_core.errors import codes
from rostrum_core.keys import keys_of
from rostrum_core.keys.marked import same_time
from rostrum_core.lipsync import voice, visemes as V
from rostrum_core.lipsync.mouths import WORDS
from rostrum_core.lipsync.track import track

from . import mouths
from .kind import REGISTRY as R
from .ops_keys import put_key

DEFAULT_FPS = 24
PARAMS = [
    Param.text("line", label="Voice line", help='A voice line of the project as "<song>/<line id>" (inspect_voice_lines '
                                                 "lists them): its made take and where it starts come from RostrumSound"),
    Param.text("file", label="Voice file", control="file", filters=["WAV sound (*.wav)"], importance="secondary",
               help="Instead of a line: a WAV file (absolute path)"),
    Param.text("text", label="Words said", importance="secondary", help="With `file`: the words said (English); without, "
                                                                          "the model's own hearing is used"),
    Param.number("at", label="Starts at", min=0, max=36000, unit="s", importance="secondary",
                 help="With `file`: where the voice starts in the shot, in seconds (default 0)"),
    *(Param.id(f"shape{s}", kind="item", importance="secondary", label=f"Mouth {s}: {WORDS[s]}",
               help="The child that shows for this shape; left out, read from the children's names") for s in V.SHAPES),
]


def _fps(ctx) -> float:
    shots = [loc.item for loc in ctx.idx.values() if loc.item.get("type") == "shot"]
    return float(shots[0].get("fps", DEFAULT_FPS)) if shots else DEFAULT_FPS


def _source(ctx, args) -> dict:
    """{file, at, text (None: let the model hear it)} from a project voice line, or from file / text / at."""
    if bool(args.get("line")) == bool(args.get("file")):
        ctx.fail(codes.BAD_ARGUMENT, "line / file", "needs exactly one of them", hint="Give `line` (a project voice line) "
                 "or `file` (a WAV).")
    if args.get("file"):
        return {"file": args["file"], "at": args.get("at", 0.0), "text": args.get("text") or None}
    found = {ln["id"]: ln for ln in voice.lines(ctx.doc.folder)}
    if args["line"] not in found:
        ctx.fail(codes.NOT_FOUND, "line", f'"{args["line"]}" is not a voice line of this project', sorted(found),
                 hint="Write the line in RostrumSound first.")
    ln = found[args["line"]]
    if not ln["file"]:
        ctx.fail(codes.BAD_ARGUMENT, "line", f'"{ln["text"]}" has no voice yet', hint="Make voice in RostrumSound first.")
    return {"file": ln["file"], "at": ln["at"], "text": ln["text"] if ln["english"] else None}


def _shapes(ctx, mouth: dict, args) -> dict:
    said = {s: args[f"shape{s}"] for s in V.SHAPES if args.get(f"shape{s}")}
    shapes = {**mouths.guess(mouth), **said}
    own = {c["id"] for c in mouths.kids(mouth)}
    outside = sorted(c for c in shapes.values() if c not in own)
    if outside:
        ctx.fail(codes.BAD_ARGUMENT, "mouth shapes", f"{outside} are not children of {mouth['id']} that can be scaled",
                 sorted(own))
    if not shapes:
        ctx.fail(codes.BAD_ARGUMENT, "mouth", f'"{mouth["id"]}" has no children named as mouth shapes',
                 [f"shape{s}" for s in V.SHAPES], hint="Name the children (mouth_rest, mouth_closed, mouth_wide …) or give shapeX … shapeH.")
    return shapes


@R.operation("lipsync.make", "Key a mouth (a group whose children are the mouth shapes, one per shape X rest, A closed, "
             "B slightly open, C open, D wide open, E rounded, F puckered, G teeth on lip, H tongue up) to a voice line "
             "from RostrumSound: Scale keys, held, show one shape at a time (the others sit at almost nothing). Shapes "
             "are read from the children's names or given as shapeX … shapeH; a missing shape shows the nearest one "
             "given. One undo step; adds keys only, keys already there stay.",
             target=("group",), label="Lip sync", params=PARAMS)
def lipsync_make(ctx, targets, args):
    src = _source(ctx, args)
    fps = _fps(ctx)
    for t in targets:
        mouth = ctx.item(t)
        shapes = _shapes(ctx, mouth, args)
        try:
            job = track(src["file"], src["at"], fps, shapes, src["text"], where=ctx.where)
        except ValueError as e:
            ctx.fail(codes.BAD_ARGUMENT, "mouth shapes", str(e))
        for child, plan in job["keys"].items():
            node = ctx.item(child)
            for at, on in plan.items():
                for prop in mouths.SHOWS:
                    if any(same_time(k["t"], at) for k in keys_of(node, prop)):
                        continue
                    put_key(ctx, child, prop, at, {"v": float(node.get(prop, 1.0)) if on else mouths.HIDDEN,
                                                   "ease": "hold", "from": "lip sync"})
