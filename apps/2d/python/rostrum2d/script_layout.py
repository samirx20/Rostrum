"""React-like layout in the film script (guide lay-out-a-screen): containers that place and size what is made inside
them, so a screen is written as nested boxes with padding, gap and align instead of x / y sums.

    with column("menu", padding=24, gap=16, w=520):          # h left out: it fits what is inside
        text(body="Trips", size=32, weight=700)
        with row(gap=12, align="center"):
            shape(w=40, h=40, radius=20, fill="#4f46e5")
            text(body="Lisbon dinner", size=18, grow=1)
        with grid(columns=3, gap=12, tw="p-4"):
            ...

`row`, `column`, `grid`, `stack` are `group(..., layout=…)` starting as CSS does (padding 0, gap 0, align stretch;
top-left origin, so x / y outside a container is its top-left). Words every layer call takes (`prepare`, called by
Build.layer for each one): `origin=` (the pivot by name, "top-left" … "bottom-right"), `tw=` (Tailwind layout words,
tw.py; explicit arguments win), and inside a container `grow=`, `shrink=`, `align_self=`, `margin=`, `span=`,
`apart=`, `shift_x=` / `shift_y=`. A group's (or shape's, image's) `w` / `h` take px, "N%", "fill" or (a container)
"fit". The x / y rule: inside a container the layout places a layer, so x= / y= there fail loudly unless the layer is
`apart=True` (then it keeps its own x / y and takes no room: a badge, a pointer).
"""
from __future__ import annotations

from . import tw as TW

ORIGINS = {"center": (0.5, 0.5), "top-left": (0, 0), "top-center": (0.5, 0), "top-right": (1, 0),
           "left-center": (0, 0.5), "right-center": (1, 0.5), "bottom-left": (0, 1), "bottom-center": (0.5, 1),
           "bottom-right": (1, 1)}
CHILD = {"grow": "layoutGrow", "shrink": "layoutShrink", "align_self": "alignSelf", "alignSelf": "alignSelf",
         "margin": "margin", "span": "colSpan", "apart": "layoutApart", "shift_x": "shiftX", "shift_y": "shiftY"}
BOX = {"padding_x": "paddingX", "padding_y": "paddingY", "row_gap": "rowGap", "radius": "bgRadius"}
RESIZABLE = ("group", "shape", "image")
KINDS = ("row", "column", "grid", "stack")
START = {"padding": 0, "gap": 0, "align": "stretch"}       # a container starts as CSS does: no padding or gap, stretched


def in_layout(build) -> bool:
    """Layers made now go into a container (a group with a layout)."""
    h = build.holders[-1] if build.holders else {}
    return h.get("type") == "group" and h.get("layout", "none") != "none"


def _size(type_, axis, v, out, where):
    """w / h: px, "N%", "fill" or "fit" -> the field and its size mode."""
    A = axis.upper()
    if not isinstance(v, str) or type_ not in RESIZABLE:
        if type_ in RESIZABLE:
            out[f"size{A}"] = "fixed"
        out[axis] = v
    elif v.endswith("%"):
        out[f"size{A}"], out[f"pct{A}"] = "percent", float(v[:-1])
    elif v in ("fill", "fit") and (v == "fill" or type_ == "group"):
        out[f"size{A}"] = v
    else:
        raise ValueError(f'{where}: {axis}="{v}" is not a size; write px (320), a share of the parent ("50%"), "fill"'
                         + (' or "fit" (hug what is inside)' if type_ == "group" else ""))


def prepare(build, type_: str, id_, values: dict) -> dict:
    """A layer call's arguments with the layout words turned into its fields."""
    where = f'{type_}("{id_}")' if id_ else f"{type_}(…)"
    values = {**TW.read(values.pop("tw")), **values} if "tw" in values else dict(values)
    inside = in_layout(build)
    out: dict = {}
    for k, v in values.items():
        if k == "origin":
            if v not in ORIGINS:
                raise ValueError(f'{where}: origin "{v}" is not one of {", ".join(ORIGINS)}')
            out["anchorX"], out["anchorY"] = ORIGINS[v]
        elif k in CHILD:
            if not inside and k != "apart":
                raise ValueError(f"{where}: {k}= places a layer in a container; it is not inside one. Make it inside "
                                 "`with row(…)` / column / grid / stack (or a device's screen)")
            out[CHILD[k]] = v
        elif k in ("w", "h", "width", "height"):
            _size(type_, k[0], v, out, where)
        elif type_ == "group" and k == "overflow":
            if v not in ("visible", "hidden"):
                raise ValueError(f'{where}: overflow "{v}" is not one of visible, hidden')
            out["clip"] = v == "hidden"
        elif type_ == "group" and k == "bg":
            out["background"], out["bgColor"] = True, v
        elif type_ == "group" and k == "columns" and isinstance(v, str):
            out["columnsTemplate"] = v
        elif type_ == "group" and k in BOX:
            out[BOX[k]] = v
        else:
            out[k] = v
    if inside and not out.get("layoutApart") and {"x", "y"} & set(out):
        raise ValueError(f"{where}: x= / y= inside a container: the layout places this layer. Leave x / y out (use "
                         "align, justify, gap, margin; shift_x= / shift_y= to move it off its place without pushing the "
                         "others), or give apart=True to place it by its own x / y (it then takes no room)")
    return out


def for_script(build) -> dict:
    def container(kind):
        def make(id=None, **values):
            if "tw" in values:
                values = {**TW.read(values.pop("tw")), **values}
            values = {**START, **values, "layout": kind}
            if not {"origin", "anchorX", "anchorY"} & set(values):
                values["origin"] = "top-left"
            return build.layer("group", id, **values)
        make.__name__ = kind
        make.__doc__ = (f"A group laid out as a {kind}: padding, gap, align, justify, wrap, w / h (px, \"N%\", "
                        "\"fill\", \"fit\" — left out: fit), bg, radius, overflow, tw; `with` it to make its layers.")
        return make
    return {k: container(k) for k in KINDS}
