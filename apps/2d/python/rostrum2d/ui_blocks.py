"""Script calls that build product screens as plain, editable layers (guide ui-and-product-animation, "Building
blocks"): a device (phone, laptop, browser window) whose screen is a clipped group, and the parts a screen is made
of (status bar, title bar, tab bar, list rows, cards, buttons, toggles, chart bars) plus a counting number.

    scr = device("phone", kind="phone", x=960, y=540)          # the screen group; layer("phone") is the whole device
    with scr:
        status_bar(w=scr.w); nav_bar("Trips", w=scr.w, y=60)
        rows = list_rows([("Lisbon dinner", "4 people", "$168.00"), ("Taxi", "2 people", "$24.50")], y=200, w=scr.w)
        total = counter("total", 0, 186.4, at=2, duration=1.2, decimals=2, prefix="$", x=40, y=640, size=72, align="left")

Each block is a group of shapes and texts with ids made from the block's id (`trips_r0_title`, `pay_label`), placed
by its top-left (x, y) in the parent's px, so it is moved, keyed, restyled or taken apart like anything else. The
colours and sizes given are only a starting point: every one is a parameter. Nothing is animated except `counter`.
"""
from __future__ import annotations

KINDS = ("phone", "laptop", "browser")
INK, MUTED, LINE, PAPER, ACCENT = "#111827", "#6b7280", "#e5e7eb", "#ffffff", "#4f46e5"


