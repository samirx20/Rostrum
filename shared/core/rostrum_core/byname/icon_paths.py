"""An icon as plain path data, for apps that draw paths rather than SVG (the classic 2D script's icon(), 3D's shapes):
every element (path, line, polyline, polygon, circle, ellipse, rect with round corners) as SVG `d` in the icon's
24×24 box, with whether it is filled and/or stroked (the icon's own attributes, inherited from <svg> as SVG does).
An element neither filled nor stroked (Tabler's invisible 24×24 frame) is left out."""
from __future__ import annotations

import xml.etree.ElementTree as ET

from .icons import icon

NS = "{http://www.w3.org/2000/svg}"


def _f(e, k: str, default: float = 0.0) -> float:
    return float(e.get(k, default))


def _arc_d(cx: float, cy: float, rx: float, ry: float) -> str:
    return (f"M{cx - rx:g} {cy:g}A{rx:g} {ry:g} 0 1 0 {cx + rx:g} {cy:g}"
            f"A{rx:g} {ry:g} 0 1 0 {cx - rx:g} {cy:g}Z")


def _rect_d(e) -> str:
    x, y, w, h = _f(e, "x"), _f(e, "y"), _f(e, "width"), _f(e, "height")
    rx = _f(e, "rx", _f(e, "ry"))
    ry = _f(e, "ry", rx)
    rx, ry = min(rx, w / 2), min(ry, h / 2)
    if not rx:
        return f"M{x:g} {y:g}H{x + w:g}V{y + h:g}H{x:g}Z"
    a = lambda dx, dy: f"A{rx:g} {ry:g} 0 0 1 {dx:g} {dy:g}"
    return (f"M{x + rx:g} {y:g}H{x + w - rx:g}{a(x + w, y + ry)}V{y + h - ry:g}{a(x + w - rx, y + h)}"
            f"H{x + rx:g}{a(x, y + h - ry)}V{y + ry:g}{a(x + rx, y)}Z")


def _d(e) -> str | None:
    tag = e.tag.replace(NS, "")
    if tag == "path":
        return e.get("d")
    if tag == "line":
        return f'M{_f(e, "x1"):g} {_f(e, "y1"):g}L{_f(e, "x2"):g} {_f(e, "y2"):g}'
    if tag in ("polyline", "polygon"):
        nums = e.get("points", "").replace(",", " ").split()
        pts = [f"{nums[i]} {nums[i + 1]}" for i in range(0, len(nums) - 1, 2)]
        return ("M" + "L".join(pts) + ("Z" if tag == "polygon" else "")) if pts else None
    if tag == "circle":
        return _arc_d(_f(e, "cx"), _f(e, "cy"), _f(e, "r"), _f(e, "r"))
    if tag == "ellipse":
        return _arc_d(_f(e, "cx"), _f(e, "cy"), _f(e, "rx"), _f(e, "ry"))
    if tag == "rect":
        return _rect_d(e)
    return None


def icon_paths(name: str) -> list[dict]:
    """[{"d", "fill": bool, "stroke": bool, "stroke_width": float}] in the icon's 24×24 box, back to front."""
    root = ET.fromstring(icon(name))
    out = []

    def walk(node, fill: str, stroke: str, width: str):
        for e in node:
            f, s, w = e.get("fill", fill), e.get("stroke", stroke), e.get("stroke-width", width)
            if e.tag.replace(NS, "") == "g":
                walk(e, f, s, w)
                continue
            d = _d(e)
            if d and (f != "none" or s != "none"):
                out.append({"d": d, "fill": f != "none", "stroke": s != "none", "stroke_width": float(w)})

    walk(root, root.get("fill", "black"), root.get("stroke", "none"), root.get("stroke-width", "1"))
    return out
