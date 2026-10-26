"""`text.counter`: make texts count, in one change (one undo step). Turns Counts a number on (fields.py COUNTER), writes
the format given (decimals, thousands mark, the words before and after) and replaces the Number's keys with two: `from`
at `at`, `to` at `at + duration`, the first with `ease`. The engine writes the number per frame (scene/counter.rs), so
the canvas, the look tools and the export show the same digits. More steps: key `count` like any number (key.add).
Stop counting: value.set counter off (the text shows its words again)."""
from __future__ import annotations

from rostrum_core import Param
from rostrum_core.keys import keys_of
from rostrum_core.keys.easing import NAMES as EASES

from . import fields as F
from .kind import REGISTRY as R
from .ops_keys import put_key

FORMAT = {"decimals": "countDecimals", "digits": "countDigits", "separator": "countSeparator", "prefix": "countPrefix", "suffix": "countSuffix"}


@R.operation("text.counter", "Make a text count a number: from `from` at `at` to `to` at `at + duration` with `ease`, "
             "written with `decimals` places, at least `digits` digits (zeros in front) and the `separator` thousands mark (comma 1,284.5; period 1.284,5; space "
             "1 284.5; none), between `prefix` and `suffix` (e.g. \"$\", \" GWh\"). One change; the text's words are not "
             "shown while it counts. Format fields left out stay as they are. More steps: key.add on `count`; tabular "
             "figures (figures, only on a font that has them, e.g. Inter) keep the width steady.", target="text", label="Count a number", importance="secondary",
             params=[Param.number("from", label="From", required=True), Param.number("to", label="To", required=True),
                     Param.number("at", label="Starts at", min=0, max=36000, unit=" s", default=0.0),
                     Param.number("duration", label="Takes", min=0.001, max=36000, unit=" s", default=1.0),
                     Param.choice("ease", EASES, label="Ease", default="smooth"),
                     Param.number("decimals", label="Decimals", min=0, max=6, integer=True),
                     Param.number("digits", label="Least digits", min=1, max=15, integer=True,
                                  help="Zeros in front up to this many digits (3: 007)"),
                     Param.choice("separator", F.SEPARATORS, label="Thousands"),
                     Param.text("prefix", label="Before"), Param.text("suffix", label="After")])
def text_counter(ctx, targets, args):
    at, end = args.get("at", 0.0), args.get("at", 0.0) + args.get("duration", 1.0)
    for t in targets:
        ctx.set(t, "counter", True)
        for arg, field in FORMAT.items():
            if arg in args:
                ctx.set(t, field, F.param("text", field).check(args[arg], f"{ctx.where} › {t}.{field}"))
        for k in keys_of(ctx.item(t), "count"):
            ctx.remove(k["id"])
        put_key(ctx, t, "count", at, {"v": args["from"], "ease": args.get("ease", "smooth")})
        put_key(ctx, t, "count", end, {"v": args["to"]})