def for_script(build) -> dict:
    L = build.layer
    used: dict[str, int] = {}

    def auto(word):                         # block ids when none is given: list, list_2 …
        used[word] = used.get(word, 0) + 1
        return word if used[word] == 1 else f"{word}_{used[word]}"

    def box(id, x, y, w, h, **f):           # a group placed by its top-left, its children in its own px
        return L("group", id, x=x, y=y, w=w, h=h, anchorX=0, anchorY=0, **f)

    def words(id, body, x, y, size, color, align="left", weight=500, **f):
        return L("text", id, body=str(body), x=x, y=y, size=size, color=color, align=align, weight=weight, **f)

    def device(id, kind="phone", x=960, y=540, w=None, h=None, body="#0b0d12", screen=PAPER, radius=None, url="app.example.com"):
        """A device drawn from plain shapes, centred on (x, y). Returns its screen: a clipped group (rounded by a mask)
        whose px start at the screen's top-left; make the screen's layers inside `with` it."""
        if kind not in KINDS:
            raise ValueError(f'device {id}: kind "{kind}" is not one of {", ".join(KINDS)}')
        size = {"phone": (430, 900), "laptop": (1240, 800), "browser": (1280, 800)}[kind]
        w, h = float(w or size[0]), float(h or size[1])
        outer = L("group", id, x=x, y=y, w=w, h=h)
        with outer:
            if kind == "phone":
                bez = round(w * 0.033)
                r = radius if radius is not None else w * 0.15
                L("shape", f"{id}_body", x=w / 2, y=h / 2, w=w, h=h, radius=r, fill=body)
                sx, sy, sw, sh, sr = bez, bez, w - 2 * bez, h - 2 * bez, max(r - bez, 0)
            elif kind == "laptop":
                lid = h * 0.93
                r = radius if radius is not None else 26
                L("shape", f"{id}_body", x=w / 2, y=lid / 2, w=w * 0.9, h=lid, radius=r, fill=body)
                L("shape", f"{id}_base", x=w / 2, y=lid + (h - lid) / 2, w=w, h=h - lid, radius=(h - lid) / 2, fill=body, fillOpacity=0.85)
                L("shape", f"{id}_lip", x=w / 2, y=lid + (h - lid) * 0.3, w=w * 0.14, h=(h - lid) * 0.35, radius=(h - lid) * 0.2, fill="#000000", fillOpacity=0.35)
                bez = w * 0.02
                sx, sy, sw, sh, sr = w * 0.05 + bez, bez, w * 0.9 - 2 * bez, lid - 2.4 * bez, 6
            else:
                bar = 56
                r = radius if radius is not None else 16
                L("shape", f"{id}_body", x=w / 2, y=h / 2, w=w, h=h, radius=r, fill=body)
                for i, c in enumerate(("#ff5f57", "#febc2e", "#28c840")):
                    L("shape", f"{id}_dot{i}", shape="ellipse", x=26 + i * 24, y=bar / 2, w=13, h=13, fill=c)
                L("shape", f"{id}_address", x=w / 2, y=bar / 2, w=w * 0.42, h=32, radius=16, fill="#ffffff", fillOpacity=0.12)
                words(f"{id}_url", url, w / 2, bar / 2, 16, "#ffffff", align="center", weight=450, opacity=0.7)
                sx, sy, sw, sh, sr = 0, bar, w, h - bar, 0
            scr = box(f"{id}_screen", sx, sy, sw, sh, clip=True)
            if sr:
                scr.mask(f"{id}_screen_round", x=0, y=0, w=sw, h=sh, radius=sr)
            with scr:
                L("shape", f"{id}_screen_bg", x=sw / 2, y=sh / 2, w=sw, h=sh, fill=screen)
            if kind == "phone":
                L("shape", f"{id}_island", x=w / 2, y=bez + sw * 0.05, w=sw * 0.3, h=sw * 0.085, radius=sw * 0.05, fill="#000000")
            elif kind == "laptop":
                L("shape", f"{id}_camera", shape="ellipse", x=w / 2, y=bez / 2, w=6, h=6, fill="#2a2f3a")
        return scr

    def status_bar(id=None, w=390, y=0, x=0, time="9:41", color=INK, h=54, size=None):
        """Time on the left, signal, Wi-Fi and battery on the right."""
        id = id or auto("status")
        size = size or h * 0.36
        g = box(id, x, y, w, h)
        with g:
            words(f"{id}_time", time, w * 0.09, h * 0.55, size, color, weight=650)
            rx = w * 0.91
            L("shape", f"{id}_battery", x=rx - 14, y=h * 0.55, w=28, h=size * 0.62, radius=4, fill=color)
            L("shape", f"{id}_wifi", shape="arc", startAngle=-45, sweep=90, hole=0, x=rx - 46, y=h * 0.55 + size * 0.3, w=size * 1.3, h=size * 1.3, fill=color)
            for i in range(4):
                bh = size * (0.3 + 0.18 * i)
                L("shape", f"{id}_signal{i}", x=rx - 86 + i * 7, y=h * 0.55 + (size * 0.84 - bh) / 2 - size * 0.12, w=4.5, h=bh, radius=1.5, fill=color)
        return g

    def nav_bar(title, id=None, w=390, y=54, x=0, h=110, back=None, action=None, color=INK, muted=MUTED, size=None):
        """A screen's title row: an optional back label left, a big title, an optional action word right."""
        id = id or auto("nav")
        size = size or h * 0.36
        g = box(id, x, y, w, h)
        with g:
            if back:
                words(f"{id}_back", "‹ " + back, w * 0.06, h * 0.2, size * 0.5, muted)
            if action:
                words(f"{id}_action", action, w * 0.94, h * 0.2, size * 0.5, muted, align="right")
            words(f"{id}_title", title, w * 0.06, h * 0.62, size, color, weight=760)
        return g

    def tab_bar(labels, id=None, w=390, y=None, x=0, h=96, active=0, fill=PAPER, color=MUTED, accent=ACCENT, line=LINE, parent_h=None):
        """Tabs evenly across the bottom (y = its top; default the bottom of a screen `parent_h` tall), each an icon
        square and a label; `active` is drawn in the accent colour."""
        id = id or auto("tabs")
        if y is None:
            if parent_h is None:
                raise ValueError("tab_bar: give y (its top) or parent_h (the screen's height: it sits at the bottom)")
            y = parent_h - h
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

    def list_rows(rows, id=None, x=0, y=0, w=390, row_h=84, avatar=True, color=INK, muted=MUTED, line=LINE,
                  accent=ACCENT, size=None, pad=None):
        """One row a group (`<id>_r0` …): an avatar with the title's first letter, the title, a detail line under it,
        a value on the right, a divider. A row is a string, (title, detail) or (title, detail, value).
        Returns the row groups, top first (stagger them in; layer.stagger orders by place)."""
        id = id or auto("list")
        size = size or row_h * 0.27
        pad = pad if pad is not None else w * 0.06
        made = []
        with box(id, x, y, w, row_h * len(rows)):
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

    def card(id, x=0, y=0, w=340, h=200, title=None, detail=None, value=None, fill=PAPER, color=INK, muted=MUTED,
             radius=28, shadow=True, pad=None, size=None):
        """A rounded card (`<id>_bg`) with an optional title and detail at its top-left and a big value at its
        bottom-left; `shadow` adds a soft drop shadow effect. Make more of the card's layers inside `with` it."""
        pad = pad if pad is not None else min(w, h) * 0.12
        size = size or min(h * 0.13, 34)
        g = box(id, x, y, w, h)
        with g:
            bg = L("shape", f"{id}_bg", x=w / 2, y=h / 2, w=w, h=h, radius=radius, fill=fill)
            if shadow:
                bg.effect("shadow", f"{id}_shadow", dy=h * 0.06, radius=h * 0.18, strength=0.22)
            if title:
                words(f"{id}_title", title, pad, pad + size * 0.6, size, color, weight=650)
            if detail:
                words(f"{id}_detail", detail, pad, pad + size * 1.75, size * 0.78, muted, weight=450)
            if value is not None:
                words(f"{id}_value", value, pad, h - pad - size * 0.9, size * 2, color, weight=760)
        return g

    def button(label, id=None, x=0, y=0, w=320, h=88, fill=ACCENT, color="#ffffff", radius=None, size=None, outline=False):
        """A button: a pill (`<id>_bg`) with its label centred (`<id>_label`); `outline` draws only its edge."""
        id = id or auto("button")
        g = box(id, x, y, w, h)
        with g:
            L("shape", f"{id}_bg", x=w / 2, y=h / 2, w=w, h=h, radius=h / 2 if radius is None else radius, fill=fill,
              filled=not outline, stroke=outline, strokeColor=fill, strokeWidth=3)
            words(f"{id}_label", label, w / 2, h / 2, size or h * 0.32, fill if outline else color, align="center", weight=650)
        return g

    def toggle(id=None, x=0, y=0, on=False, w=84, h=48, on_color="#22c55e", off_color="#d1d5db", knob="#ffffff"):
        """A switch: the track (`<id>_track`) and the knob (`<id>_knob`). To flip it, key the knob's x (from
        h/2 to w - h/2) and the track's fill."""
        id = id or auto("toggle")
        g = box(id, x, y, w, h)
        with g:
            L("shape", f"{id}_track", x=w / 2, y=h / 2, w=w, h=h, radius=h / 2, fill=on_color if on else off_color)
            L("shape", f"{id}_knob", shape="ellipse", x=w - h / 2 if on else h / 2, y=h / 2, w=h * 0.82, h=h * 0.82, fill=knob)
        return g

    def bars(values, id=None, x=0, y=0, w=320, h=180, color=ACCENT, gap=0.35, top=None, radius=None, labels=None,
             label_color=MUTED, size=None):
        """A bar chart: one bar per value, standing on the box's bottom edge (anchored there, so a key on `scaleY`
        from 0 grows it upward), heights to `top` (default the biggest value). `labels` go under the bars.
        Returns the bar shapes, left first."""
        id = id or auto("bars")
        n = max(len(values), 1)
        top = float(top or max(values) or 1)
        slot = w / n
        bw = slot * (1 - gap)
        made = []
        with box(id, x, y, w, h):
            for i, v in enumerate(values):
                bh = max(h * float(v) / top, 0.0)
                made.append(L("shape", f"{id}_{i}", x=slot * (i + 0.5), y=h, w=bw, h=bh, anchorY=1,
                              radius=bw * 0.18 if radius is None else radius, fill=color))
                if labels and i < len(labels):
                    words(f"{id}_label{i}", labels[i], slot * (i + 0.5), h + (size or 16) * 1.2, size or 16, label_color, align="center")
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

    return {"device": device, "status_bar": status_bar, "nav_bar": nav_bar, "tab_bar": tab_bar, "list_rows": list_rows,
            "card": card, "button": button, "toggle": toggle, "bars": bars, "counter": counter}
