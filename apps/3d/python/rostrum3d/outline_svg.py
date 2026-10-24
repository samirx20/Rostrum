"""Drawings as outlines: an SVG file or path data text, or a path layer of a 2D document. Filled shapes only (path, rect,
circle, ellipse, polygon, polyline); strokes, images, gradients and `use` are ignored, `fill="none"` shapes are skipped,
`fill-rule` and group transforms are followed. All shapes are merged into one outline. The drawing is scaled so its
ink is `svgWidth` metres wide and centred on its middle; SVG y points down, the outline's y up.
"""
from __future__ import annotations

import json
import math
import re
import xml.etree.ElementTree as ET
from pathlib import Path

import pathops
from fontTools.misc.transform import Identity, Transform
from fontTools.pens.transformPen import TransformPen

from . import outline as O

_NUM = re.compile(r"[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?")
_ARGS = dict(M=2, L=2, H=1, V=1, C=6, S=4, Q=4, T=2, A=7, Z=0)
_SKIP = {"defs", "clipPath", "mask", "symbol", "pattern", "marker", "metadata", "title", "desc", "style"}


class _Reader:
    def __init__(self, d: str):
        self.d, self.i = d, 0

    def _ws(self):
        while self.i < len(self.d) and self.d[self.i] in " \t\r\n,":
            self.i += 1

    def letter(self):
        self._ws()
        if self.i < len(self.d) and self.d[self.i].isalpha():
            self.i += 1
            return self.d[self.i - 1]

    def more(self) -> bool:
        self._ws()
        return self.i < len(self.d)

    def number(self) -> float:
        self._ws()
        m = _NUM.match(self.d, self.i)
        if not m:
            raise ValueError(f"path data: a number was expected at character {self.i}: …{self.d[self.i:self.i + 12]!r}")
        self.i = m.end()
        return float(m.group())

    def flag(self) -> float:
        self._ws()
        if self.d[self.i:self.i + 1] not in ("0", "1"):
            raise ValueError(f"path data: an arc flag (0 or 1) was expected at character {self.i}")
        self.i += 1
        return float(self.d[self.i - 1])


def _arc(pen, p0, rx, ry, rot, large, sweep, p1):
    """An SVG elliptical arc as cubic curves (endpoint → centre form, W3C SVG 1.1 appendix F.6)."""
    if p0 == p1:
        return
    rx, ry = abs(rx), abs(ry)
    if not rx or not ry:
        pen.lineTo(p1)
        return
    phi = math.radians(rot)
    c, s = math.cos(phi), math.sin(phi)
    dx, dy = (p0[0] - p1[0]) / 2, (p0[1] - p1[1]) / 2
    x1, y1 = c * dx + s * dy, -s * dx + c * dy
    lam = x1 * x1 / (rx * rx) + y1 * y1 / (ry * ry)
    if lam > 1:
        rx, ry = rx * math.sqrt(lam), ry * math.sqrt(lam)
    num = rx * rx * ry * ry - rx * rx * y1 * y1 - ry * ry * x1 * x1
    co = math.sqrt(max(0.0, num / (rx * rx * y1 * y1 + ry * ry * x1 * x1))) * (-1 if large == sweep else 1)
    cxp, cyp = co * rx * y1 / ry, -co * ry * x1 / rx
    cx, cy = c * cxp - s * cyp + (p0[0] + p1[0]) / 2, s * cxp + c * cyp + (p0[1] + p1[1]) / 2
    ang = lambda ux, uy, vx, vy: math.atan2(ux * vy - uy * vx, ux * vx + uy * vy)  # noqa: E731
    t1 = ang(1, 0, (x1 - cxp) / rx, (y1 - cyp) / ry)
    dt = ang((x1 - cxp) / rx, (y1 - cyp) / ry, (-x1 - cxp) / rx, (-y1 - cyp) / ry)
    dt = dt - 2 * math.pi if not sweep and dt > 0 else dt + 2 * math.pi if sweep and dt < 0 else dt
    n = max(1, math.ceil(abs(dt) / (math.pi / 2) - 1e-9))
    step, k = dt / n, 4 / 3 * math.tan(dt / n / 4)
    def at(a, d=0.0):
        u, v = math.cos(a) - d * math.sin(a), math.sin(a) + d * math.cos(a)
        return (cx + rx * u * c - ry * v * s, cy + rx * u * s + ry * v * c)
    for i in range(n):
        a0, a1 = t1 + i * step, t1 + (i + 1) * step
        pen.curveTo(at(a0, k), at(a1, -k), at(a1) if i < n - 1 else p1)


