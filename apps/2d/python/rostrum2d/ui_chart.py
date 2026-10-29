"""chart(): a bar or line chart with a y axis (round tick values and gridlines), x labels and an optional title, as
plain editable layers (guide lower-thirds-and-charts; `bars` is the bare bar strip without axes).

    with scr:                                       # a device's screen, a column, a card's body …
        chart([12, 30, 18, 42], labels=["Q1", "Q2", "Q3", "Q4"], title="Revenue", unit="$k", at="#data")

It is a column (`<id>`) filling its container's width: `<id>_title`, then a row with the tick labels (`<id>_y0` …,
bottom first) and the plot (`<id>_plot`: gridlines `<id>_grid0` …, bars `<id>_bar0` … or the line `<id>_line` with
dots `<id>_dot0` …), then the x labels (`<id>_label0` …). The axis runs 0 .. a round number at or above the biggest
value (plot.nice_ticks), or to `top`. Text sizes, bar corners and the line's width come from the width the chart is
made in (a phone's screen, a laptop's, a whole frame), the default height from that room too; colours from what it
sits on (ui_layout.palette); every one is a parameter. `at=` grows the bars (scaleY from 0, `stagger` s apart) or
draws the line on (trimEnd), from that time (seconds or "#marker+0.2"); without `at=` it is still.
"""
from __future__ import annotations

from . import pathdata, plot, ui_layout as U
from .script_layout import in_layout
from .ui_layout import ACCENT
from .ui_lower_third import when


def room_down(build) -> None:
    """The columns a growing chart is made in, up to the device screen (or a box of set height), grow too, so the chart
    takes the room left under what is above it rather than the room its column fits."""
    from .script import Item
    screens, chain = getattr(build, "screens", {}), build.holders
    for node, parent in zip(reversed(chain[1:]), reversed(chain[:-1])):
        if node["id"] in screens or node.get("sizeH", "fit") != "fit" or parent.get("layout") != "column":
            return
        Item(build, node).set(layoutGrow=1)


def room(build) -> tuple[float, float]:
    """The width and height a block made now gets: the nearest sized box (or the scene) less the padding of the
    containers on the way (a guess before the layout runs: in a row next to others, give the block its own w=)."""
    px = py = 0.0
    for node in reversed(build.holders):
        if node["type"] == "comp":
            return float(node.get("width", 1920)) - px, float(node.get("height", 1080)) - py
        if node.get("layout", "none") != "none":
            p = float(node.get("padding", 0))
            px += 2 * (p if float(node.get("paddingX", -1)) < 0 else float(node["paddingX"]))
            py += 2 * (p if float(node.get("paddingY", -1)) < 0 else float(node["paddingY"]))
        if node["id"] in build.sized:
            return float(node.get("w", 0)) - px, float(node.get("h", 0)) - py
    return 1920.0 - px, 1080.0 - py


