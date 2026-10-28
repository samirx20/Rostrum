"""Script calls that build product screens as plain, editable layers (guide ui-and-product-animation, "Building
blocks"): a device (phone, laptop, browser window) whose screen is a clipped group, and the parts a screen is made
of (status bar, title bar, tab bar, list rows, cards, buttons, toggles, chart bars) plus a counting number.

    scr = device("phone")                       # fills 82 % of the picture's height, centred; layer("phone") is the device
    with scr:
        status_bar(); nav_bar("Trips")          # each block made without y goes under the one before it
        hero = card("hero", h=180, title="Lisbon dinner", value="$168.00")
        rows = list_rows([("Taxi", "2 people", "$24.50")])      # under the card; rows.bottom is where it ends
        tab_bar(["Home", "Trips"])              # always at the screen's bottom

Each block is a group of shapes and texts with ids made from the block's id (`trips_r0_title`, `pay_label`), placed
by its top-left (x, y) in the parent's px, so it is moved, keyed, restyled or taken apart like anything else. Left
out, x / y / w come from the parent (ui_layout.py): full width for bars and lists, a side margin for cards, buttons
and toggles, stacked under the previous block. Sizes and colours are a starting point (drawn for a 390 px wide
screen, scaled to the parent's width); every one is a parameter. Nothing is animated except `counter`.
"""
from __future__ import annotations

from . import ui_device, ui_layout as U
from .ui_layout import ACCENT, INK, LINE, MUTED, PAPER


