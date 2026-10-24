"""look_frame's `onion` option: the same ghosts as the viewport (rostrum3d.onion), drawn by the core's `view` request, the only
one that takes `ghosts` (ENGINE_CONTRACT.md § 4: Quick looks only, renders never). The picture is written as a PNG like a render's."""
from __future__ import annotations

from pathlib import Path

from rostrum_core.errors import RostrumError, codes

from rostrum3d import onion

from . import draw

ONION = {"onion": {"type": "object", "additionalProperties": False, "required": ["item"],
                   "properties": {"item": {"type": "string", "description": "The item whose ghosts to draw (with everything inside it)."},
                                  "mode": {"enum": list(onion.MODES), "default": "keys",
                                           "description": "keys = the item at its previous and next keys; frames = 2 and 4 frames before and after."}},
                   "description": "Onion skin as in the viewport: the item's ghosts at other frames, red before, green after. Quick looks only "
                                  "(fast or stylized, not final); no ghosts are drawn when the item has no other keys or frames to show."}}


def ghosts_of(ctx, doc, info: dict, frame: int, spec: dict, renderer: str) -> list[dict]:
    """The ghosts for look_frame's `onion` (item, mode), or a loud BAD_ARGUMENT."""
    if renderer == "cycles":
        raise RostrumError(codes.BAD_ARGUMENT, ctx.tool, "onion", "onion skin is a quick look: use quality fast or renderer storm / stylized")
    if not doc.has(spec["item"]):
        raise RostrumError.not_found(ctx.tool, "onion item", spec["item"], [i["id"] for i in doc.items()], "the document's items")
    try:
        return onion.ghosts(doc.item(spec["item"]), frame, info, spec.get("mode", "keys"))
    except ValueError as e:
        raise RostrumError(codes.BAD_ARGUMENT, ctx.tool, "onion mode", str(e), list(onion.MODES)) from None


def view_png(where: str, what: str, engine, scene: dict, dest: Path, ghosts: list[dict], **req) -> dict:
    """Draw the quick look with `ghosts` and save it as `dest` (a PNG, like a render's). The reply of the engine's `view`.
    Like a render: no studio light, no selection ring, no contact shading."""
    from PIL import Image
    req = {**req, "ghosts": ghosts, "studio": 0.0, "sceneLights": True, "ao": 0.0, "selected": [], "view": ""}
    view, w, h, stride, reply = draw.call(where, what, engine, scene, "view", **req)
    Image.frombuffer("RGBA", (w, h), bytes(view), "raw", "RGBA", stride, 1).convert("RGB").save(dest)    # copy: the block is reused
    return reply