def draw_d(d: str, pen):
    """SVG path data (every command, relative or absolute) into a pen; each subpath is closed."""
    r, cmd, cur, start, prev, open_ = _Reader(d), None, (0.0, 0.0), (0.0, 0.0), None, False
    while r.more():
        c = r.letter()
        if c:
            cmd = c
        elif cmd is None or cmd.upper() == "Z":
            raise ValueError(f"path data: a command letter was expected at character {r.i}")
        up, rel = cmd.upper(), cmd.islower()
        if up not in _ARGS:
            raise ValueError(f'path data: unknown command "{cmd}" (accepted: M L H V C S Q T A Z)')
        if up == "Z":
            if open_:
                pen.closePath()
            cur, open_, prev, cmd = start, False, None, "Z"
            continue
        a = [r.flag() if up == "A" and k in (3, 4) else r.number() for k in range(_ARGS[up])]
        ox, oy = cur if rel else (0.0, 0.0)
        if up == "M":
            if open_:
                pen.closePath()
            cur = start = (a[0] + ox, a[1] + oy)
            pen.moveTo(cur)
            open_, prev, cmd = True, None, "l" if rel else "L"
            continue
        if not open_:
            pen.moveTo(cur)
            open_ = True
        if up == "L":
            cur = (a[0] + ox, a[1] + oy)
            pen.lineTo(cur)
            prev = None
        elif up == "H":
            cur = (a[0] + ox, cur[1])
            pen.lineTo(cur)
            prev = None
        elif up == "V":
            cur = (cur[0], a[0] + oy)
            pen.lineTo(cur)
            prev = None
        elif up in "CS":
            if up == "C":
                p1, p2, p3 = (a[0] + ox, a[1] + oy), (a[2] + ox, a[3] + oy), (a[4] + ox, a[5] + oy)
            else:
                p1 = (2 * cur[0] - prev[0], 2 * cur[1] - prev[1]) if prev and prev[2] == "c" else cur
                p2, p3 = (a[0] + ox, a[1] + oy), (a[2] + ox, a[3] + oy)
            pen.curveTo(p1, p2, p3)
            prev, cur = (*p2, "c"), p3
        elif up in "QT":
            if up == "Q":
                p1, p2 = (a[0] + ox, a[1] + oy), (a[2] + ox, a[3] + oy)
            else:
                p1 = (2 * cur[0] - prev[0], 2 * cur[1] - prev[1]) if prev and prev[2] == "q" else cur
                p2 = (a[0] + ox, a[1] + oy)
            pen.qCurveTo(p1, p2)
            prev, cur = (*p1, "q"), p2
        else:
            end = (a[5] + ox, a[6] + oy)
            _arc(pen, cur, a[0], a[1], a[2], a[3], a[4], end)
            cur, prev = end, None
    if open_:
        pen.closePath()


def _transform(text: str) -> Transform:
    t = Identity
    for name, args in re.findall(r"(\w+)\s*\(([^)]*)\)", text or ""):
        v = [float(x) for x in _NUM.findall(args)]
        step = {"matrix": lambda: Transform(*v[:6]), "translate": lambda: Transform().translate(v[0], v[1] if len(v) > 1 else 0),
                "scale": lambda: Transform().scale(v[0], v[1] if len(v) > 1 else v[0]),
                "rotate": lambda: Transform().translate(*(v[1:3] or (0, 0))).rotate(math.radians(v[0])).translate(*(-x for x in (v[1:3] or (0, 0)))),
                "skewX": lambda: Transform().skew(math.radians(v[0]), 0),
                "skewY": lambda: Transform().skew(0, math.radians(v[0]))}.get(name)
        if step is None:
            raise ValueError(f'svg: unknown transform "{name}" (accepted: matrix translate scale rotate skewX skewY)')
        t = t.transform(step())
    return t


