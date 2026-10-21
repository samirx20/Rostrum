"""`path.width`: the variable width of a path's stroke (taper at the ends and/or a width profile along the line) in one
undoable step. The engine reads `taperStart`, `taperEnd`, `widthProfile` and `taperAlong` (fields.py, group Width)."""
from __future__ import annotations

from rostrum_core import Param
from rostrum_core.errors import codes

from . import widthprofile as W
from .kind import REGISTRY as R

TAPER = lambda name, label, help: Param.number(name, label=label, min=0, max=1, step=0.01, importance="primary", help=help)  # noqa: E731


@R.operation("path.width", "Vary a path's stroke width: taper the start and/or end (a fraction of the line's length over "
             "which the width grows from 0, or shrinks to 0) and/or give a width profile, pairs [position 0..1, multiplier of "
             "strokeWidth], positions increasing. `even` removes the profile. Only what you pass changes. The stroke must be on.",
             target="path", label="Stroke width",
             params=[TAPER("taperStart", "Taper start", "How much of the line the width takes to grow from 0 at the start (0..1)"),
                     TAPER("taperEnd", "Taper end", "How much of the line the width takes to shrink to 0 at the end (0..1)"),
                     Param.points("profile", label="Width profile", min=2, max=2, importance="secondary",
                                  help="[[position, multiplier], …]: position 0..1 along the line, increasing; multiplier of strokeWidth, 0 or more"),
                     Param.toggle("even", label="Even width", importance="deep", help="Remove the profile"),
                     Param.choice("taperAlong", ["line", "drawn"], label="Measured along", importance="deep",
                                  labels={"line": "Whole line", "drawn": "Drawn part"})])
def path_width(ctx, targets, args):
    if "profile" in args and args.get("even"):
        ctx.fail(codes.BAD_ARGUMENT, "profile / even", "can't be given together")
    text = None
    if "profile" in args:
        pairs = [(p, m) for p, m in args["profile"]]
        text = W.format(pairs)
        try:
            W.parse(text)
        except ValueError as e:
            ctx.fail(codes.BAD_ARGUMENT, "profile", str(e))
    elif args.get("even"):
        text = ""
    if text is None and not {"taperStart", "taperEnd", "taperAlong"} & set(args):
        ctx.fail(codes.BAD_ARGUMENT, "args", "changes nothing", ["taperStart", "taperEnd", "profile", "even", "taperAlong"])
    for t in targets:
        if not ctx.item(t).get("stroke"):
            ctx.fail(codes.BAD_ARGUMENT, f'target "{t}"', "has its stroke off, so a width would show nothing; set stroke=true first")
        for k in ("taperStart", "taperEnd", "taperAlong"):
            if k in args:
                ctx.set(t, k, args[k])
        if text is not None:
            ctx.set(t, "widthProfile", text)
