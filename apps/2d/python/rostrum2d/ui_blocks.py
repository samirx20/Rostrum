"""Script calls that build product screens as plain, editable layers (guide ui-and-product-animation, "Building
blocks", and lay-out-a-screen): a device (phone, laptop, browser window) whose screen is a column, and the parts a
screen is made of (status bar, title bar, tab bar, list rows, cards, buttons, toggles, chart bars) plus a counting
number.

    scr = device("phone", screen="#ffffff")     # fills 82 % of the picture's height, centred; its screen is a column
    with scr:
        status_bar(); nav_bar("Trips")
        with column(padding=20, gap=16):        # the content: a padded column, each block full width in it
            hero = card("hero", h=180, title="Lisbon dinner", value="$168.00")
            rows = list_rows([("Taxi", "2 people", "$24.50")])
        tab_bar(["Home", "Trips"])              # pinned to the screen's bottom (a spacer above it takes the room)

Each block is a container of shapes and texts with ids made from the block's id (`trips_r0_title`, `pay_label`), so
it is moved, keyed, restyled or taken apart like anything else. Made in a container (a device's screen, a column, a
row) the container places it and it fills the width (w= for its own; apart=True with x= / y= to place it yourself);
made anywhere else it needs x= and y= (its top-left). Sizes and colours are a starting point (drawn for a 390 px wide
screen, scaled to the parent's width, colours for a light screen); every one is a parameter. Nothing is animated
except `counter`.
"""
from __future__ import annotations

from . import ui_device, ui_layout as U
from .script_layout import in_layout
from .ui_layout import ACCENT, INK, LINE, MUTED, PAPER


