"""A group's own background, like a design tool's frame fill: a colour box (corner radius, optional outline) drawn
behind the group's layers and as big as the group's box. With auto layout and Width / Height hugs layers on, the box
hugs the layers with the layout's Padding all round: a lower-third is one group, a name with a pill around it.

Document-side fields: scene.py hands the engine an ordinary rect shape as the group's first (backmost) layer, sized
and keyed from the group's own w / h (the layout's baked keys included), so it draws through the one render path.
"""
from __future__ import annotations

from rostrum_core import Param

G = "Background"
ON = {"is": ["background", True]}
LINE = {"all": [ON, {"is": ["bgStroke", True]}]}

FIELDS = [
    Param.toggle("background", label="On", group=G, default=False, importance="secondary",
                 help="A colour box behind the group's layers, as big as the group (with auto layout and hugging on, "
                      "it hugs them with the padding: a name on a pill)"),
    Param.color("bgColor", label="Background colour", group=G, default="#1d4ed8", importance="secondary", valid_when=ON),
    Param.number("bgRadius", label="Corner radius", group=G, min=0, max=10000, step=1, unit="px", default=0.0,
                 importance="secondary", valid_when=ON, help="Rounds the box's corners; half its height or more makes a pill"),
    Param.toggle("bgStroke", label="Outline", group=G, default=False, importance="secondary", valid_when=ON),
    Param.color("bgStrokeColor", label="Outline colour", group=G, default="#ffffff", importance="secondary", valid_when=LINE),
    Param.number("bgStrokeWidth", label="Outline width", group=G, min=0, max=1000, step=0.5, unit="px", default=2.0,
                 importance="secondary", valid_when=LINE),
]
NAMES = {p.name for p in FIELDS}
_DEFAULT = {p.name: p.default for p in FIELDS}
_AS_SHAPE = {"bgColor": "fill", "bgRadius": "radius", "bgStroke": "stroke", "bgStrokeColor": "strokeColor",
             "bgStrokeWidth": "strokeWidth"}


def _half(keys: list[dict]) -> list[dict]:
    """The same keys at half the value: the box's centre follows the group's size (eases are linear in the value)."""
    return [{**k, "v": k["v"] / 2} for k in keys]


def node(item: dict, group: dict, keys_of, engine_props) -> dict | None:
    """The background's engine node for the group `item` (None with Background off). `group`: the group's engine node
    (its props and anim, the layout's size keys included); `keys_of(field)`: the group's own keys of a field, as the
    engine reads them; `engine_props(type, given)`: a node's full props (scene.py)."""
    if not item.get("background"):
        return None
    props, anim = group["props"], group.get("anim", {})
    given = {shape: item.get(field, _DEFAULT[field]) for field, shape in _AS_SHAPE.items()}
    w, h = props["w"], props["h"]
    shape = {"id": f'{item["id"]}.background', "type": "shape", "props": engine_props("shape", {
        **given, "shape": "rect", "filled": True, "w": w, "h": h, "x": w / 2, "y": h / 2})}
    own = {"w": anim.get("w"), "h": anim.get("h"), "x": anim.get("w") and _half(anim["w"]),
           "y": anim.get("h") and _half(anim["h"])}
    own.update({shape_f: keys_of(field) for field, shape_f in _AS_SHAPE.items() if keys_of(field)})
    own = {k: v for k, v in own.items() if v}
    if own:
        shape["anim"] = own
    return shape
