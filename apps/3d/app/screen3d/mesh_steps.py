"""Scripted Edit mesh steps (steps.py hands every `mesh-…` word here), each the same call a key or click makes:

    mesh-tab (Tab: in / out) | mesh-edit (the panel's Edit: mesh.edit) | mesh-kind points|edges|faces (1 2 3)
    mesh-pick <selector …> (pick by the operations' words: top, faces 3 4, points 0 1, all)
    mesh-box <x0> <y0> <x1> <y1> (a box dragged in the viewport, in parts of it, 0..1)
    mesh-action extrude|inset|bevel|loopcut|sharp|unsharp | mesh-number <distance|width|depth|segments|count|slide> <n>
    (typed under the last action; mm, or a plain number for segments, count, slide)
    mesh-arrow <mm> (the grip of Extrude or Bevel dragged to that number and let go)
    mesh-material <material id, or - for the shape's own> (the picked faces take it)
    mesh-xray (Alt+Z) | mesh-knife (K) | mesh-knife-at <x> <y> (a click, parts of the viewport) | mesh-knife-apply | mesh-esc
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
            raise RuntimeError("mesh-arrow: no arrow (pick faces and run Extrude, or edges and run Bevel, first)")
        me._nums[me._last["name"]][me._grip()[0]] = float(rest[0])
        me._again()
    elif word == "mesh-material":
        me.setFaceMaterial("" if rest[0] == "-" else rest[0])
    elif word == "mesh-xray":
        me.toggleXray()
    elif word == "mesh-knife":
        me.toggleKnife()
    elif word == "mesh-knife-at":
        me.knifeAt(float(rest[0]), float(rest[1]))
    elif word == "mesh-knife-apply":
        me.knifeApply()
    elif word == "mesh-esc":
        me.escape()
    else:
        raise ValueError(f"unknown step {word!r}")
    if bridge.status.startswith("Error"):
        raise RuntimeError(f"step {word}: {bridge.status}")
