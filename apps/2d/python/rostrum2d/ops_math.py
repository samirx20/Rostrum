"""`math.add`: typeset a formula (LaTeX-style) as a group of path layers, one per symbol and rule (mathtype.py). The same
layers a script's `math_text(…)` makes: ordinary paths a person or agent animates, colours or moves."""
from __future__ import annotations

from rostrum_core import Param
from rostrum_core.errors import codes

from . import mathtype, pathdata as PD
from .kind import REGISTRY as R
from .ops_items import ID, new_item


@R.operation("math.add", "Typeset a formula as vector paths: a group of one path layer per symbol and rule (fraction bars and root "
             "signs included), ids `<id>_<n>_<symbol>` in reading order (eq_3_equal, eq_9_sum). `tex` is LaTeX-style: "
             r"\frac{a}{b}, \sqrt{x}, \sum_{k=1}^{n}, \pi, \int, x^2, x_i, \pm, \infty, \sin. `x`, `y` place its top-left in the "
             "scene's px; `size` is the font size in px; `color` fills every symbol. Reveal term by term by keying each "
             "path's opacity; write on with stroke + trimEnd; colour or move a term by editing its paths.",
             target=("comp", "group"), label="Add equation",
             params=[Param.text("tex", label="Formula", required=True, help=r"LaTeX-style, e.g. \frac{1}{2}mv^2"), ID,
                     Param.number("x", label="Left", min=-100000, max=100000, default=0.0, unit=" px"),
                     Param.number("y", label="Top", min=-100000, max=100000, default=0.0, unit=" px"),
                     Param.number("size", label="Size", min=4, max=4000, default=64.0, unit=" px"),
                     Param.color("color", label="Colour", default="#ffffff")])
def math_add(ctx, targets, args):
    try:
        parts = mathtype.math_parts(args["tex"], args.get("size", 64.0))
    except ValueError as e:
        ctx.fail(codes.BAD_ARGUMENT, '"tex"', str(e).removeprefix("math_text: "), hint="Fix the formula and run it again.")
    w, h = mathtype.bounds(parts)
    for t in targets:
        group = new_item(ctx, "group", {"id": args.get("id") if len(targets) == 1 else None},
                         w=w, h=h, x=args.get("x", 0.0) + w / 2, y=args.get("y", 0.0) + h / 2)
        ctx.insert(t, "layers", group)
        for n, (what, d) in enumerate(parts, 1):
            cmds, (x0, y0, pw, ph) = PD.fit(PD.commands(d))
            path = new_item(ctx, "path", {"id": f"{group['id']}_{n}_{what}"}, d=PD.write(cmds), w=pw, h=ph,
                            x=x0 + pw / 2, y=y0 + ph / 2, filled=True, fill=args.get("color", "#ffffff"), stroke=False)
            ctx.insert(group["id"], "layers", path)
