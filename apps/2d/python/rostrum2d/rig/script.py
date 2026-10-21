"""Script calls for rigs, used inside `with rig(id, w=, h=):` (RIG.md § Operations):

    with rig("puppet", w=600, h=800):
        hip = bone("hip", x=300, y=400, angle=90, length=0)          # a root bone
        thigh = bone("thigh", parent=hip, x=300, y=400, angle=90, length=180)
        shin = bone("shin", parent=thigh, length=170)                # starts at the thigh's tip
        foot = ik("foot_ik", bone=shin, bend="clockwise")            # the target starts at the shin's tip
        foot.key("targetX", {0: 300, 1: 360}).key("pin", {0: 1, 0.5: 0}, ease="hold")
        leg = shape("leg", w=60, h=350, x=300, y=580)                # layers go into the rig
        bind(layer=leg, bone=thigh, bone2=shin)                      # bends across the knee

Bones, iks and binds take an id first, then their fields; another item can stand where an id is wanted. Like
layers they are items with ids, so a re-run merges field by field and key by key.
"""
from __future__ import annotations

from .model import start_bone, start_ik

REFS = ("parent", "bone", "bone2", "layer")


def for_script(build) -> dict:
    def add(type_, key, start, id_, values):
        node = next((h for h in reversed(build.holders) if h["type"] == "rig"), None)
        if node is None:
            raise ValueError(f"{type_}(...) goes inside `with rig(...):`")
        values = {k: getattr(v, "id", v) if k in REFS else v for k, v in values.items()}   # an item can stand for its id
        return build.add(type_, id_, start(node["bones"], values), node[key])

    return {"bone": lambda id=None, **v: add("bone", "bones", start_bone, id, v),
            "ik": lambda id=None, **v: add("ik", "iks", start_ik, id, v),
            "bind": lambda id=None, **v: add("bind", "binds", lambda bones, values: values, id, v)}
