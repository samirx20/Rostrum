"""The arrangement picture: one row per track across time (notes as bars placed by pitch inside the row, drum hits
as ticks, one lane per drum, clips as boxes, spoken lines as flags). Shade and thickness show each note's written
level (velocity × the fader, its automation included); the left column names the track, its median level and the
range it spans (highest note at the row's top edge, lowest at the bottom, or its drums by lane). Along the top:
sections, markers (their lines drawn under the parts), bar numbers and the chord symbols; seconds along the bottom.

Drawn with Pillow (already loaded by the MCP layer), not matplotlib: the first look in a fresh server is under a second.
"""
from __future__ import annotations

from PIL import Image, ImageDraw, ImageFont

from .arrangement import db, levels
from .draw_clash import PALETTE

W, GUTTER, PAD = 1600, 176, 12
BG, GRID, TEXT, DIM, MARK = (255, 255, 255), (226, 229, 236), (40, 44, 52), (120, 126, 140), (209, 54, 47)
SECTION = [(238, 241, 246), (246, 247, 250)]
LO_DB, HI_DB = -30.0, 6.0          # the shade scale: -30 dB and quieter palest, +6 dB and louder full colour
_FONTS: dict[int, ImageFont.FreeTypeFont] = {}


def _font(size: int):
    if size not in _FONTS:
        _FONTS[size] = ImageFont.load_default(size=size)
    return _FONTS[size]


def _rgb(hex_: str) -> tuple[int, int, int]:
    return tuple(int(hex_[i:i + 2], 16) for i in (1, 3, 5))


def _amount(level: float) -> float:
    """0 … 1 along the shade scale."""
    return min(max((db(level) - LO_DB) / (HI_DB - LO_DB), 0.0), 1.0)


def _shade(col, a: float):
    k = 0.18 + 0.82 * a
    return tuple(round(255 + (c - 255) * k) for c in col)


def _db_text(v: float) -> str:
    v = round(v)
    return "0 dB" if v == 0 else f"{v:+d} dB"


def _fit(text: str, font, width: float) -> str:
    if font.getlength(text) <= width:
        return text
    while text and font.getlength(text + "…") > width:
        text = text[:-1]
    return text + "…" if text else ""


def _lanes(items: list[tuple[float, float]], gap: float = 6) -> list[int]:
    """A lane for each (left, right) span so labels in one lane never overlap (greedy, in order of left)."""
    ends: list[float] = []
    out = [0] * len(items)
    for i in sorted(range(len(items)), key=lambda i: items[i][0]):
        l, r = items[i]
        lane = next((k for k, e in enumerate(ends) if l >= e + gap), len(ends))
        if lane < len(ends):
            ends[lane] = r
        else:
            ends.append(r)
        out[i] = lane
    return out


def _step(span: float, px: float, min_px: float) -> float:
    for s in (0.5, 1, 2, 5, 10, 15, 20, 30, 60, 120, 300, 600):
        if s * px / span >= min_px:
            return s
    return 1200