def _style(el, inherited: dict) -> dict:
    s = dict(inherited)
    for k in ("fill", "fill-rule", "display"):
        if el.get(k) is not None:
            s[k] = el.get(k).strip()
    for k, v in re.findall(r"([\w-]+)\s*:\s*([^;]+)", el.get("style", "")):
        if k in ("fill", "fill-rule", "display"):
            s[k] = v.strip()
    return s


def _shape_d(tag: str, el) -> str | None:
    f = lambda k, default=0.0: float(_NUM.match(el.get(k, str(default)).strip() or "0").group())  # noqa: E731
    if tag == "path":
        return el.get("d", "")
    if tag == "rect":
        x, y, w, h = f("x"), f("y"), f("width"), f("height")
        rx = f("rx", f("ry")) if el.get("rx") or el.get("ry") else 0.0
        ry = f("ry", rx) if el.get("ry") else rx
        rx, ry = min(rx, w / 2), min(ry, h / 2)
        if not rx and not ry:
            return f"M{x} {y}H{x + w}V{y + h}H{x}Z"
        return (f"M{x + rx} {y}H{x + w - rx}A{rx} {ry} 0 0 1 {x + w} {y + ry}V{y + h - ry}A{rx} {ry} 0 0 1 {x + w - rx} {y + h}"
                f"H{x + rx}A{rx} {ry} 0 0 1 {x} {y + h - ry}V{y + ry}A{rx} {ry} 0 0 1 {x + rx} {y}Z")
    if tag in ("circle", "ellipse"):
        cx, cy = f("cx"), f("cy")
        rx = f("r") if tag == "circle" else f("rx")
        ry = rx if tag == "circle" else f("ry")
        return f"M{cx - rx} {cy}A{rx} {ry} 0 1 1 {cx + rx} {cy}A{rx} {ry} 0 1 1 {cx - rx} {cy}Z"
    if tag in ("polygon", "polyline"):
        n = _NUM.findall(el.get("points", ""))
        return "M" + " ".join(n[:2]) + "L" + " ".join(n[2:]) + "Z" if len(n) >= 4 else None
    return None


def _walk(el, t: Transform, style: dict, out: list):
    tag = el.tag.split("}")[-1]
    if tag in _SKIP:
        return
    t, style = t.transform(_transform(el.get("transform"))), _style(el, style)
    if style.get("display") == "none":
        return
    if style.get("fill") != "none" and (d := _shape_d(tag, el)):
        p = pathops.Path()
        draw_d(d, TransformPen(p.getPen(), t))
        if style.get("fill-rule") == "evenodd":
            p.fillType = pathops.FillType.EVEN_ODD
        p.simplify(fix_winding=True, keep_starting_points=False)
        out.append(p)
    for child in el:
        _walk(child, t, style, out)


def _merged(paths: list):
    total = pathops.Path()
    for p in paths:
        total = pathops.op(total, p, pathops.PathOp.UNION)
    total.simplify(fix_winding=True, keep_starting_points=False)
    return total


def _fit(path, width_m: float, who: str) -> list[dict]:
    if width_m <= 0:
        raise ValueError(f"{who}: svgWidth must be above 0 (metres)")
    rough = O.contours_of(path, 1e9)
    if not rough:
        raise ValueError(f"{who}: the drawing has no filled shapes (strokes, images and fill=\"none\" shapes are ignored)")
    x0, y0, x1, y1 = O.bounds(rough)
    if x1 - x0 <= 0:
        raise ValueError(f"{who}: the drawing has no width")
    scale = width_m / (x1 - x0)
    contours = O.contours_of(path, max(O.MIN_TOLERANCE, 0.002 * width_m) / scale)
    return O.nest(O.place(contours, scale, ((x0 + x1) / 2, (y0 + y1) / 2), True))


def _from_d(d: str, rule: str, width_m: float, who: str) -> list[dict]:
    p = pathops.Path()
    draw_d(d, p.getPen())
    if rule == "evenodd":
        p.fillType = pathops.FillType.EVEN_ODD
    p.simplify(fix_winding=True, keep_starting_points=False)
    return _fit(p, width_m, who)


