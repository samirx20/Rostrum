"""A flat colour at once for paint that is changed but not yet drawn exactly: a Fill, a paste of strokes. The exact
picture (every stroke stamped, the layers put together, the file written) takes 1 to 3 s on a full-size drawing, so
this draws the new fills and strokes the quick way (QPainter: a plain colour, no brush texture) over the canvas, in
composition px, at the same moment the change is made. wet.py shows it (WetView.flat) and takes it away when the real
frame lands, as it does for a stroke's wet ink. No Qt Quick; a QImage only.
"""
from __future__ import annotations

import math

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor, QImage, QPainter, QPainterPath, QPen, QPolygonF
from rostrum2d import placement
from rostrum2d.evaluate import resolve


def new_items(before: dict | None, after: dict | None) -> list[dict]:
    """The strokes and fills a drawing has now that it did not have (frames as `_frame()` gives them)."""
    seen = {s["id"] for p in (before["paints"] if before else []) for s in p["strokes"]}
    return [s for p in (after["paints"] if after else []) if p.get("visible", True)
            for s in p["strokes"] if s["id"] not in seen]


def draw(items: list[dict], item: dict, props: dict, place: dict, comp_size: tuple[int, int]):
    """(QImage, box) of the items drawn flat, or None when nothing is to show. `items`: strokes / fills of the layer
    `item` (canvas px points); `place`: the layer's place (placement.py); box: {x, y, w, h} in composition px."""
    k = _scale(item, props, place)
    shapes = []
    for s in items:
        if s.get("mode") == "erase":
            continue                                    # an eraser takes paint away: nothing flat can show that
        pts = placement.comp_points(item, props, place, s["points"])
        shapes.append((s, pts, s.get("size", 0) * k))
    xs = [q[0] for _, pts, _ in shapes for q in pts]
    ys = [q[1] for _, pts, _ in shapes for q in pts]
    if not xs:
        return None
    pad = max((w for _, _, w in shapes), default=0) / 2 + 2
    x0, y0 = max(0, math.floor(min(xs) - pad)), max(0, math.floor(min(ys) - pad))
    x1, y1 = min(comp_size[0], math.ceil(max(xs) + pad)), min(comp_size[1], math.ceil(max(ys) + pad))
    if x1 <= x0 or y1 <= y0:
        return None
    img = QImage(x1 - x0, y1 - y0, QImage.Format.Format_ARGB32_Premultiplied)
    img.fill(0)
    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.translate(-x0, -y0)
    for s, pts, width in shapes:
        colour = QColor(s["color"])
        p.setOpacity(float(s.get("opacity", 1.0)))
        (_fill if s["type"] == "fill" else _line)(p, pts, colour, width)
    p.end()
    return img, {"x": x0, "y": y0, "w": x1 - x0, "h": y1 - y0}


def _scale(item, props, place) -> float:
    """Composition px per canvas px about the layer's middle."""
    a, b = placement.comp_points(item, props, place, [[0.0, 0.0], [10.0, 0.0]])
    return math.hypot(b[0] - a[0], b[1] - a[1]) / 10.0 or 1.0


def _fill(p: QPainter, pts, colour: QColor, _width):
    """The outline's rings (point[2] = the ring) as one shape, holes cut out."""
    rings: dict[int, list] = {}
    for q in pts:
        rings.setdefault(int(q[2]) if len(q) > 2 else 0, []).append(QPointF(q[0], q[1]))
    path = QPainterPath()
    path.setFillRule(Qt.FillRule.OddEvenFill)
    for ring in rings.values():
        path.addPolygon(QPolygonF(ring))
        path.closeSubpath()
    p.fillPath(path, colour)


def _line(p: QPainter, pts, colour: QColor, width: float):
    pen = QPen(colour, max(1.0, width), Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
    p.setPen(pen)
    if len(pts) == 1:
        p.drawPoint(QPointF(pts[0][0], pts[0][1]))
    else:
        p.drawPolyline(QPolygonF([QPointF(q[0], q[1]) for q in pts]))


def for_layer(bridge, layer_id: str, items: list[dict], place: dict):
    """draw() for the layer `layer_id` of the bridge's document, as it is now."""
    item = bridge.doc.item(layer_id)
    c = bridge.comp()
    return draw(items, item, resolve(item, bridge.own_t(layer_id)), place, (c["width"], c["height"]))