def for_script(build) -> dict:
    L = build.layer
    flow = U.Flow(build)
    build.ui_flow = flow
    used: dict[str, int] = {}

    def auto(word):                         # block ids when none is given: list, list_2 …
        used[word] = used.get(word, 0) + 1
        return word if used[word] == 1 else f"{word}_{used[word]}"

    def box(id, x, y, w, h, **f):           # a group placed by its top-left, its children in its own px
        return L("group", id, x=x, y=y, w=w, h=h, anchorX=0, anchorY=0, **f)

    def words(id, body, x, y, size, color, align="left", weight=500, **f):
        return L("text", id, body=str(body), x=x, y=y, size=size, color=color, align=align, weight=weight, **f)

    def span(x, w, side=True):              # x and w left out: the parent's width, with or without side margins
        pw = U.parent_size(build)[0]
        m = pw * 0.06 if side else 0.0
        x = m if x is None else float(x)
        return x, float(w) if w is not None else pw - x - m

    def above(g):                           # the space above a stacked block
        return flow.unit() * 16 if g is None else float(g)

    def status_bar(id=None, w=None, y=None, x=None, time="9:41", color=INK, h=None, size=None):
        """Time on the left, signal, Wi-Fi and battery on the right."""
        id = id or auto("status")
        x, w = span(x, w, side=False)
        h = h or 54 * flow.unit()
        size = size or h * 0.36
        g = box(id, x, flow.place(h, y, id=id), w, h)
        with g:
            words(f"{id}_time", time, w * 0.09, h * 0.55, size, color, weight=650)
            rx = w * 0.91
            L("shape", f"{id}_battery", x=rx - size * 0.78, y=h * 0.55, w=size * 1.45, h=size * 0.62, radius=size * 0.2, fill=color)
            L("shape", f"{id}_wifi", shape="arc", startAngle=-45, sweep=90, hole=0, x=rx - size * 2.4, y=h * 0.55 + size * 0.3, w=size * 1.3, h=size * 1.3, fill=color)
            for i in range(4):
                bh = size * (0.3 + 0.18 * i)
                L("shape", f"{id}_signal{i}", x=rx - size * 4.4 + i * size * 0.36, y=h * 0.55 + (size * 0.84 - bh) / 2 - size * 0.12, w=size * 0.23, h=bh, radius=size * 0.08, fill=color)
        return g

    def nav_bar(title, id=None, w=None, y=None, x=None, h=None, back=None, action=None, color=INK, muted=MUTED, size=None):
        """A screen's title row: an optional back label left, a big title, an optional action word right. Every text
        sits inside its own height, so the next block (stacked under it) never touches the title."""
        id = id or auto("nav")
        x, w = span(x, w, side=False)
        h = h or 96 * flow.unit()
        size = size or h * 0.34
        g = box(id, x, flow.place(h, y, id=id), w, h)
        with g:
            if back:
                words(f"{id}_back", "‹ " + back, w * 0.06, h * 0.2, size * 0.5, muted)
            if action:
                words(f"{id}_action", action, w * 0.94, h * 0.2, size * 0.5, muted, align="right")
            words(f"{id}_title", title, w * 0.06, h - size * 0.75, size, color, weight=760)
        return g

    def tab_bar(labels, id=None, w=None, y=None, x=None, h=None, active=0, fill=PAPER, color=MUTED, accent=ACCENT, line=LINE, parent_h=None):
        """Tabs evenly across the bottom of the screen (y = its top, to put it elsewhere), each an icon square and a
        label; `active` is drawn in the accent colour. It never moves the stack of the other blocks."""
        id = id or auto("tabs")
        x, w = span(x, w, side=False)
        h = h or 84 * flow.unit()
        if y is None:
            y = (parent_h if parent_h is not None else U.parent_size(build)[1]) - h
            flow.floor(y, id)
        g = box(id, x, y, w, h)
        with g:
            L("shape", f"{id}_bg", x=w / 2, y=h / 2, w=w, h=h, fill=fill)
            L("shape", f"{id}_line", x=w / 2, y=0.5, w=w, h=1, fill=line)
            n = max(len(labels), 1)
            for i, lab in enumerate(labels):
                cx, c = w * (i + 0.5) / n, accent if i == active else color
                L("shape", f"{id}_icon{i}", x=cx, y=h * 0.36, w=h * 0.26, h=h * 0.26, radius=h * 0.07, fill=c,
                  filled=i == active, stroke=i != active, strokeColor=c, strokeWidth=2.5)
                words(f"{id}_label{i}", lab, cx, h * 0.72, h * 0.15, c, align="center", weight=600 if i == active else 500)
        return g

    def list_rows(rows, id=None, x=None, y=None, w=None, row_h=None, avatar=True, color=INK, muted=MUTED, line=LINE,
                  accent=ACCENT, size=None, pad=None, gap=None):
        """One row a group (`<id>_r0` …): an avatar with the title's first letter, the title, a detail line under it,
        a value on the right, a divider. A row is a string, (title, detail) or (title, detail, value).
        Returns the row groups, top first (stagger them in; layer.stagger orders by place); .group and .bottom too."""
        id = id or auto("list")
        x, w = span(x, w, side=False)
        row_h = row_h or 72 * flow.unit()
        size = size or row_h * 0.27
        pad = pad if pad is not None else w * 0.06
        made = U.Rows()
        with box(id, x, flow.place(row_h * len(rows), y, above(gap), id), w, row_h * len(rows)) as made.group:
            for i, row in enumerate(rows):
                title, detail, value = (tuple([row]) if isinstance(row, str) else tuple(row)) + (None,) * (3 - (1 if isinstance(row, str) else len(row)))
                with box(f"{id}_r{i}", 0, i * row_h, w, row_h) as r:
                    tx = pad
                    if avatar:
                        d = row_h * 0.56
                        L("shape", f"{id}_r{i}_avatar", shape="ellipse", x=pad + d / 2, y=row_h / 2, w=d, h=d, fill=accent, fillOpacity=0.14)
                        words(f"{id}_r{i}_initial", str(title)[:1].upper(), pad + d / 2, row_h / 2, d * 0.42, accent, align="center", weight=700)
                        tx = pad + d + pad * 0.6
                    words(f"{id}_r{i}_title", title, tx, row_h * (0.38 if detail else 0.5), size, color, weight=620)
                    if detail:
                        words(f"{id}_r{i}_detail", detail, tx, row_h * 0.66, size * 0.78, muted, weight=450)
                    if value is not None:
                        words(f"{id}_r{i}_value", value, w - pad, row_h / 2, size, color, align="right", weight=650)
                    L("shape", f"{id}_r{i}_line", x=(tx + w) / 2, y=row_h - 0.5, w=w - tx, h=1, fill=line)
                made.append(r)
        return made

    def card(id, x=None, y=None, w=None, h=None, title=None, detail=None, value=None, fill=PAPER, color=INK, muted=MUTED,
             radius=None, shadow=True, pad=None, size=None, gap=None):
        """A rounded card (`<id>_bg`) with an optional title and detail at its top-left and a big value at its
        bottom-left; `shadow` adds a soft drop shadow effect. Make more of the card's layers inside `with` it."""
        x, w = span(x, w)
        u = flow.unit()
        h = float(h or 180 * u)
        pad = pad if pad is not None else min(w, h) * 0.12
        size = size or min(h * 0.13, 30 * u)
        g = box(id, x, flow.place(h, y, above(gap), id), w, h)
        with g:
            bg = L("shape", f"{id}_bg", x=w / 2, y=h / 2, w=w, h=h, radius=24 * u if radius is None else radius, fill=fill)
            if shadow:
                bg.effect("shadow", f"{id}_shadow", dy=h * 0.06, radius=h * 0.18, strength=0.22)
            if title:
                words(f"{id}_title", title, pad, pad + size * 0.6, size, color, weight=650)
            if detail:
                words(f"{id}_detail", detail, pad, pad + size * 1.75, size * 0.78, muted, weight=450)
            if value is not None:
                words(f"{id}_value", value, pad, h - pad - size * 0.9, size * 2, color, weight=760)
        return g

    def button(label, id=None, x=None, y=None, w=None, h=None, fill=ACCENT, color="#ffffff", radius=None, size=None,
               outline=False, gap=None):
        """A button: a pill (`<id>_bg`) with its label centred (`<id>_label`); `outline` draws only its edge."""
        id = id or auto("button")
        x, w = span(x, w)
        h = float(h or 56 * flow.unit())
        g = box(id, x, flow.place(h, y, above(gap), id), w, h)
        with g:
            L("shape", f"{id}_bg", x=w / 2, y=h / 2, w=w, h=h, radius=h / 2 if radius is None else radius, fill=fill,
              filled=not outline, stroke=outline, strokeColor=fill, strokeWidth=3)
            words(f"{id}_label", label, w / 2, h / 2, size or h * 0.32, fill if outline else color, align="center", weight=650)
        return g

    def toggle(id=None, x=None, y=None, on=False, w=None, h=None, label=None, detail=None, on_color="#22c55e",
               off_color="#d1d5db", knob="#ffffff", color=INK, muted=MUTED, gap=None):
        """A switch: the track (`<id>_track`) and the knob (`<id>_knob`). To flip it, key the knob's x (from h/2 to
        w - h/2) and the track's fill. Left out, x puts it against the right margin. With `label` (and `detail`) it
        is a settings row: the words on the left, the switch (`<id>_switch`) on the right."""
        id = id or auto("toggle")
        u = flow.unit()
        w, h = float(w or 52 * u), float(h or 32 * u)
        pw = U.parent_size(build)[0]
        m = pw * 0.06
        if not label:
            g = box(id, pw - m - w if x is None else x, flow.place(h, y, above(gap), id), w, h)
            sw = g
        else:
            rh = h * (2.2 if detail else 1.6)
            g = box(id, 0 if x is None else x, flow.place(rh, y, above(gap), id), pw, rh)
            with g:
                words(f"{id}_label", label, m, rh * (0.36 if detail else 0.5), 17 * u, color, weight=600)
                if detail:
                    words(f"{id}_detail", detail, m, rh * 0.68, 13 * u, muted, weight=450)
                sw = box(f"{id}_switch", pw - m - w, (rh - h) / 2, w, h)
        with sw:
            L("shape", f"{id}_track", x=w / 2, y=h / 2, w=w, h=h, radius=h / 2, fill=on_color if on else off_color)
            L("shape", f"{id}_knob", shape="ellipse", x=w - h / 2 if on else h / 2, y=h / 2, w=h * 0.82, h=h * 0.82, fill=knob)
        return g

    def bars(values, id=None, x=None, y=None, w=None, h=None, color=ACCENT, gap=0.35, top=None, radius=None, labels=None,
             label_color=MUTED, size=None, space=None):
        """A bar chart: one bar per value, standing on the box's bottom edge (anchored there, so a key on `scaleY`
        from 0 grows it upward), heights to `top` (default the biggest value). `labels` go under the bars (inside
        the block's height). Returns the bar shapes, left first; .group and .bottom too. `space`: the gap above it."""
        id = id or auto("bars")
        x, w = span(x, w)
        u = flow.unit()
        size = size or 13 * u
        lab = size * 1.8 if labels else 0.0
        h = float(h or 140 * u)
        n = max(len(values), 1)
        top = float(top or max(values) or 1)
        slot = w / n
        bw = slot * (1 - gap)
        made = U.Rows()
        with box(id, x, flow.place(h, y, above(space), id), w, h) as made.group:
            for i, v in enumerate(values):
                bh = max((h - lab) * float(v) / top, 0.0)
                made.append(L("shape", f"{id}_{i}", x=slot * (i + 0.5), y=h - lab, w=bw, h=bh, anchorY=1,
                              radius=bw * 0.18 if radius is None else radius, fill=color))
                if labels and i < len(labels):
                    words(f"{id}_label{i}", labels[i], slot * (i + 0.5), h - lab / 2, size, label_color, align="center")
        return made

    def counter(id, start=0.0, to=100.0, at=0.0, duration=1.0, ease="smooth", decimals=0, prefix="", suffix="",
                separator=None, digits=None, **fields):
        """One text that counts from `start` at `at` to `to` at `at + duration` (text.counter): the engine writes the
        number each frame; tabular figures keep its width steady. More steps: .key("count", {t: v})."""
        f = {"counter": True, "countDecimals": decimals, "countPrefix": prefix, "countSuffix": suffix,
             "figures": "tabular lining", **fields}
        if separator is not None:
            f["countSeparator"] = separator
        if digits is not None:
            f["countDigits"] = digits
        t = L("text", id, **f)
        return t.key("count", {at: (start, ease), at + duration: to})

    return {"device": ui_device.maker(build, box, words), "status_bar": status_bar, "nav_bar": nav_bar, "tab_bar": tab_bar, "list_rows": list_rows,
            "card": card, "button": button, "toggle": toggle, "bars": bars, "counter": counter}