def arrangement_picture(png, arr: dict, start: float = 0.0, end: float | None = None, title: str = "arrangement",
                        chords: list | None = None):
    """`chords`: [[start_s, end_s, symbol]] drawn as a row under the bar numbers (ears/bar_text.py), when given."""
    end = arr["end"] if end is None else end
    end = end if end > start else start + 1.0
    rows = arr["tracks"]
    n = max(len(rows), 1)
    row_h = 84 if n <= 6 else max(52, min(84, 900 // n))
    f9, f10, f11, f12, f14 = _font(10), _font(11), _font(12), _font(13), _font(16)
    x0, x1 = GUTTER, W - PAD
    X = lambda t: x0 + (t - start) * (x1 - x0) / (end - start)
    inside = lambda t: start - 1e-6 <= t <= end + 1e-6

    # top band: title, key line, sections, markers (as many lanes as their labels need), bar numbers
    marks = [(name, at) for name, at in arr["markers"] if inside(at)]
    mlabels = [f"{name} {at:.2f}s" for name, at in marks]
    mspans = [(X(at) + 3, X(at) + 3 + f11.getlength(lab)) for (_, at), lab in zip(marks, mlabels)]
    mlane = _lanes(mspans)
    n_mlanes = max(mlane, default=-1) + 1
    y_title = PAD
    y_key = y_title + 22
    y_sec = y_key + 22
    y_mark = y_sec + 20
    y_bar = y_mark + 16 * n_mlanes + 2
    y_chord = y_bar + 16
    y_rows = y_chord + (18 if chords else 2)
    y_axis = y_rows + row_h * len(rows)
    H = y_axis + 30
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)

    d.text((PAD, y_title), title, fill=TEXT, font=f14)
    d.text((PAD, y_key), "shade and thickness: each note's level (velocity x fader, automation included), "
           f"pale {LO_DB:.0f} dB … full {HI_DB:+.0f} dB.  Left: median level in dB, highest note at the row's top, "
           "lowest at its bottom.  Red: markers.", fill=DIM, font=f10)

    # sections: shaded across the band and the rows, name at the start
    for k, (name, s, e) in enumerate(arr["sections"]):
        if e <= start or s >= end:
            continue
        a, b = X(max(s, start)), X(min(e, end))
        d.rectangle([a, y_sec, b, y_axis], fill=SECTION[k % 2])
        d.line([a, y_sec, a, y_axis], fill=(205, 210, 222))
        d.text((a + 4, y_sec + 2), _fit(name, f11, b - a - 8), fill=(70, 76, 96), font=f11)

    # bar lines and numbers (every bar, or every 2nd/4th … when they would crowd)
    bars = arr["bars"]
    vis = [(i + 1, b) for i, b in enumerate(bars) if inside(b)]
    every = 1
    if len(vis) > 1:
        gap = (X(vis[-1][1]) - X(vis[0][1])) / (len(vis) - 1)
        while gap * every < f9.getlength(str(len(bars))) + 10:
            every *= 2
    d.text((PAD, y_bar + 1), "bar", fill=DIM, font=f9)
    for num, b in vis:
        x = X(b)
        d.line([x, y_bar + 14, x, y_axis], fill=GRID)
        if (num - 1) % every == 0 and num <= arr.get("bar_count", len(bars)) + 1:
            lab = str(num)
            tx = min(max(x - f9.getlength(lab) / 2, x0), x1 - f9.getlength(lab))
            d.text((tx, y_bar + 1), lab, fill=DIM, font=f9)

    # chord symbols: a tick at every change, the name in full where it has room after the last one written
    # (the bar_by_bar text names every one)
    if chords:
        d.text((PAD, y_chord + 1), "chords", fill=DIM, font=f9)
        free = x0
        for s, e, lab in chords:
            if e <= start or s >= end:
                continue
            a = X(max(s, start))
            if a >= free - 4:                           # never through a name already written
                d.line([a, y_chord + 2, a, y_chord + 13], fill=DIM)
            if a + 3 >= free:
                text = _fit(lab, f11, x1 - a - 3)
                d.text((a + 3, y_chord + 1), text, fill=TEXT, font=f11)
                free = a + 3 + f11.getlength(text) + 6

    # markers: the line under the parts (a hit on the marker stays visible), the label in the top band
    for (name, at), lab, lane in zip(marks, mlabels, mlane):
        x = X(at)
        d.line([x, y_mark + 16 * lane, x, y_axis], fill=MARK, width=2)
        d.text((x + 3, y_mark + 16 * lane), _fit(lab, f11, x1 - x - 4), fill=MARK, font=f11)

    # rows
    for r, t in enumerate(rows):
        col = _rgb(PALETTE[r % len(PALETTE)])
        top, bot = y_rows + r * row_h, y_rows + (r + 1) * row_h
        d.line([PAD, bot, x1, bot], fill=GRID)
        lv = levels(t, arr.get("key"))
        name = t["id"] + ("  (muted)" if t.get("mute") else "")
        d.text((PAD, top + 4), _fit(name, f12, GUTTER - PAD - 40), fill=col, font=f12)
        info = _db_text(lv["level_db"]) if lv["level_db"] is not None else "silent"
        if t.get("automated"):
            info += " (auto)"
        d.text((PAD, top + 21), info, fill=TEXT, font=f10)
        area_top, area_bot = top + 7, bot - 7

        ms = [nt[2] for nt in t["notes"]]
        if ms:
            lo, hi = min(ms), max(ms)
            span = max(hi - lo, 12)
            pad_lo = lo - (span - (hi - lo)) / 2
            Y = lambda m: area_bot - (m - pad_lo) / span * (area_bot - area_top)
            reg = lv["register"]
            hx = GUTTER - 6
            d.text((hx - f10.getlength(reg["high"]), Y(hi) - 6), reg["high"], fill=DIM, font=f10)
            if lo != hi:
                d.text((hx - f10.getlength(reg["low"]), Y(lo) - 6), reg["low"], fill=DIM, font=f10)
            for s, e, m, _v, level in t["notes"]:
                if e < start or s > end:
                    continue
                a = _amount(level)
                th = 1.5 + 3.5 * a
                y = Y(m)
                d.rectangle([max(X(s), x0), y - th / 2, max(min(X(e), x1) - 1, max(X(s), x0) + 1), y + th / 2],
                            fill=_shade(col, a))

        drums = lv["drums"]
        if drums:
            lane_h = (area_bot - area_top) / len(drums)
            show = lane_h >= 10 and not ms
            for k, dr in enumerate(drums):
                if show:
                    yc = area_top + lane_h * (k + 0.5)
                    d.text((GUTTER - 6 - f9.getlength(_fit(dr, f9, 70)), yc - 6), _fit(dr, f9, 70), fill=DIM, font=f9)
            if not show:
                d.text((PAD, top + 36), _fit(", ".join(drums), f9, GUTTER - PAD - 6), fill=DIM, font=f9)
            for s, dr, level, _ in t["hits"]:
                if not inside(s):
                    continue
                a = _amount(level)
                yc = area_top + lane_h * (drums.index(dr) + 0.5)
                hh = min(lane_h * 0.45, 2 + 5 * a)
                x = X(s)
                d.rectangle([x, yc - hh, x + (1 if a < 0.6 else 2) + 1, yc + hh], fill=_shade(col, a))

        for s, e, level in t["clips"]:
            if e < start or s > end:
                continue
            a = _amount(level)
            d.rectangle([max(X(s), x0), top + 12, min(X(e), x1), bot - 12], fill=_shade(col, a * 0.35),
                        outline=_shade(col, a), width=2)
        for s, text in t["lines"]:
            if not inside(s):
                continue
            x = X(s)
            yc = (top + bot) / 2
            d.polygon([(x, yc - 5), (x + 7, yc), (x, yc + 5)], fill=col)
            d.text((x + 9, yc - 7), _fit(text, f10, x1 - x - 10), fill=col, font=f10)


    # seconds along the bottom
    d.line([x0, y_axis, x1, y_axis], fill=DIM)
    st = _step(end - start, x1 - x0, 60)
    t0 = (int(start / st) + (start % st > 1e-9)) * st
    k = 0
    while t0 + k * st <= end + 1e-9:
        tt = t0 + k * st
        x = X(tt)
        lab = f"{tt:g}"
        d.line([x, y_axis, x, y_axis + 4], fill=DIM)
        d.text((min(max(x - f10.getlength(lab) / 2, x0), x1 - f10.getlength(lab)), y_axis + 6), lab, fill=DIM, font=f10)
        k += 1
    d.text((PAD, y_axis + 6), "seconds", fill=DIM, font=f10)
    img.save(png, optimize=False, compress_level=3)
    return png
