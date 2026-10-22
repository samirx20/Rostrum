"""The eases a person picks (UX_SPEC 3.18, INTERACTION 1.5 point 6), in the one order the key bar's Ease ▾, a key's
right-click and the action list (F9, Shift+F9, Ctrl+Shift+F9, Ctrl+Alt+J) all read. `value` is the key's `ease` in the
document; `job` the shared key map job, if it has a key. The document's other eases (snappy, natural, heavy, ease in
and out, bounce) still show by their own names when a key has one."""
from __future__ import annotations

from rostrum_core.keys import BEZIERS

EASES = [
    {"value": "linear", "label": "Linear", "job": ""},
    {"value": "easeIn", "label": "Ease in", "job": "ease_in"},
    {"value": "easeOut", "label": "Ease out", "job": "ease_out"},
    {"value": "smooth", "label": "Smooth", "job": "smooth"},
    {"value": "spring", "label": "Spring", "job": ""},
    {"value": "hold", "label": "Jump", "job": "jump"},
    {"value": "custom", "label": "Custom", "job": ""},
]
OTHER = {"snappy": "Snappy", "natural": "Natural", "heavy": "Heavy", "easeInOut": "Ease in and out", "bounce": "Bounce"}


def label_of(ease: str) -> str:
    return next((e["label"] for e in EASES if e["value"] == ease), OTHER.get(ease, ease))


def shape_of(ease: str) -> str:
    """The tiny mark drawn on the bar between two keys: "line" (linear), "step" (jump) or "curve" (anything eased)."""
    return {"linear": "line", "hold": "step"}.get(ease, "curve")


def handles(key: dict) -> list[float]:
    """[x1, y1, x2, y2] the small curve shows and drags: a cubic's own numbers; linear is the diagonal; others (spring,
    jump, bounce) start a custom curve from Smooth's."""
    ease = key.get("ease", "smooth")
    if ease == "custom":
        return [key.get(n, d) for n, d in zip(("x1", "y1", "x2", "y2"), (0.25, 0.1, 0.25, 1.0))]
    if ease == "linear":
        return [0.0, 0.0, 1.0, 1.0]
    return list(BEZIERS.get(ease, BEZIERS["smooth"]))
