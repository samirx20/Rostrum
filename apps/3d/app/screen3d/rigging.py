"""Rigs from the Camera flyout (SPEC §8 Rigs): Orbit, Turntable, Crane, Dolly and Handheld put the camera on a rig in
one step through `rig.wrap` (rostrum3d/ops_rigs.py), the operation agents use. The camera is the selected one, else
the shot camera. An orbit or a turntable then waits for a click on what it circles (the item there, else the point
on the ground); crane, dolly and handheld start at once, running the way the camera looks. A turntable also keys one
full turn over the shot the screen shows. Offered only while that camera is not on a rig already.
"""
from __future__ import annotations

from rostrum_core.tree import index
from rostrum3d.kind import KIND

# {flyout choice: (name, rig kind, needs a click, handheld)}
RIGS = {"rig:orbit": ("Orbit", "orbit", True, False), "rig:turntable": ("Turntable", "orbit", True, False),
        "rig:crane": ("Crane", "crane", False, False), "rig:dolly": ("Dolly", "dolly", False, False),
        "rig:handheld": ("Handheld", "dolly", False, True)}


def camera_of(b) -> str:
    """The camera a rig choice puts on a rig: the selected camera, else the one the shot looks through."""
    sel = b.selected and b.doc.has(b.selected) and b.doc.item(b.selected)
    return sel["id"] if sel and sel["type"] == "camera" else b.shot_info()["camera"]


def on_a_rig(b, cam: str) -> bool:
    loc = index(b.doc.data, KIND.lists).get(cam)
    return bool(loc and loc.parent != "root" and b.doc.item(loc.parent)["type"] == "rig")


def entries(b) -> list[dict]:
    """The flyout's rig rows: absent while the camera rides a rig (its Rig setting changes the kind then)."""
    if on_a_rig(b, camera_of(b)):
        return []
    return [{"value": v, "name": name, "icon": "rig"} for v, (name, *_rest) in RIGS.items()]


def needs_click(choice: str) -> bool:
    return RIGS[choice][2]


def wrap(adder, choice: str, hit: dict | None = None):
    """Put the camera on the `choice` rig; `hit` = the click ({point, item}) an orbit circles. One undo step; the rig
    is selected so its settings (Distance, Angle …) show."""
    b, (name, kind, _click, handheld) = adder.b, RIGS[choice]
    args = {"kind": kind, "name": f"{name} rig"}
    if handheld:
        args["handheld"] = True
    if hit:
        args.update({"around": hit["item"]} if hit.get("item") else {"point": list(hit["point"])})
    if choice == "rig:turntable":
        args["turn"] = b.shot_id
    before = {i["id"] for i in b.doc.items()}
    adder._apply([{"op": "rig.wrap", "target": [camera_of(b)], "args": args}], f"Put the camera on {name.lower()}", "")
    made = [i["id"] for i in b.doc.items() if i["id"] not in before and i.get("type") == "rig"]
    if made:
        b.select(made[0])
