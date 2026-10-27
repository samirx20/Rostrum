"""A material's numbers and colours drawn live (brief 22): dragging Lines' width (or any number or colour of a material)
sends the window's own view one light `material` request per pointer move (ENGINE_CONTRACT.md § 4: it rewrites that
material's shaders on the stage it holds, no new scene), the newest replacing one still waiting (copies_live.Live);
the document changes once, when the pointer lets go (one undo step, the field's own material.set). Used by the settings
panel with a material selected (copies_live.Scrubs) and by a material's rows inline under its item (materials.py).

Where the view can't (an older build, the Final look: Cycles draws in the engine program, not in the window), the drag
previews each move in the document as it always did.
"""
from __future__ import annotations

from rostrum3d import fields as F
from rostrum3d.material_fields import DOC_ONLY
from rostrum3d.material_scene import prop_out

from .copies_live import Live, available

REFUSED = [False]                      # the view refused a `material` request once (an older build): every drag previews
LIVE_TYPES = {"number", "color"}


def ok(bridge, param: str) -> bool:
    """A drag of this material field can be drawn live in the window's view now."""
    p = next((q for q in F.FIELDS["material"] if q.name == param), None)
    vp = getattr(bridge, "viewport", None)
    return (p is not None and p.type in LIVE_TYPES and param not in DOC_ONLY and not REFUSED[0]
            and available(bridge) and getattr(vp, "look", "quick") != "final")


def request(material: str, param: str, value) -> dict:
    """The live request: the material's one changed field, in the scene's own units (a colour linear, as compiled)."""
    return {"material": {"id": material, "props": {param: prop_out(param, value)}}}


class Drag:
    """One live drag of one material field: `send(value)` per move; `end()` the value to write (None: nothing to
    write) and, on Esc (`cancel`), the view put back to the value at the press."""

    def __init__(self, bridge, material: str, param: str, start, refused):
        self.material, self.param, self.start, self.value = material, param, start, None
        self.live = Live(bridge.viewport.link, refused)

    def send(self, value):
        self.value = value
        self.live.post(request(self.material, self.param, value))

    def end(self, cancel: bool = False):
        self.live.drop_waiting()
        if self.value is None or self.value == self.start:
            return None
        if cancel:
            self.live.post(request(self.material, self.param, self.start))
            return None
        return self.value
