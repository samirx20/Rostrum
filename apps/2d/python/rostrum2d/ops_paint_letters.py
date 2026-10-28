"""`paint.letters`: words painted as brush strokes (lettering.py lays out the centre lines a hand writes them with),
each stroke a real `paint.stroke` on the target, in writing order, all in one change (one undo step). With Drawn so
far (write_on.py) they write on letter by letter, stroke by stroke, at the pen's one speed.
"""
from __future__ import annotations

import rostrum_paint
from rostrum_core import Param
from rostrum_core.errors import codes

from . import lettering, ops_paint
from .kind import REGISTRY as R

_OWN = ("text", "font", "x", "y", "height", "align", "tracking", "line", "slant", "hand", "hand_seed", "path", "start")


@R.operation("paint.letters", "Paint words as brush strokes, the way a hand letters them: each letter's centre line from a "
             "single-stroke font, in the order it is written, painted with any brush (every paint.stroke setting: taper, "
             "swell, ink pool, wobble, dry brush) on a drawing or any element, in one undo step. Turn on Drawn so far "
             "(key `drawn` 0 -> 1) and the words write on stroke by stroke. Optionally on a curve (`path`, composition px), "
             "with an unsteady hand (`hand`). Letter params: height, tracking, slant, hand, hand_seed; brush params as paint.stroke. Hand-lettered titles, signatures, chalkboard and sign writing.",
             target=ops_paint.PAINTABLE, label="Letter",
             params=[Param.text("text", label="Words", default="", required=True,
                                help="What to write; a new line (\\n) starts the next line. Plain English letters, digits and punctuation"),
                     Param.choice("font", list(lettering.FONTS), label="Lettering", default="script",
                                  help="The hand: script (joined handwriting), script heavy (its double-line form), cursive, "
                                       "sans, serif, italic, blackletter; heavy = drawn with more strokes"),
                     Param.number("x", label="X", min=-10**6, max=10**6, default=0,
                                  help="Where the first line's baseline starts (composition px; its middle or end with align)"),
                     Param.number("y", label="Y", min=-10**6, max=10**6, default=0, help="The first line's baseline (composition px)"),
                     Param.number("height", label="Letter height", min=1, max=10000, default=120,
                                  help="Capital height, composition px. Brush `size` is separate: about 6-12 % of it reads as a pen, 15-25 % as a loaded brush"),
                     Param.choice("align", list(lettering.ALIGN), label="Align", default="left", importance="secondary",
                                  help="Each line from x (left), around x (center) or ending at x (right); on a path, from `start`"),
                     Param.number("tracking", label="Letter spacing", min=-1000, max=1000, default=0, importance="secondary",
                                  help="Extra px between letters (negative: closer; script letters overlap and join)"),
                     Param.number("line", label="Line height", min=0.5, max=5, default=1.6, importance="secondary",
                                  help="Baseline to baseline, × the letter height"),
                     Param.number("slant", label="Slant", min=-45, max=45, default=0, importance="secondary",
                                  help="Degrees the letters lean right (negative: left)"),
                     Param.number("hand", label="Unsteady hand", min=0, max=1, default=0, importance="secondary",
                                  help="0 = the font's own lines; up to 1 each letter is a little moved, turned and sized "
                                       "and the line drifts, like a person writing. Brush `wobble` shakes the line itself"),
                     Param.number("hand_seed", label="Hand seed", min=0, max=10**6, integer=True, default=0, importance="deep",
                                  help="Another seed, another hand with the same unsteadiness"),
                     Param.text("path", label="On a curve", default="", importance="secondary", shown="script",
                                help="SVG path data in composition px the baseline follows (a path layer's d moved to where it "
                                     "shows); empty = a straight baseline at x, y. Past the path's ends the letters carry on straight"),
                     Param.number("start", label="Start along curve", min=-10**6, max=10**6, default=0, importance="deep",
                                  help="With path: px along it where the words start (where their middle sits with align center)"),
                     Param.text("layer", label="Paint layer", default="", importance="secondary",
                                help='"new" = a new paint layer for the words (handy to write them on alone); empty = the top unlocked one'),
                     Param.number("frame", label="Frame", min=0, max=10**7, integer=True, importance="secondary",
                                  help="Which frame's drawing, and the time the composition px are placed at. Default 0"),
                     *rostrum_paint.BRUSH])
def paint_letters(ctx, targets, args):
    try:
        lines = lettering.strokes(args["text"], font_name=args.get("font", "script"), size=float(args.get("height", 120)),
                                  x=float(args.get("x", 0)), y=float(args.get("y", 0)), align=args.get("align", "left"),
                                  spacing=float(args.get("tracking", 0)), line=float(args.get("line", 1.6)),
                                  slant=float(args.get("slant", 0)), hand=float(args.get("hand", 0)),
                                  seed=int(args.get("hand_seed", 0)), path=args.get("path", ""), start=float(args.get("start", 0)))
    except ValueError as e:
        ctx.fail(codes.BAD_ARGUMENT, "paint.letters", str(e))
    stroke = {k: v for k, v in args.items() if k not in _OWN}
    layer = stroke.get("layer", "")
    for i, pts in enumerate(lines):
        # A new paint layer is made by the first stroke; the rest go on it, the top one now.
        ops_paint.paint_stroke(ctx, targets, {**stroke, "points": pts, "space": "comp",
                                              "layer": "" if layer == "new" and i else layer})
