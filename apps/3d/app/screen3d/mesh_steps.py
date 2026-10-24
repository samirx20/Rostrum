"""Scripted Edit mesh steps (steps.py hands every `mesh-…` word here), each the same call a key or click makes:

    mesh-tab (Tab: in / out) | mesh-edit (the panel's Edit: mesh.edit) | mesh-kind points|edges|faces (1 2 3)
    mesh-pick <selector …> (pick by the operations' words: top, faces 3 4, points 0 1, all)
    mesh-box <x0> <y0> <x1> <y1> (a box dragged in the viewport, in parts of it, 0..1)
    mesh-action extrude|inset | mesh-number <distance|width|depth> <mm> (typed under the last action)
    mesh-arrow <mm> (the extrude arrow dragged to that distance and let go)
"""
from __future__ import annotations


def do(bridge, word, rest):
    me = bridge.viewport.mesh_edit
    if word == "mesh-tab":
        me.toggle()
    elif word == "mesh-edit":
        me.convert()
    elif word == "mesh-kind":
        me.setKind(rest[0])
    elif word == "mesh-pick":
        me.select_text(" ".join(rest))
    elif word == "mesh-box":
        me.boxSelect(*map(float, rest[:4]), False)
    elif word == "mesh-action":
        me.runAction(rest[0])
    elif word == "mesh-number":
        me.setNumber(rest[0], float(rest[1]))
    elif word == "mesh-arrow":
        if not me.arrow_shown():
            raise RuntimeError("mesh-arrow: no extrude arrow (pick faces and run Extrude first)")
        me._nums["extrude"]["distance"] = float(rest[0])
        me._again()
    else:
        raise ValueError(f"unknown step {word!r}")
    if bridge.status.startswith("Error"):
        raise RuntimeError(f"step {word}: {bridge.status}")
