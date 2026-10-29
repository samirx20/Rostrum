"""Where a block (a card, a group, a panel) really draws, for review's layout checks and their fixes: its own paint and
every showing layer inside it, at the size the layout gives (the render's size: a card whose words outgrow the h its
script wrote draws past that h), and the y that puts one block under another, in the px its script types (its
parent's px, before the camera: a layer's x / y are never picture px)."""
from __future__ import annotations

from rostrum2d import boxes

from .geometry import _apply, _invert, _mul, drawn_box

SHOWS = 0.1               # opacity from which a layer draws something (review_sample.SEEN)


def shows(n: dict) -> bool:
    """It draws something now, wherever it is (in or out of the picture): in its time, not nearly clear, not only a
    matte, painting itself (a plain group paints nothing of its own)."""
    return (n["in_time"] and n["opacity"] >= SHOWS and not n["matte_for"] and n["type"] != "rig"
            and not (n["type"] == "group" and not n["paint"]))


def extent(nodes: list[dict], bid: str) -> tuple | None:
    """The picture box (x0, y0, x1, y1) block `bid` draws in: its own paint and every showing layer inside it; None
    when nothing of it shows."""
    got = [drawn_box(n) for n in nodes if (n["id"] == bid or bid in n["within"]) and shows(n)]
    if not got:
        return None
    return min(b[0] for b in got), min(b[1] for b in got), max(b[2] for b in got), max(b[3] for b in got)


def parent_px(n: dict, x: float, y: float) -> tuple[float, float]:
    """A picture point in the px of n's parent (a group's own px, or the composition's before the camera): the space n's
    x / y are typed in."""
    own = _invert(boxes.matrix(n["props"], *n["size"]))
    inv = _invert(_mul(n["matrix"], own)) if own else None
    return _apply(inv, x, y) if inv else (x, y)


def below(nodes: list[dict], a: str, b: str, axis: str = "y") -> str:
    """'<upper> ends at y = … (<lower> starts at y = …)' for two sibling blocks (axis "x": left / right), the numbers in
    the lower one's parent px from where the other really ends (its drawn extent, not its written h): a measurement."""
    by = {n["id"]: n for n in nodes}
    ea, eb = extent(nodes, a), extent(nodes, b)
    if not ea or not eb or a not in by or b not in by:
        return f'"{b}" and "{a}" overlap'
    k = 0 if axis == "x" else 1
    (first, ef), (second, es) = sorted(((a, ea), (b, eb)), key=lambda r: r[1][k])
    n = by[second]
    end = parent_px(n, *((ef[2], es[1]) if k == 0 else (es[0], ef[3])))[k]
    start = parent_px(n, es[0], es[1])[k]
    at = float(n["props"].get(axis, 0.0))
    where = f'"{n["within"][-1]}" px' if n["within"] else "the composition's px"
    return (f'"{first}" ends at {axis} = {end:.0f} in {where}, {end - start:.0f} px past where "{second}" starts '
            f'("{second}" {axis} = {at:.0f})')
