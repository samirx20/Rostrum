"""Cover the frame's move from the screen (2d-camera SPEC §4.12): the ⋯ entry on a scene's own sized, still, not pinned
layer while the frame moves (`background.fit`, the operation an agent calls too), the layers Set depth resizes after it
(pin_depth.depth_calls), and the status line's note after Fill the frame on such a layer: it covers the frame at that
moment only. Plain data and facts read by actions.py and action_rules.py. No Qt.
"""
from __future__ import annotations

from rostrum2d.ops_cover import applies

WHY = ("Cover the frame's move is for a scene's own picture, shape, drawing or group that stays still, while the frame "
       "moves. A pinned layer moves with the frame: use Fill the frame.")


def _comp(doc, id_: str) -> dict | None:
    parent = doc.item(doc.parent_of(id_)[0])
    return parent if parent["type"] == "comp" else None


def targets(doc, ids) -> list[str]:
    """The layers among `ids` Cover the frame's move applies to (ops_cover.applies)."""
    return [i for i in ids if (c := _comp(doc, i)) is not None and applies(doc.item(i), c)]


def applies_to_all(f) -> bool:
    """The fact "cover_ok": every picked layer can take it (the first that can't ends the look)."""
    return bool(f.ids) and all((c := _comp(f.doc, i)) is not None and applies(f.doc.item(i), c) for i in f.ids)


def data(a) -> list[dict]:
    """⋯ Cover the frame's move (made with actions._a)."""
    return [a("cover_move", "Cover the frame's move", rank=67, group="arrange", when={"fact": "cover_ok"},
              calls={"op": "background.fit", "target": "ids", "args": {}}, why=WHY)]


def fill_note(calls: list[dict], label: str, doc) -> str:
    """After Fill the frame on layers the frame's move would leave uncovered: the label and when it covers ("" when not)."""
    c = next((c for c in calls if c["op"] == "layer.fill_frame" and c["args"].get("mode", "cover") == "cover"), None)
    if c is None or not targets(doc, c["target"]):
        return ""
    return f"{label} — covers the frame at {float(c['args'].get('at', 0.0)):.1f} s only; Cover the frame's move covers the whole move"
