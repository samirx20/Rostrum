"""PSD shape layer → a 2D path node (the same node SVG import makes: `d` in px, fill / stroke props). The outline is the
layer's vector mask (psd-tools; knots are stored as 0..1 fractions of the document, as (y, x)). Solid fill and a solid
outline are carried; gradient / pattern fills, outer / inner outline alignment and boolean path operations are not
(the caller keeps the layer's pixels for the first, the report says so for the others).
"""
from __future__ import annotations

from psd_tools.constants import Tag

_CAP = {"butt": "butt", "round": "round", "square": "square"}
_JOIN = {"miter": "miter", "round": "round", "bevel": "bevel"}
_OTHER_FILLS = (Tag.GRADIENT_FILL_SETTING, Tag.PATTERN_FILL_SETTING)


def _rgb(desc) -> str | None:
    c = desc.get(b"Clr ") if hasattr(desc, "get") else None
    if not c or b"Rd  " not in c:
        return None
    return "#" + "".join(f"{round(max(0.0, min(255.0, float(c[k])))):02x}" for k in (b"Rd  ", b"Grn ", b"Bl  "))


def _d(paths, w: float, h: float) -> tuple[str, list[float]]:
    """The absolute `d` of every subpath (px) and its box [x, y, w, h] (anchors and handles)."""
    def pt(p):                                                # (y, x) fractions → px
        return p[1] * w, p[0] * h
    parts, xs, ys = [], [], []
    for path in paths:
        knots = list(path)
        if not knots:
            continue
        a0 = pt(knots[0].anchor)
        parts.append(f"M {a0[0]:.3f} {a0[1]:.3f}")
        order = knots + ([knots[0]] if path.is_closed() else [])
        for k, n in zip(order, order[1:]):
            c1, c2, a = pt(k.leaving), pt(n.preceding), pt(n.anchor)
            parts.append("C " + " ".join(f"{v:.3f}" for v in (*c1, *c2, *a)))
            xs += [c1[0], c2[0], a[0]]
            ys += [c1[1], c2[1], a[1]]
        xs.append(a0[0]); ys.append(a0[1])
        if path.is_closed():
            parts.append("Z")
    return " ".join(parts), [min(xs), min(ys), max(max(xs) - min(xs), 1.0), max(max(ys) - min(ys), 1.0)]


def shape_node(layer, width: int, height: int, report: list) -> dict | None:
    name, tags = layer.name, layer.tagged_blocks
    vm = layer.vector_mask
    if vm is None or not len(vm.paths):
        return None
    if any(tags.get_data(t) is not None for t in _OTHER_FILLS):
        report.append(f"shape '{name}': gradient / pattern fill is not carried; kept as a picture")
        return None
    fill = _rgb(tags.get_data(Tag.SOLID_COLOR_SHEET_SETTING) or {})
    stroke = layer.stroke if layer.has_stroke() and layer.stroke.enabled else None
    scol = _rgb(stroke.content) if stroke else None
    if stroke and scol is None:
        report.append(f"shape '{name}': outline is not a plain colour; kept as a picture")
        return None
    if fill is None and scol is None:
        report.append(f"shape '{name}': no plain fill or outline found; kept as a picture")
        return None
    if len({p.operation for p in vm.paths}) > 1:
        report.append(f"shape '{name}': combines paths with subtract / intersect; kept as a picture")
        return None
    d, box = _d(vm.paths, width, height)
    props = {"d": d, "filled": fill is not None}
    if fill:
        props["fill"] = fill
    if vm.inverted:
        report.append(f"shape '{name}': inverted path is not carried; kept as a picture")
        return None
    if stroke:
        w = float(stroke.line_width)
        props.update(stroke=True, strokeColor=scol, strokeWidth=max(w, 0.5), cap=_CAP.get(str(stroke.line_cap_type), "butt"),
                     join=_JOIN.get(str(stroke.line_join_type), "miter"))
        dash = list(stroke.line_dash_set or [])
        if dash:
            props.update(dash=max(dash[0] * w, 0.5), gap=max((dash[1] if len(dash) > 1 else dash[0]) * w, 0.5))
        if "CENTER" not in str(stroke.line_alignment):
            report.append(f"shape '{name}': outline sits {str(stroke.line_alignment).rsplit('.', 1)[-1].lower()} the edge in the PSD; "
                          "drawn centred")
    return {"type": "path", "name": name, "box": box, "props": props}
