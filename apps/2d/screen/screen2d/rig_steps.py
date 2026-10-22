"""Scripted steps for characters (steps.py hands these over); each goes through the call the overlay's press-drag-release
or the sheets' clicks make. Bones, chains, poses and drawings are named by id or name (_ for spaces).

    bones                          wait for the engine's posed bones of the rig in hand, then print them and the joints
    jointdrag <bone> pivot|tip <x> <y>    drag that joint circle to (x, y) composition px (fixes it at rest)
    posedrag <bone> <dx> <dy>      press the bone's middle and drag by (dx, dy) composition px (FK turn, or IK pull)
    bonepick <bone>                click a bone (it is picked)
    pin <bone> on|off              right-click the chain end at that bone's joint › Pin / Unpin
    posesave | poseapply <pose> | poseblend <pose> <amount>    the Poses list in the settings
    lipsync open|close|apply | lipsync line <item/line> | lipsync shape <X|A…|H> <drawing|->
    blinks open|close|apply | blinks every <s> | blinks vary <0..1> | blinks pick open|closed|half <drawing|->
"""
from __future__ import annotations

import time

from PySide6.QtCore import QCoreApplication

WORDS = ("bones", "jointdrag", "posedrag", "bonepick", "pin", "posesave", "poseapply", "poseblend", "lipsync", "blinks")


def _id(bridge, name: str, kinds=None) -> str:
    """An item by id, or by name (_ for spaces); loud when none."""
    words = name.replace("_", " ")
    from rostrum_core.tree import index
    for loc in index(bridge.doc.data, bridge.doc.kind.lists).values():
        it = loc.item
        if (not kinds or it.get("type") in kinds) and name in (it["id"], it.get("name")) or it.get("name") == words                 and (not kinds or it.get("type") in kinds):
            return it["id"]
    if bridge.doc.has(name) and not kinds:
        return name
    raise RuntimeError(f"no item named {name!r}")


def wait_bones(bridge, timeout=15.0):
    rig = bridge.rig
    rig.refresh()
    end = time.time() + timeout
    while time.time() < end:
        QCoreApplication.processEvents()
        if rig.rig and rig.bones and rig._key is not None and rig._key[1] == bridge.time:
            return
        time.sleep(0.02)
    raise RuntimeError("the engine gave no posed bones for the rig in hand" if rig.rig else "no rig in hand (select one)")


def do_rig_step(bridge, word, rest, step):
    rig, drag = bridge.rig, bridge.rig.drag
    if word == "bones":
        wait_bones(bridge)
        print("bones", [(b["name"], round(b["x"]), round(b["y"]), round(b["tipX"]), round(b["tipY"]), b["chain"]) for b in rig.bones])
        print("joints", [(j["bone"], j["end"], round(j["x"]), round(j["y"]), j["ik"], j["pinned"]) for j in rig.joints])
    elif word == "jointdrag":
        wait_bones(bridge)
        bone, end, x, y = _id(bridge, rest[0], ("bone",)), rest[1], float(rest[2]), float(rest[3])
        if not drag.beginJoint(bone, end):
            raise RuntimeError(f"step {step!r}: {bridge.status}")
        drag.moveTo(x, y)
        drag.end()
    elif word == "posedrag":
        wait_bones(bridge)
        bone = _id(bridge, rest[0], ("bone",))
        b = next(p for p in rig.bones if p["id"] == bone)
        x0, y0 = (b["x"] + b["tipX"]) / 2, (b["y"] + b["tipY"]) / 2
        if not drag.beginPose(bone, x0, y0):
            raise RuntimeError(f"step {step!r}: {bridge.status}")
        for k in (0.5, 1.0):
            drag.moveTo(x0 + k * float(rest[1]), y0 + k * float(rest[2]))
        drag.end()
    elif word == "bonepick":
        wait_bones(bridge)
        rig.pickBone(_id(bridge, rest[0], ("bone",)))
    elif word == "pin":
        wait_bones(bridge)
        bone = _id(bridge, rest[0], ("bone",))
        joint = next((j for j in rig.joints if j["bone"] == bone and j["ik"]), None)
        if joint is None:
            raise RuntimeError(f"step {step!r}: {rest[0]} has no chain end to pin")
        drag.pin(joint["ik"], rest[1] == "on")
    elif word == "posesave":
        bridge.poses.save()
    elif word == "poseapply":
        bridge.poses.apply(_id(bridge, rest[0], ("pose",)))
    elif word == "poseblend":
        pose = _id(bridge, rest[0], ("pose",))
        for k in (0.5, 1.0):
            bridge.poses.blendTo(pose, k * float(rest[1]))
        bridge.poses.endBlend()
    elif word in ("lipsync", "blinks"):
        sheet = bridge.lipsync if word == "lipsync" else bridge.blinks
        what = rest[0]
        if what == "open" and not sheet.start():
            raise RuntimeError(f"step {step!r}: {bridge.status}")
        elif what in ("close", "apply"):
            getattr(sheet, what)()
            if word == "lipsync" and what == "apply":
                end = time.time() + 600                  # a line not heard before is listened to first (off the thread)
                while sheet._busy and time.time() < end:
                    QCoreApplication.processEvents()
                    time.sleep(0.05)
                if sheet._busy:
                    raise RuntimeError(f"step {step!r}: still listening to the line after 600 s")
        elif what == "line":
            sheet.pickLine(rest[1])
        elif what == "shape":
            sheet.setShape(rest[1], "" if rest[2] == "-" else _id(bridge, rest[2]))
        elif what == "every":
            sheet.setEvery(float(rest[1]))
        elif what == "vary":
            sheet.setVary(float(rest[1]))
        elif what == "pick":
            sheet.setPick(rest[1], "" if rest[2] == "-" else _id(bridge, rest[2]))
