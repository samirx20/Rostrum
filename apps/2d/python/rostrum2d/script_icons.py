"""icon(...) in a script: a Lucide or Tabler icon by name (rostrum_core.byname) as layers you can animate: a group
`size` px square holding the icon's paths (each a path layer: trimEnd draws it on, strokeColor / fill recolour it).

    icon("arrow-right", size=96, color="#fff", x=300, y=200)
    icon("tabler:heart-filled", id="like", size=64, color="#e5484d")

`color` is the icon's currentColor (its strokes, or its fills for a filled icon); `stroke_width` in the icon's own
24 px units (Lucide and Tabler draw at 2). Any other field is the group's. A name no set has fails, naming the
five nearest."""
from __future__ import annotations

from rostrum_core.byname import icon_paths

from . import fields as F, pathdata


def for_script(build) -> dict:
    L = build.layer
    path = pathdata.for_script(L)["path"]                  # d read as SVG reads it, in the icon's box

    def icon(name: str, id=None, size: float = 24, color=None, stroke_width: float | None = None, **fields):
        """The icon as a group of path layers; returns the group."""
        parts = icon_paths(name)
        color = color if color is not None else F.defaults("text")["color"]
        outer = L("group", id, w=size, h=size, **fields)
        with outer:
            with L("group", None, w=24, h=24, scale=size / 24):        # the icon's own 24 px box, scaled to `size`
                for p in parts:
                    path(None, d=p["d"], fill=color if p["fill"] else "none", stroke=p["stroke"],
                         strokeColor=color, strokeWidth=stroke_width if stroke_width is not None else p["stroke_width"],
                         cap="round", join="round")
        return outer

    return {"icon": icon}
