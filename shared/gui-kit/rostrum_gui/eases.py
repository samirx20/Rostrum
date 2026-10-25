"""The eases a person picks, for every app with keys: rows of the ONE list (rostrum_core.keys.easing.EASE_LIST, 2D SPEC
pro-workflows base E) as the kit's EasePicker.qml shows them (the Key block, a key's right-click and the Move view all
read it). `rows(key_of)` adds each ease's key from the app's key map (F9 …); `label_of` names any ease, "Custom" too.
No list of its own: the words, order, keys' jobs and curves are EASE_LIST's."""
from __future__ import annotations

from rostrum_core.keys import BEZIERS
from rostrum_core.keys.easing import EASE_LIST, label_of  # noqa: F401  (the kit's importers)


def rows(key_of=None) -> list[dict]:
    """[{id, label, group, curve, keys}] in EASE_LIST's order; `keys` the job's key in the app's key map ("" without)."""
    return [{"id": e["id"], "label": e["label"], "group": e["group"], "curve": e["curve"],
             "keys": key_of(e["job"]) if key_of and e["job"] else ""} for e in EASE_LIST]


def handles(key: dict) -> list[float]:
    """[x1, y1, x2, y2] the small curve shows and drags: a cubic's own numbers; linear is the diagonal; others (spring,
    hold, bounce) start a custom curve from Smooth's."""
    ease = key.get("ease", "smooth")
    if ease == "custom":
        return [key.get(n, d) for n, d in zip(("x1", "y1", "x2", "y2"), (0.25, 0.1, 0.25, 1.0))]
    if ease == "linear":
        return [0.0, 0.0, 1.0, 1.0]
    return list(BEZIERS.get(ease, BEZIERS["smooth"]))