def for_script(build) -> dict:
    L = build.layer
    used: dict[str, int] = {}

    def auto(word):                         # block ids when none is given: list, list_2 …
        used[word] = used.get(word, 0) + 1
        return word if used[word] == 1 else f"{word}_{used[word]}"

    def unit():
        return U.parent_size(build)[0] / U.BASE_W

    def box(id, x, y, w, h, **f):           # a plain group placed by its top-left, its children in its own px
        return L("group", id, x=x, y=y, w=w, h=h, anchorX=0, anchorY=0, **f)

    def words(id, body, x, y, size, color, align="left", weight=500, **f):
        return L("text", id, body=str(body), x=x, y=y, size=size, color=color, align=align, weight=weight, **f)

    def say(id, body, size, color, weight=500, **f):        # a text a layout places
        return L("text", id, body=str(body), size=size, color=color, weight=weight, **f)

    def block(kind, id, x, y, w, h, apart=False, **f):
        """A block's own container (`kind` a layout, None a plain group): placed by the container it is made in (or by
        x, y elsewhere), full width unless w is given."""
        inside = in_layout(build)
        if not inside and (x is None or y is None):
            raise ValueError(f"{id}: a screen block is placed by the container it is made in (a device's screen, a "
                             "column, a row); make it inside one, or give x= and y= (its top-left)")
        place = {"x": x, "y": y} if x is not None or y is not None else {}
        if apart:
            place["apart"] = True
        if w is None:
            w = "fill" if inside and not apart else U.parent_size(build)[0] - (x or 0)
        if kind is None:                    # a plain group: its layers placed by their own x, y
            return L("group", id, origin="top-left", w=w, h=h, **place, **f)
        return L("group", id, **{"layout": kind, "origin": "top-left", "w": w, "h": "fit" if h is None else h,
                                 "padding": 0, "gap": 0, **place, **f})

    def status_bar(id=None, w=None, y=None, x=None, time="9:41", color=INK, h=None, size=None, apart=False):
        """Time on the left, signal, Wi-Fi and battery on the right."""
        id = id or auto("status")
        u = unit()
        h = h or 54 * u
        size = size or h * 0.36
        g = block("row", id, x, y, w, h, apart, padding_x=26 * u, justify="between", align="center")
        with g:
            say(f"{id}_time", time, size, color, weight=650)
            with L("group", f"{id}_icons", layout="row", gap=size * 0.4, align="center", padding=0):
                with L("group", f"{id}_signal", layout="row", gap=size * 0.13, align="end", padding=0):
                    for i in range(4):
                        L("shape", f"{id}_signal{i}", w=size * 0.23, h=size * (0.3 + 0.18 * i), radius=size * 0.08, fill=color)
                L("shape", f"{id}_wifi", shape="arc", startAngle=-45, sweep=90, hole=0, w=size * 1.3, h=size * 1.3, fill=color)
                L("shape", f"{id}_battery", w=size * 1.45, h=size * 0.62, radius=size * 0.2, fill=color)
        return g

    def nav_bar(title, id=None, w=None, y=None, x=None, h=None, back=None, action=None, color=INK, muted=MUTED, size=None,
                apart=False):
        """A screen's title row: an optional back label left and action word right over a big title."""
        id = id or auto("nav")
        u = unit()
        h = h or 96 * u
        size = size or h * 0.34
        g = block("column", id, x, y, w, h, apart, padding_x=24 * u, padding_y=10 * u, justify="end", gap=6 * u)
        with g:
            if back or action:
                with L("group", f"{id}_top", layout="row", justify="between" if back else "end", padding=0):
                    if back:
                        say(f"{id}_back", "‹ " + back, size * 0.5, muted)
                    if action:
                        say(f"{id}_action", action, size * 0.5, muted)
            say(f"{id}_title", title, size, color, weight=760)
        return g

    def tab_bar(labels, id=None, w=None, y=None, x=None, h=None, active=0, fill=PAPER, color=MUTED, accent=ACCENT, line=LINE,
                apart=False):
        """Tabs evenly across a bar, each an icon square and a label; `active` in the accent colour. In a column it
        sits at the bottom: a spacer (`<id>_push`, grow 1) made before it takes the room left."""
        id = id or auto("tabs")
        h = h or 84 * unit()
        if in_layout(build) and not apart:
            L("group", f"{id}_push", w=0, h=0, grow=1)
        g = block("column", id, x, y, w, h, apart, bg=fill)
        with g:
            L("shape", f"{id}_line", w="fill", h=1, fill=line)
            with L("group", f"{id}_tabs", layout="row", w="fill", grow=1, align="center", padding=0, gap=0):
                for i, lab in enumerate(labels):
                    c = accent if i == active else color
                    with L("group", f"{id}_tab{i}", layout="column", grow=1, align="center", gap=h * 0.08, padding=0):
                        L("shape", f"{id}_icon{i}", w=h * 0.26, h=h * 0.26, radius=h * 0.07, fill=c,
                          filled=i == active, stroke=i != active, strokeColor=c, strokeWidth=2.5)
                        say(f"{id}_label{i}", lab, h * 0.15, c, weight=600 if i == active else 500)
        return g

    def list_rows(rows, id=None, x=None, y=None, w=None, row_h=None, avatar=True, color=INK, muted=MUTED, line=LINE,
                  accent=ACCENT, size=None, pad=None, apart=False):
        """One row a container (`<id>_r0` …): an avatar with the title's first letter, the title, a detail line under
        it, a value on the right, a divider. A row is a string, (title, detail) or (title, detail, value).
        Returns the row groups, top first (stagger them in; layer.stagger orders by place); .group too."""
        id = id or auto("list")
        u = unit()
        row_h = row_h or 72 * u
        size = size or row_h * 0.27
        pad = pad if pad is not None else 22 * u
        made = U.Rows()
        with block("column", id, x, y, w, None, apart) as made.group:
            for i, row in enumerate(rows):
                title, detail, value = (tuple([row]) if isinstance(row, str) else tuple(row)) + (None,) * (3 - (1 if isinstance(row, str) else len(row)))
                with L("group", f"{id}_r{i}", layout="column", w="fill", h=row_h, padding=0, gap=0) as r:
                    with L("group", f"{id}_r{i}_main", layout="row", w="fill", grow=1, align="center", padding_x=pad,
                           padding_y=0, gap=pad * 0.6):
                        if avatar:
                            d = row_h * 0.56
                            with L("group", f"{id}_r{i}_badge", layout="stack", w=d, h=d, align="center", justify="center", padding=0):
                                L("shape", f"{id}_r{i}_avatar", shape="ellipse", w=d, h=d, fill=accent, fillOpacity=0.14)
                                say(f"{id}_r{i}_initial", str(title)[:1].upper(), d * 0.42, accent, weight=700)
                        with L("group", f"{id}_r{i}_words", layout="column", grow=1, gap=size * 0.2, padding=0):
                            say(f"{id}_r{i}_title", title, size, color, weight=620)
                            if detail:
                                say(f"{id}_r{i}_detail", detail, size * 0.78, muted, weight=450)
                        if value is not None:
                            say(f"{id}_r{i}_value", value, size, color, weight=650)
                    L("shape", f"{id}_r{i}_line", w="fill", h=1, fill=line)
                made.append(r)
        return made

    def card(id, x=None, y=None, w=None, h=None, title=None, detail=None, value=None, fill=PAPER, color=INK, muted=MUTED,
             radius=None, shadow=True, pad=None, size=None, apart=False):
        """A rounded card (`<id>_bg`, filling the card) with an optional title and detail at its top and a big value
        at its bottom (`<id>_body`, a padded column: make more of the card's layers inside `with layer("<id>_body")`);
        `shadow` adds a soft drop shadow. Left out, h fits what is inside."""
        u = unit()
        pad = pad if pad is not None else 20 * u
        size = size or (min(float(h) * 0.13, 30 * u) if isinstance(h, (int, float)) else 22 * u)
        g = block("stack", id, x, y, w, h, apart, align="stretch", justify="start")
        with g:
            bg = L("shape", f"{id}_bg", w="fill", h="fill", radius=24 * u if radius is None else radius, fill=fill)
            if shadow:
                bg.effect("shadow", f"{id}_shadow", dy=size * 0.5, radius=size * 1.4, strength=0.22)
            with L("group", f"{id}_body", layout="column", w="fill", h="fill" if h is not None else "fit", padding=pad,
                   gap=size * 0.5, justify="between"):
                if title or detail:
                    with L("group", f"{id}_head", layout="column", gap=size * 0.3, padding=0):
                        if title:
                            say(f"{id}_title", title, size, color, weight=650)
                        if detail:
                            say(f"{id}_detail", detail, size * 0.78, muted, weight=450)
                if value is not None:
                    say(f"{id}_value", value, size * 2, color, weight=760)
        return g

    def button(label, id=None, x=None, y=None, w=None, h=None, fill=ACCENT, color="#ffffff", radius=None, size=None,
               outline=False, apart=False):
        """A button: a pill (`<id>_bg`) with its label centred (`<id>_label`); `outline` draws only its edge."""
        id = id or auto("button")
        h = float(h or 56 * unit())
        g = block("stack", id, x, y, w, h, apart, align="center", justify="center")
        with g:
            L("shape", f"{id}_bg", w="fill", h="fill", radius=h / 2 if radius is None else radius, fill=fill,
              filled=not outline, stroke=outline, strokeColor=fill, strokeWidth=3)
            say(f"{id}_label", label, size or h * 0.32, fill if outline else color, weight=650)
        return g

    def toggle(id=None, x=None, y=None, on=False, w=None, h=None, label=None, detail=None, on_color="#22c55e",
               off_color="#d1d5db", knob="#ffffff", color=INK, muted=MUTED, apart=False):
        """A switch: the track (`<id>_track`) and the knob (`<id>_knob`). To flip it, key the knob's x (from h/2 to
        w - h/2) and the track's fill. With `label` (and `detail`) it is a settings row, full width: the words on the
        left, the switch (`<id>_switch`) on the right."""
        id = id or auto("toggle")
        u = unit()
        w, h = float(w or 52 * u), float(h or 32 * u)
        if not label:
            g = sw = block(None, id, x, y, w, h, apart)
        else:
            g = block("row", id, x, y, None, h * (2.2 if detail else 1.6), apart, align="center", padding_x=22 * u, gap=12 * u)
            with g:
                with L("group", f"{id}_words", layout="column", grow=1, gap=4 * u, padding=0):
                    say(f"{id}_label", label, 17 * u, color, weight=600)
                    if detail:
                        say(f"{id}_detail", detail, 13 * u, muted, weight=450)
                sw = L("group", f"{id}_switch", w=w, h=h, origin="top-left")
        with sw:                            # a plain group: the knob is keyed by its x
            L("shape", f"{id}_track", x=w / 2, y=h / 2, w=w, h=h, radius=h / 2, fill=on_color if on else off_color)
            L("shape", f"{id}_knob", shape="ellipse", x=w - h / 2 if on else h / 2, y=h / 2, w=h * 0.82, h=h * 0.82, fill=knob)
        return g

    def bars(values, id=None, x=None, y=None, w=None, h=None, color=ACCENT, gap=0.35, top=None, radius=None, labels=None,
             label_color=MUTED, size=None, apart=False):
        """A bar chart: one bar per value, standing on the chart's floor (origin bottom-center, so a key on `scaleY`
        from 0 grows it upward), heights to `top` (default the biggest value), `gap` the share of each slot left
        empty. `labels` go under the bars. Returns the bar shapes, left first; .group too."""
        id = id or auto("bars")
        u = unit()
        size = size or 13 * u
        lab = size * 1.8 if labels else 0.0
        h = float(h or 140 * u)
        top = float(top or max(values) or 1)
        made = U.Rows()
        with block("row", id, x, y, w, h, apart, align="stretch") as made.group:
            for i, v in enumerate(values):
                with L("group", f"{id}_slot{i}", layout="column", grow=1, align="center", justify="end", padding=0, gap=0):
                    bh = max((h - lab) * float(v) / top, 0.0)
                    made.append(L("shape", f"{id}_{i}", w=f"{round((1 - gap) * 100, 4)}%", h=bh, origin="bottom-center",
                                  radius=size * 0.6 if radius is None else radius, fill=color))
                    if labels and i < len(labels):
                        with L("group", f"{id}_under{i}", layout="row", h=lab, align="center", padding=0):
                            say(f"{id}_label{i}", labels[i], size, label_color)
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
