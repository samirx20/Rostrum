"""The words agents and people write by habit (CSS, SVG, other animation tools) for the script layer, in one table each:

- FIELDS: a habit word -> the real field it means. Taken only where it is unambiguous: the item type has no field of
  that name and has the real one (a comp's `width` is its own field; a shape's `width` is `w`).
- ON_WITH_COLOUR / FILL: a colour given to an on/off field (`stroke="#fff"`) turns it on and sets its colour field;
  `fill="none"` / `fill=None` turns a fill off.
- CHOICES: a habit word for a choice value (`shape="circle"`).
- NOT_A_FIELD / NOT_A_NAME: words that are no field (or no script name) anywhere, with the line to write instead, for
  the error. Nothing here is guessed silently: what isn't in the first three tables still fails loudly.

Script layer only; operations, files and screens use the real names.
"""
from __future__ import annotations

FIELDS = {
    "width": ("w",), "height": ("h",), "text": ("body",), "content": ("body",), "fontSize": ("size",),
    "fontWeight": ("weight",), "fontFamily": ("font",), "borderRadius": ("radius",), "cornerRadius": ("radius",),
    "rotate": ("rotation",), "steps": ("timing",), "letterSpacing": ("tracking",),
    "textAlign": ("align",), "strokeWeight": ("strokeWidth",), "lineWidth": ("strokeWidth",),
    "backgroundColor": ("background", "bgColor"), "backgroundColour": ("background", "bgColor"),
    "color": ("fill",), "colour": ("color", "fill"), "fill": ("color",), "fillColor": ("fill", "color"),
    "strokeColour": ("strokeColor",), "stroke_color": ("strokeColor",), "stroke_width": ("strokeWidth",),
    "offsetX": ("dx",), "offsetY": ("dy",), "url": ("src",), "file": ("src",),
}
BY_TYPE = {"shadow": {"blur": "radius"}, "glow": {"blur": "radius"}}   # words that mean a field on one type only
ON_WITH_COLOUR = {"stroke": "strokeColor", "background": "bgColor", "bgStroke": "bgStrokeColor"}
FILL = ("fill", "filled")                      # fill=None / "none" / False -> filled=False
NO_FILL = (None, False, "none", "transparent")    # and a fully see-through colour, "#rrggbb00" / "#rgb0" (no_fill)
CHOICES = {"shape": {"circle": "ellipse", "oval": "ellipse", "rectangle": "rect"},
           "align": {"middle": "center", "centre": "center"}}

_KEY = 'key it with .key("x", {0: 100, 1: 500}) and .key("y", {...})'
NOT_A_FIELD = {
    "position": f"x and y are two fields: x=…, y=… (to animate, {_KEY})",
    "pos": f"x and y are two fields: x=…, y=… (to animate, {_KEY})",
    "delay": "start the keys later: .key(\"opacity\", {0.5: 0, 0.8: 1}); letter by letter: letterDelay",
    "duration": "a layer is on screen from start= to end= (seconds); a move lasts from one key's time to the next",
    "ease": "ease is an argument of .key(): .key(\"x\", {0: 0, 1: 500}, ease=\"easeOut\")",
    "easing": "ease is an argument of .key(): .key(\"x\", {0: 0, 1: 500}, ease=\"easeOut\")",
    "zIndex": "layers draw in the order they are made: the last made is on top",
    "visible": "hidden=True hides a layer; opacity=0 makes it see-through",
    "parent": "make layers inside `with group(\"id\", …):` to put them in a group",
    "mask": "item.mask(id, x=, y=, w=, h=) cuts a layer to a box; matte=\"id\" shows it through a layer beside it",
    "shadow": "item.effect(\"shadow\", dy=10, radius=30, strength=0.3)",
    "gradient": "item.effect(\"gradient\", color1=\"#fff\", color2=\"#f75\", angle=90), or fillType=\"linear\" on a shape",
    "scaleXY": "scale= (both), or scaleX= / scaleY=",
}
NOT_A_NAME = {
    "rect": 'shape(id, shape="rect", w=…, h=…, radius=…)', "rectangle": 'shape(id, shape="rect", w=…, h=…)',
    "ellipse": 'shape(id, shape="ellipse", w=…, h=…)', "circle": 'shape(id, shape="ellipse", w=…, h=…)',
    "line": 'path(id, d="M 100 500 L 900 500", filled=False, stroke="#fff", strokeWidth=4), or shape(id, shape="line")',
    "label": 'text(id, body="…", size=…)', "title": 'text(id, body="…", size=…)',
    "animate": 'item.key(field, {time: value}, ease="easeOut")', "keyframe": 'item.key(field, {time: value})',
    "keyframes": 'item.key(field, {time: value})', "interpolate": 'item.key(field, {time: value})',
    "spring": 'a key\'s ease: item.key("scale", {0: 0, 0.6: 1}, ease="spring")',
    "marker": 'a key time names a shared marker: item.key("opacity", {"#beat-0.3": 0, "#beat": 1})',
    "layer": "shape / text / image / path / group(id, **fields)", "svg": 'path(id, d="M … Z")',
    "print": "nothing: a script has nowhere to print. See what it made with inspect_item, look_motion or look_frame",
}


def resolve(type_: str, values: dict, known: list[str], kind_of) -> dict:
    """`values` with habit words replaced by the real fields of a `type_` item (`known`: its fields; `kind_of(name)`:
    a field's type). A word that maps to two real names given at once is refused."""
    out: dict = {}
    for k, v in values.items():
        k = field(k, known, type_)
        if k in ON_WITH_COLOUR and k in known and kind_of(k) == "toggle" and isinstance(v, str) and ON_WITH_COLOUR[k] in known:
            _put(out, k, True)
            k = ON_WITH_COLOUR[k]
        elif k == FILL[0] and FILL[1] in known and kind_of(k) == "color" and (v is True or no_fill(v)):
            k, v = FILL[1], v is True
        elif k in CHOICES and isinstance(v, str):
            v = CHOICES[k].get(v.lower(), v)
        _put(out, k, v)
    return out


def no_fill(v) -> bool:
    """None, False, "none", "transparent", or a colour with alpha 0 ("#00000000", "#0000"): no fill at all."""
    if isinstance(v, str) and v.startswith("#") and len(v) in (5, 9):
        return v[-2:] == "00" if len(v) == 9 else v[-1] == "0"
    return v in NO_FILL


def field(name: str, known: list[str], type_: str = "") -> str:
    """The real field `name` means on a `type_` item with fields `known` (itself when it is one, or not a habit word)."""
    if name in known:
        return name
    if name in BY_TYPE.get(type_, {}):
        return BY_TYPE[type_][name]
    return next((real for real in FIELDS.get(name, ()) if real in known), name)


def _put(out, k, v):
    if k in out and out[k] != v:
        raise ValueError(f'"{k}" is given twice (once under another name); give it once')
    out[k] = v


def not_a_field(name: str) -> str:
    return f" ({NOT_A_FIELD[name]})" if name in NOT_A_FIELD else ""