def svg_outline(item: dict) -> list[dict]:
    who, file, d, width = item["id"], item["svgFile"], item["pathData"].strip(), float(item["svgWidth"])
    if d:
        return O.cached(("svgd", d, width), lambda: _from_d(d, "nonzero", width, who))
    if not file:
        raise ValueError(f"{who}: give an svgFile (absolute path of an .svg) or pathData (SVG path data text)")
    if not Path(file).is_file():
        raise ValueError(f'{who}: svg file "{file}" was not found')

    def make():
        try:
            root = ET.parse(file).getroot()
        except ET.ParseError as e:
            raise ValueError(f'{who}: "{file}" is not valid SVG ({e})') from None
        paths: list = []
        _walk(root, Identity, {}, paths)
        return _fit(_merged(paths), width, who)
    return O.cached(("svg", file, O.stamp(file), width), make)


def _find_layer(node, layer: str):
    if isinstance(node, dict):
        if node.get("id") == layer and node.get("type") == "path":
            return node
        node = list(node.values())
    if isinstance(node, list):
        for v in node:
            if (hit := _find_layer(v, layer)):
                return hit


def _path_ids(node) -> list[str]:
    if isinstance(node, dict):
        own = [node["id"]] if node.get("type") == "path" and "id" in node else []
        return own + _path_ids(list(node.values()))
    if isinstance(node, list):
        return [i for v in node for i in _path_ids(v)]
    return []


def path2d_outline(item: dict, folder) -> list[dict]:
    """The `d` of a path layer in the 2D document `doc2d` (docs/<doc2d>.mtn in the project folder), drawn y-down in its px."""
    who, doc2d, layer = item["id"], item["doc2d"], item["layer"]
    if not doc2d or not layer:
        raise ValueError(f"{who}: give doc2d (the id of a 2D item in this project) and layer (a path layer's id in it)")
    if folder is None:
        raise ValueError(f"{who}: path2d reads the 2D document from the project folder, and this document has none (save it in a project)")
    file = Path(folder) / "docs" / f"{doc2d}.mtn"
    if not file.is_file():
        have = sorted(p.stem for p in (Path(folder) / "docs").glob("*.mtn"))
        raise ValueError(f'{who}: no 2D document "{doc2d}" in the project folder (there are: {", ".join(have) or "none"})')
    width = float(item["svgWidth"])

    def make():
        data = json.loads(file.read_text(encoding="utf-8")).get("doc", {})
        node = _find_layer(data, layer)
        if node is None:
            raise ValueError(f'{who}: "{doc2d}" has no path layer "{layer}" (its path layers: {", ".join(_path_ids(data)) or "none"})')
        if not node.get("d"):
            raise ValueError(f'{who}: path layer "{layer}" in "{doc2d}" has no points yet')
        return _from_d(node["d"], node.get("fillRule", "nonzero"), width, who)
    return O.cached(("path2d", str(file), O.stamp(str(file)), layer, width), make)


def _path_layers(node) -> list[dict]:
    if isinstance(node, dict):
        own = [{"id": node["id"], "name": node.get("name") or node["id"]}] if node.get("type") == "path" and node.get("d") else []
        return own + _path_layers(list(node.values()))
    if isinstance(node, list):
        return [x for v in node for x in _path_layers(v)]
    return []


def drawings(folder) -> list[dict]:
    """The 2D items in a project folder that have drawn path layers, for picking a path2d source:
    [{"doc2d": id, "name": its name, "layers": [{"id", "name"}]}], sorted by name; [] without a folder."""
    if folder is None or not (Path(folder) / "docs").is_dir():
        return []
    out = []
    for file in sorted((Path(folder) / "docs").glob("*.mtn")):
        try:
            data = json.loads(file.read_text(encoding="utf-8")).get("doc", {})
        except (OSError, ValueError) as e:
            raise ValueError(f'2D item "{file.stem}" can\'t be read: {e}') from e
        if layers := _path_layers(data):
            out.append({"doc2d": file.stem, "name": data.get("name") or file.stem, "layers": layers})
    return sorted(out, key=lambda d: d["name"].lower())
