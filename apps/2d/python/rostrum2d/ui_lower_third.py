"""lower_third(): a name and a role (job title) on a bar, as plain editable layers (guide lower-thirds-and-charts).

    lower_third("Ada Lovelace", role="Chief engineer", at="#intro+0.2", out="#intro+4")

Made at the top level it sits in the picture's lower-left title-safe area (8 % of the width in, 10 % of the height up;
x= / y= place its bottom-left instead). Made in a container (a device's screen, a column, a stack) the container
places it and it hugs its words. The bar is a column (`<id>`, its background the bar) holding `<id>_name` and
`<id>_role`; `accent=` adds a strip (`<id>_accent`) on its left in a row (`<id>_words` then holds the texts). Sizes come
from the picture's height at the top level, from the container's width inside one; the bar takes the ink of what it
sits on (ui_layout.palette: a dark bar on a light screen, a light one on a dark picture), its words the other way;
every one is a parameter. `at=` slides and fades it in (seconds or "#marker+0.2"), `out=` back
out the same way; without `at=` it is still.
"""
from __future__ import annotations

from contextlib import nullcontext
from math import sqrt

from . import script_time as T, ui_layout as U
from .script_layout import in_layout

ENTER = {"left": (-1, 0), "right": (1, 0), "below": (0, 1), "above": (0, -1), "none": (0, 0)}    # where it comes from


def when(build, value, where):
    """A time as a key takes it: a marker time (checked now, stays on its marker) or seconds."""
    if isinstance(value, str):
        T.seconds(build, value, where)
        return T.Time(value)
    return float(value)


def maker(build, auto):
    L = build.layer

    def lower_third(name, role=None, id=None, x=None, y=None, size=None, role_size=None, bar=None, color=None,
                    muted=None, accent=None, radius=None, pad=None, at=None, out=None, enter="left", slide=None,
                    duration=0.5, ease="easeOut", **layout):
        """A name over a role on a bar. `size` the name's size (role 0.62 of it), `bar` / `color` / `muted` the bar,
        name and role colours, `accent` a strip's colour on the bar's left (none by default), `radius` the bar's
        corners, `pad` the space inside it. `at` / `out`: when it slides in / out, from and back to the `enter` side
        (left, right, below, above; none = only a fade) by `slide` px over `duration` s. Other words (align_self=,
        margin=, …) go to the bar's group. Returns the bar's group."""
        if enter not in ENTER:
            raise ValueError(f'lower_third: enter "{enter}" is not one of {", ".join(ENTER)}')
        on = U.palette(build)                       # the bar in what sits on its ground's ink, its words the other way
        flip = U.DARK if on is U.LIGHT else U.LIGHT
        bar, color, muted = on["ink"] if bar is None else bar, color or flip["ink"], muted or flip["muted"]
        id = id or auto("lower_third")
        inside = in_layout(build)
        pw, ph = U.parent_size(build)
        size = float(size or (18 * sqrt(pw / U.BASE_W) if inside else ph * 0.046))
        role_size = float(role_size or size * 0.62)
        pad = size * 0.55 if pad is None else float(pad)
        place = {"align_self": "start", **layout} if inside else {
            "x": pw * 0.08 if x is None else x, "y": ph * 0.9 if y is None else y, **layout}
        g = L("group", id, layout="row" if accent else "column", origin="bottom-left", hugPin=False, w="fit", h="fit",
              padding_x=pad * 1.4, padding_y=pad, gap=size * (0.5 if accent else 0.12), align="stretch" if accent else "start",
              bg=bar, radius=size * 0.25 if radius is None else radius, **place)
        with g:
            if accent:
                L("shape", f"{id}_accent", w=size * 0.14, h=size * 1.25 + (role_size * 1.3 if role else 0),
                  radius=size * 0.07, fill=accent)
            words = L("group", f"{id}_words", layout="column", gap=size * 0.12, padding=0, align="start") if accent else nullcontext()
            with words:
                L("text", f"{id}_name", body=str(name), size=size, color=color, weight=700)
                if role:
                    L("text", f"{id}_role", body=str(role), size=role_size, color=muted, weight=500)
        if at is not None:
            dx, dy = ENTER[enter]
            far = size * 1.6 if slide is None else float(slide)
            prop = ("shiftX" if dx else "shiftY") if inside else ("x" if dx else "y")
            home = 0.0 if inside else float(place[prop])
            off = home + far * (dx or dy)
            t0 = when(build, at, f"{id} at")
            g.key("opacity", {t0: (0.0, ease), t0 + duration: 1.0})
            if enter != "none":
                g.key(prop, {t0: (off, ease), t0 + duration: home})
            if out is not None:
                t1 = when(build, out, f"{id} out")
                g.key("opacity", {t0: (0.0, ease), t0 + duration: 1.0, t1: (1.0, "easeIn"), t1 + duration: 0.0})
                if enter != "none":
                    g.key(prop, {t0: (off, ease), t0 + duration: home, t1: (home, "easeIn"), t1 + duration: off})
        return g

    return {"lower_third": lower_third}
