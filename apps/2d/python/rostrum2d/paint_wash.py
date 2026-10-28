"""A wash laid to the edges: `paint.wash` (and a script's `paint.wash(...)`) covers a region of a paint layer, or the
whole canvas, with the brush going back and forth across it, so no strip is left bare by a stroke that stopped short.

    plan(region, w, h, values) -> (the paint mask's values or None, [each stroke's values])

How it is laid (all ordinary kit items, so it replays, undoes and draws on with drawnSoFar like hand-made strokes):
- **Passes**: rows `size × overlap` apart (left out: as far as the hardness allows with no paler seam, `auto_spacing`) (across) or columns (down), each running a full brush size past the region on
  both sides; the turns lie outside it. A flat wash is one stroke, its rows joined, so its wet edge (Edge darkening)
  forms only where the wash ends, never between rows. A graded wash (`to`) is `bands` strokes, the colour going from
  `color` to `to` band by band, each band overlapping the next by half a row.
- **The edge**: one paint mask the strokes paint inside: the region's outline pushed out by up to `bleed` px, in an
  uneven, smooth way (paint running into damp paper), then blurred `edge` px (the paint mask's Feather); for the whole
  canvas, the canvas's own outline. The passes running past it never grow the drawing (paint_grow: a masked mark
  reaches no further than its mask).
Every brush setting (brush, hardness, opacity, granulation, edge_darken, paper, wobble …) goes to each stroke as given;
left out, the drying is a watercolour's (`WATER`: a dried edge, granulation, pooling, the paper's tooth showing) and a
box / outline's edge wanders (`bleed` from the size), each turned off by 0.
"""
from __future__ import annotations

import math

import rostrum_paint
from rostrum_core import Param
from rostrum_core.errors import codes
from rostrum_core.tree import index
from rostrum_paint.ops import build, canvas_of

from .kind import REGISTRY as R

SAMPLE = 12             # px between the outline's points once it is roughened
# A wash's drying, left out: a watercolour's, strong enough to read in a 1920x1080 frame seen small (at 0.4 / 0.3 / 0.5
# and no grain the rim, puddles and speckle averaged away below ~480 px wide and a wash read as a flat fill).
WATER = {"edge_darken": 0.85, "granulation": 0.7, "pooling": 0.9, "grain": 0.3}
BLEED_SHARE, BLEED_MAX = 0.2, 30    # a box / outline's edge, left out, wanders up to this share of the size (≤ this px)


def _box(points) -> tuple[float, float, float, float]:
    xs, ys = [p[0] for p in points], [p[1] for p in points]
    return min(xs), min(ys), max(xs), max(ys)


def outline(region, w: int, h: int) -> list[list[float]] | None:
    """The region as a polygon in canvas px; None for the whole canvas."""
    if region in (None, "whole"):
        return None
    if isinstance(region, (list, tuple)) and len(region) == 4 and all(isinstance(v, (int, float)) for v in region):
        x0, y0, x1, y1 = region
        if x1 <= x0 or y1 <= y0:
            raise ValueError(f"region box {list(region)} is empty: give [x0, y0, x1, y1] with x1 > x0 and y1 > y0")
        return [[x0, y0], [x1, y0], [x1, y1], [x0, y1]]
    if isinstance(region, (list, tuple)) and len(region) >= 3 and all(len(p) >= 2 for p in region):
        return [[float(p[0]), float(p[1])] for p in region]
    raise ValueError('the region is the whole canvas, a box [x0, y0, x1, y1] or an outline [[x, y], …] (3 points or more), in canvas px')


def _noise(t: float, seed: int) -> float:
    """Smooth, 0..1, from a few sines with phases from the seed (the same edge every run): long swells plus a ripple a
    few tens of px across, so the edge wanders at a small scale too (a long-wave-only edge reads as a bent ruler)."""
    r = [((seed * 2654435761 + k * 40503) % 1000) / 1000 for k in range(5)]
    v = (math.sin(t * 1.0 + 6.28 * r[0]) + 0.6 * math.sin(t * 2.3 + 6.28 * r[1]) + 0.35 * math.sin(t * 5.1 + 6.28 * r[2])
         + 0.3 * math.sin(t * 11.3 + 6.28 * r[3]) + 0.2 * math.sin(t * 23.7 + 6.28 * r[4]))
    return (v / 2.45 + 1) / 2