def maker(build, block, auto, colours):
    L = build.layer

    def chart(values, labels=None, id=None, kind="bar", x=None, y=None, w=None, h=None, title=None, unit=None,
              top=None, ticks=4, color=ACCENT, ink=None, muted=None, line=None, size=None, gap=0.35, radius=None,
              width=None, dots=True, at=None, duration=0.8, stagger=0.06, ease="easeOut", apart=False):
        """A chart of `values` (kind "bar" or "line") with `labels` under them, a y axis of about `ticks` round steps
        from 0 to `top` (left out: a round number at or above the biggest value) and gridlines; `title` (and `unit`,
        after it in the muted colour) above. `size` the labels' size, `gap` the share of each bar's slot left empty,
        `radius` the bars' corners, `width` the line's. Returns the bars or the dots, left first; .group too."""
        if kind not in ("bar", "line"):
            raise ValueError(f'chart: kind "{kind}" is not one of bar, line')
        vals = [float(v) for v in values]
        if not vals or min(vals) < 0:
            raise ValueError("chart: values are one or more numbers from 0 up (the axis starts at 0)")
        ink, muted, line = colours(ink=ink, muted=muted, line=line)
        id = id or auto("chart")
        rw, rh = room(build)
        cw = float(w) if isinstance(w, (int, float)) else rw - (0 if in_layout(build) and not apart else x or 0)
        s = float(size or 13 * (max(cw, 120) / U.BASE_W) ** 0.6)     # phone ~13 px, laptop screen ~19, full frame ~31
        given_h = h
        h = float(h or min(cw * 0.55, rh * 0.5))
        steps = plot.nice_ticks(0, float(top or max(vals) or 1), ticks, extend=True)
        hi = float(steps[-1])
        names = [plot.tick_label(v, steps) for v in steps]
        yw = max(len(n) for n in names) * s * 0.62
        head = s * 1.5 * 1.6 if title else 0.0
        foot = s * 2.0 if labels else s * 0.6
        half = s * 0.6                              # a tick label's half height: the gridlines run that far in
        ph = max(h - head - foot - 2 * half, 1.0)   # the plot's own height, 0 .. hi
        made = U.Rows()
        # A bar chart left without h= in a layout grows into the room left under what is above it (h is then its least
        # height; its bars are shares of the plot). A line is drawn for one size when the script runs: it keeps h.
        grows = {"grow": 1} if kind == "bar" and given_h is None and in_layout(build) and not apart else {}
        if grows:
            room_down(build)
        with block("column", id, x, y, w, h, apart, **grows) as made.group:
            if title:
                with L("group", f"{id}_head", layout="row", h=head, align="start", gap=s * 0.6, padding=0):
                    L("text", f"{id}_title", body=str(title), size=s * 1.5, color=ink, weight=680)
                    if unit:
                        L("text", f"{id}_unit", body=str(unit), size=s * 1.1, color=muted, weight=500)
            with L("group", f"{id}_body", layout="row", w="fill", grow=1, gap=s * 0.7, padding=0, align="stretch"):
                with L("group", f"{id}_axis", layout="column", w=yw, justify="between", align="end", padding=0):
                    for i, n in reversed(list(enumerate(names))):
                        L("text", f"{id}_y{i}", body=n, size=s, color=muted, weight=500, align="right")
                with L("group", f"{id}_plot", layout="stack", grow=1, padding_y=half, padding_x=0, align="stretch"):
                    with L("group", f"{id}_grid", layout="column", w="fill", h="fill", justify="between", padding=0):
                        for i in reversed(range(len(steps))):
                            L("shape", f"{id}_grid{i}", w="fill", h=max(1.0, s * 0.08), fill=line)
                    if kind == "bar":
                        with L("group", f"{id}_bars", layout="row", w="fill", h="fill", align="stretch", padding=0):
                            for i, v in enumerate(vals):
                                with L("group", f"{id}_slot{i}", layout="column", grow=1, align="center", justify="end", padding=0):
                                    made.append(L("shape", f"{id}_bar{i}", w=f"{round((1 - gap) * 100, 4)}%", h=f"{round(max(v / hi, 0.0) * 100, 4)}%",
                                                  origin="bottom-center", radius=s * 0.35 if radius is None else radius, fill=color))
                    else:
                        pw = max(cw - yw - s * 0.7, 1.0)    # the plot's width as made now (the line is drawn in it)
                        pts = [((i + 0.5) * pw / len(vals), ph * (1 - v / hi)) for i, v in enumerate(vals)]
                        lw = s * 0.25 if width is None else float(width)
                        with L("group", f"{id}_lines", w="fill", h="fill", origin="top-left"):
                            d = pathdata.check(plot.line_d(pts), f"{id}_line.d")
                            made.line = L("path", f"{id}_line", d=d, x=0, y=0, w=pw, h=ph, origin="top-left", filled=False,
                                          stroke=True, strokeColor=color, strokeWidth=lw)
                            for i, (px, py) in enumerate(pts if dots else ()):
                                made.append(L("shape", f"{id}_dot{i}", shape="ellipse", x=px, y=py, w=lw * 2.6, h=lw * 2.6, fill=color))
            if labels:
                with L("group", f"{id}_labels", layout="row", w="fill", h=foot, padding_y=0, padding_x=0, gap=0, align="center"):
                    L("group", f"{id}_labels_pad", w=yw + s * 0.7, h=1)
                    for i in range(len(vals)):
                        with L("group", f"{id}_under{i}", layout="row", grow=1, justify="center", padding=0):
                            L("text", f"{id}_label{i}", body=str(labels[i]) if i < len(labels) else "", size=s, color=muted, weight=500)
        if at is not None:
            t0 = when(build, at, f"{id} at")
            if kind == "bar":
                for i, b in enumerate(made):
                    b.key("scaleY", {t0 + i * stagger: (0.0, ease), t0 + i * stagger + duration: 1.0})
            else:
                made.line.key("trimEnd", {t0: (0.0, "linear"), t0 + duration: 1.0})
                for i, d in enumerate(made):
                    ti = t0 + duration * (i + 0.5) / len(vals)
                    d.key("scale", {ti: (0.0, ease), ti + 0.25: 1.0})
        return made

    return {"chart": chart}
