"""What a timeline row draws of an item's animations (rostrum_core.keys.animations, in the app's names), for every
app's rows (2D: screen2d/outline.py, 3D: screen3d/outline.py) and the kit's StretchBand.qml. No Qt."""
from __future__ import annotations

from . import eases


def stretches(owner_id: str, anims: list[dict]) -> list[dict]:
    """The clickable stretches of these animations, as the track draws them: from key to key, with the tooltip words
    ("Position · 1.00 → 2.00 s · Ease out"). A Hold moves nothing: drawn and picked as nothing."""
    out = []
    for a in anims:
        for s in a["stretches"]:
            if s["ease"] == "hold":
                continue
            end = s["start"] + s["length"]
            words = eases.label_of(s["ease"])
            out.append({"owner": owner_id, "ids": s["ids"], "endIds": s["endIds"], "t0": s["start"], "t1": end,
                        "tip": f'{a["label"]} · {s["start"]:.2f} → {end:.2f} s · {words}'})
    return out
