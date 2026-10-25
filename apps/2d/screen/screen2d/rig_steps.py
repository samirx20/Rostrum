"""Scripted steps for characters (steps.py hands these over); each goes through the call the overlay's press-drag-release
or the sheets' clicks make. Bones, chains, poses and drawings are named by id or name (_ for spaces).

    bones                          wait for the engine's posed bones of the rig in hand, then print them and the joints
    jointdrag <bone> pivot|tip <x> <y>    drag that joint circle to (x, y) composition px (fixes it at rest)
    posedrag <bone> <dx> <dy>      press the bone's middle and drag by (dx, dy) composition px (FK turn, or IK pull)
    bonepick <bone>                click a bone (it is picked); `bonepick <bone> ctrl` = Ctrl+click (joins the part picked)
    bonerealclick <bone> [ctrl]    a real mouse click (Ctrl held: `ctrl`) in the window on the bone's middle
    bonerealdrag <bone> <dx> <dy>  a real mouse press, slow drag and release from the bone's middle, by (dx, dy) composition px
    boneclick <x> <y>              with the Bone tool (J): a click at (x, y) composition px (a joint)
    bonedrag <x0> <y0> <x1> <y1>   with the Bone tool: press at (x0, y0), drag to (x1, y1), let go (one bone)
    bonehover <x> <y>              the pointer over (x, y): the line of the bone a click would make
    boneend                        Esc with the Bone tool: the chain ends (again: back to Move)
    pin <bone> on|off              right-click the chain end at that bone's joint › Pin / Unpin
    posesave | poseapply <pose> | poseblend <pose> <amount>    the Poses list in the settings
    lipsync open|close|apply|start|wait | lipsync snap <png> (start = Apply without waiting; snap = a picture of the window now) | lipsync line <item/line> | lipsync shape <X|A…|H> <drawing|->
    blinks open|close|apply | blinks every <s> | blinks vary <0..1> | blinks pick open|closed|half <drawing|->
"""
from __future__ import annotations
from rostrum_gui.pointer import wait  # never QTest.qWait: it starves the worker threads

import time

from PySide6.QtCore import QCoreApplication

WORDS = ("bones", "jointdrag", "posedrag", "bonepick", "bonerealclick", "bonerealdrag", "boneclick", "bonedrag", "bonehover", "boneend", "pin", "posesave", "poseapply", "poseblend", "lipsync", "blinks")


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
        rig.pickBone(_id(bridge, rest[0], ("bone",)), rest[1:2] == ["ctrl"])
    elif word == "bonerealclick":
        wait_bones(bridge)
        _real_click(bridge, _id(bridge, rest[0], ("bone",)), rest[1:2] == ["ctrl"])
    elif word == "bonerealdrag":
        wait_bones(bridge)
        _real_drag(bridge, _id(bridge, rest[0], ("bone",)), float(rest[1]), float(rest[2]))
    elif word in ("boneclick", "bonedrag", "bonehover", "boneend"):
        _bone_tool(bridge, word, [float(v) for v in rest], step)
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
        elif what == "snap":
            from PySide6.QtGui import QGuiApplication
            if not QGuiApplication.topLevelWindows()[0].grabWindow().save(rest[1]):
                raise RuntimeError(f"step {step!r}: could not save {rest[1]}")
        elif what in ("close", "apply", "start", "wait"):
            if what != "wait":
                getattr(sheet, "apply" if what == "start" else what)()
            if word == "lipsync" and what in ("apply", "wait"):
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


def _bone_tool(bridge, word, xy, step):
    """The Bone tool's press / hover / release, as BoneTool.qml makes them (a joint is caught within 8 screen px at 100 %)."""
    tool, near = bridge.boneTool, 8.0
    if word == "boneend":
        return tool.end() or bridge.setTool("move")
    if bridge.tool != "bone":
        bridge.setTool("bone")
    end = time.time() + 15
    while bridge.rig.place() is None and time.time() < end:        # the rig's place comes from the engine
        bridge.rig.refresh()
        QCoreApplication.processEvents()
        time.sleep(0.02)
    if word == "bonehover":
        return tool.hover(*xy)
    x0, y0, x1, y1 = xy if word == "bonedrag" else (*xy, *xy)
    if not tool.press(x0, y0, near):
        raise RuntimeError(f"step {step!r}: {bridge.status}")
    tool.hover((x0 + x1) / 2, (y0 + y1) / 2)
    tool.release(x1, y1, near)


def _window_point(bridge, bone, dx=0.0, dy=0.0):
    """(window, QPoint) of the bone's middle, moved by (dx, dy) composition px: where a person's pointer would be."""
    from PySide6.QtCore import QObject, QPoint, QPointF
    from PySide6.QtGui import QGuiApplication
    win = next(w for w in QGuiApplication.topLevelWindows() if w.findChild(QObject, "stage"))
    b = next(p for p in bridge.rig.bones if p["id"] == bone)
    stage = win.findChild(QObject, "stage")
    o, k = stage.property("compOrigin"), stage.property("compScale")
    c = stage.mapToScene(QPointF(o.x() + ((b["x"] + b["tipX"]) / 2 + dx) * k, o.y() + ((b["y"] + b["tipY"]) / 2 + dy) * k))
    return win, QPoint(int(c.x()), int(c.y()))


def _real_click(bridge, bone, ctrl):
    """A real press and release from the mouse (QTest) on the bone's middle, as a person's click reaches BoneOverlay.qml."""
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest
    win, p = _window_point(bridge, bone)
    mod = Qt.KeyboardModifier.ControlModifier if ctrl else Qt.KeyboardModifier.NoModifier
    QTest.mouseMove(win, p)
    wait(80)
    QTest.mouseClick(win, Qt.MouseButton.LeftButton, mod, p)
    wait(250)


def _real_drag(bridge, bone, dx, dy):
    """A real press, twenty small moves and a release from the mouse (QTest): the posing drag as a hand makes it."""
    from PySide6.QtCore import QPoint, Qt
    from PySide6.QtTest import QTest
    win, p0 = _window_point(bridge, bone)           # the bone moves while it is posed: the path is made from where it began
    p1 = _window_point(bridge, bone, dx, dy)[1]
    QTest.mouseMove(win, p0)
    wait(80)
    QTest.mousePress(win, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, p0)
    wait(40)
    for k in range(1, 21):
        QTest.mouseMove(win, QPoint(p0.x() + (p1.x() - p0.x()) * k // 20, p0.y() + (p1.y() - p0.y()) * k // 20))
        wait(16)
    QTest.mouseRelease(win, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, p1)
    wait(250)