def bled(poly: list, bleed: float, seed: int) -> list:
    """The outline pushed outward (away from its middle) by 0..bleed px, unevenly; unchanged at bleed 0."""
    if bleed <= 0:
        return poly
    cx, cy = sum(p[0] for p in poly) / len(poly), sum(p[1] for p in poly) / len(poly)
    out, run = [], 0.0
    for a, b in zip(poly, poly[1:] + poly[:1]):
        n = max(1, int(math.hypot(b[0] - a[0], b[1] - a[1]) // SAMPLE))
        for i in range(n):
            x, y = a[0] + (b[0] - a[0]) * i / n, a[1] + (b[1] - a[1]) * i / n
            d = math.hypot(x - cx, y - cy) or 1.0
            push = bleed * _noise(run / 90.0, seed)
            out.append([round(x + (x - cx) / d * push, 1), round(y + (y - cy) / d * push, 1)])
            run += SAMPLE
    return out


def _mix(a: str, b: str, t: float) -> str:
    ca, cb = (tuple(int(c[i:i + 2], 16) for i in (1, 3, 5)) for c in (a, b))
    return "#" + "".join(f"{round(x + (y - x) * t):02x}" for x, y in zip(ca, cb))


def _passes(x0, y0, x1, y1, size, gap, down) -> list[list[float]]:
    """Back and forth over the box: rows (or columns) `gap` apart, each a size past both sides."""
    if down:
        return [[p[1], p[0]] for p in _passes(y0, x0, y1, x1, size, gap, False)]
    rows = max(1, math.ceil((y1 - y0) / gap)) + 1
    top = (y0 + y1) / 2 - (rows - 1) * gap / 2
    pts = []
    for i in range(rows):
        y = top + i * gap
        ends = (x0 - size, x1 + size) if i % 2 == 0 else (x1 + size, x0 - size)
        pts += [[round(ends[0], 1), round(y, 1)], [round(ends[1], 1), round(y, 1)]]
    return pts


def auto_spacing(hardness: float) -> float:
    """Rows this many sizes apart lay an even wash: a stroke's paint is as strong as its strongest dab, so the rows must
    meet where each is still solid; a soft tip is solid only near its middle (measured: no dip over 2 % at any hardness)."""
    return min(0.5, 0.1 + 0.6 * float(hardness))


def plan(region, w: int, h: int, values: dict) -> tuple[dict | None, list[dict]]:
    v = dict(values)
    poly = outline(region, w, h)
    to, down = v.pop("to", None), v.pop("direction", "across") == "down"
    bands = int(v.pop("bands", 10)) if to else 1
    overlap, bleed, edge = v.pop("overlap", None), v.pop("bleed", None), float(v.pop("edge", 0.0))
    if overlap is not None and not 0.05 <= overlap <= 1:
        raise ValueError(f"overlap {overlap}: rows are size × overlap apart, 0.05 .. 1 (left out: from the hardness)")
    x0, y0, x1, y1 = _box(poly) if poly else (0, 0, w, h)
    if bleed is None:               # left out: the edge wanders a little, as a brushed edge does (0 = the region's own)
        across = (x1 - x0) if down else (y1 - y0)
        bleed = min(BLEED_MAX, BLEED_SHARE * float(v.get("size") or max(24.0, min(400.0, across / 5)))) if poly else 0.0
    bleed = float(bleed)
    if poly:
        x0, y0, x1, y1 = x0 - bleed, y0 - bleed, x1 + bleed, y1 + bleed
    size = float(v.setdefault("size", round(max(24.0, min(400.0, ((x1 - x0) if down else (y1 - y0)) / 5)), 1)))
    v.setdefault("brush", "round")
    v.setdefault("color_jitter", 0.0)
    v.setdefault("hardness", 0.3)
    for k, d in WATER.items():      # a wash dries like one unless told otherwise (0 turns each off)
        v.setdefault(k, d)
    gap = size * (overlap if overlap is not None else auto_spacing(v["hardness"]))
    seed = int(v.get("seed", 7))
    edge_pts = [[min(w, max(0, x)), min(h, max(0, y))] for x, y in bled(poly, bleed, seed)] if poly else None
    mask = {"points": edge_pts or [[0, 0], [w, 0], [w, h], [0, h]], "feather": edge}   # kept on the canvas: a side on
    #                                                     its edge stays solid there (the feather doesn't fade it)
    lo, hi = (x0, x1) if down else (y0, y1)
    strokes = []
    for k in range(bands):
        a = lo + (hi - lo) * k / bands - (gap / 2 if k else 0)
        b = lo + (hi - lo) * (k + 1) / bands + (gap / 2 if k < bands - 1 else 0)
        box = (a, y0, b, y1) if down else (x0, a, x1, b)
        col = _mix(v["color"], to, k / max(1, bands - 1)) if to else v.get("color")
        strokes.append({**v, **({"color": col} if col else {}), "points": _passes(*box, size, gap, down)})
    return mask, strokes


REGION = [Param.list("box", "number", label="Box", min_items=4, max_items=4,
                     help="[x0, y0, x1, y1] canvas px: wash this box. Neither box nor outline = the whole canvas"),
          Param.points("outline", label="Outline", min=2, max=2,
                       help="[[x, y], …] canvas px (3 points or more): wash inside this polygon instead of a box")]
PARAMS = [Param.text("id", label="Id", importance="deep", help="Optional: the strokes are <id>, <id>_2 …, the mask <id>_edge"),
          Param.color("to", label="Graded to", help="A graded wash: from Colour (top / left) to this colour (bottom / right)"),
          Param.number("bands", label="Bands", min=2, max=40, integer=True, default=10, help="How many steps a graded wash has (more = a smoother grade)"),
          Param.choice("direction", ["across", "down"], label="Passes", default="across",
                       help="across: the brush goes left–right, rows down the region; down: up–down, columns across"),
          Param.number("overlap", label="Row spacing", min=0.05, max=1, step=0.05, unit="× size",
                       help="Rows this many brush sizes apart. Left out: as far apart as the hardness allows with no "
                            "paler lines between rows (0.16 at hardness 0.1, 0.28 at 0.3, 0.5 from 0.67); wider = "
                            "visible rows (a streaky, laid-in-strokes wash)"),
          Param.number("bleed", label="Bleed", min=0, max=500, unit="px",
                       help="The edge runs out unevenly past the region by up to this much (paint creeping into damp "
                            "paper). Left out: a fifth of the size, at most 30 px; 0 = the region's own straight edge"),
          Param.number("edge", label="Edge softness", min=0, max=500, default=0, unit="px",
                       help="The edge blurred this wide (the paint mask's Feather); 0 = as crisp as the brush")]


@R.operation("paint.wash", "Lay a wash over a region of a paint layer, or the whole canvas, to its edges: the brush goes "
             "back and forth past every side, so nothing is left bare; an edge that is soft (edge), runs unevenly "
             "(bleed) or neither; flat (one stroke) or graded (to, bands). Makes ordinary strokes and one paint mask "
             "(<id>_edge), one undo step; drawnSoFar paints them on pass by pass. Every "
             "brush setting applies (granulation, edge_darken, pooling, bloom, grain, paper, wobble …); left out, it dries like "
             "watercolour strongly enough to read in a frame seen small (edge_darken 0.85, granulation 0.7, pooling "
             "0.9, grain 0.3, and a box / outline's edge wanders by bleed = a fifth of the size, at most 30 px); 0 turns "
             "any one off; size defaults to a fifth of the region.",
             target="paint", label="Wash", importance="secondary",
             params=[*REGION, *PARAMS, *(p for p in rostrum_paint.BRUSH)])
def paint_wash(ctx, targets, args):
    from .drawing import canvas_size
    for t in targets:
        frame = canvas_of(ctx.doc, ctx.kind.lists, t)
        idx = index(ctx.doc, ctx.kind.lists)
        holder = idx[idx[frame["id"]].parent].item
        w, h = canvas_size(holder)
        lay(ctx, t, frame, w, h, args)


def lay(ctx, paint_id, frame, w, h, args):
    values = {k: v for k, v in args.items() if v is not None}
    base = values.pop("id", None) or ctx.new_id("wash")
    region = values.pop("outline", None) or values.pop("box", None) or "whole"
    values.pop("box", None)
    try:
        mask, strokes = plan(region, w, h, values)
    except ValueError as e:
        ctx.fail(codes.BAD_ARGUMENT, 'the wash', f"can't be laid: {e}")
    if mask:
        ctx.insert(frame["id"], "paintmasks", build("paintmask", f"{base}_edge", mask, ctx.where))
    for i, s in enumerate(strokes):
        ctx.insert(paint_id, "strokes", build("stroke", base if not i else f"{base}_{i + 1}",
                                              {**s, **({"mask": f"{base}_edge"} if mask else {})}, ctx.where))
