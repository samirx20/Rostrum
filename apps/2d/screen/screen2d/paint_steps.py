"""Scripted steps for painting's panel and Fill (steps.py hands these over); each goes through the calls a click makes.

    fill <x> <y>                     G (Fill on), click at (x, y) (composition px); fails like the click (status)
    fillmode on|off | gap small|medium|large     Fill on / off (G) | Close gaps
    paintpick <paint id>             click a paint layer's name: strokes and fills go on it
    paintset <paint id> visible|opacity|mode|name|locked <json value>    its eye, Opacity, Blend, rename, Lock
    paintmove <paint id> <row>       drag it to that row of the list (0 = top) | paintremove <paint id> (right-click › Delete)
    painttoggle <field> on|off       Inside the outline (paintInside), Draw each frame (eachFrame); a painted fill
                                     painted in place: its painting's Seamless (seamless)
    preset <id> | painttool brush|eraser|fill|pick|select | brushedit on|off    a brush in the brush panel | its top
                                     row | Edit brush › / ‹ Back
    savebrush <name with _ for spaces>   + Save this brush, the name typed, Enter (My brushes)
    keytap <key> [shift|alt|ctrl]    a real key press in the window ("[", "]", "E", "Ctrl+Z" as `keytap z ctrl`)
    depthtyped <depth> [open|cancel]  Set depth ▾ › Other depth…, type the number, Enter (open: leave the popover open)
"""
from __future__ import annotations
from rostrum_gui.pointer import wait  # never QTest.qWait: it starves the worker threads

import json

WORDS = ("fill", "fillmode", "gap", "paintpick", "paintset", "paintmove", "paintremove", "painttoggle", "depthtyped",
         "preset", "painttool", "brushedit", "keytap", "savebrush")
MODS = {"shift": "ShiftModifier", "alt": "AltModifier", "ctrl": "ControlModifier"}


def keytap(win, key: str, mods: list[str]):
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest
    m = Qt.KeyboardModifier.NoModifier
    for w in mods:
        m |= getattr(Qt.KeyboardModifier, MODS[w])
    code = {"[": Qt.Key.Key_BracketLeft, "]": Qt.Key.Key_BracketRight, ",": Qt.Key.Key_Comma, ".": Qt.Key.Key_Period}.get(key) or getattr(Qt.Key, "Key_" + (key.upper() if len(key) == 1 else key.capitalize()))
    QTest.keyClick(win, code, m)
    wait(50)


def do_paint_step(bridge, word, rest, step, win=None):
    fill, layers = bridge.fill, bridge.paintLayers
    if word == "preset":
        bridge.painter.setPreset(rest[0])
    elif word == "painttool":
        bridge.paintTool.use(rest[0])
    elif word == "brushedit":
        bridge.painter.setEditing(rest[0] == "on")
    elif word == "keytap":
        keytap(win, rest[0], rest[1:])
    elif word == "savebrush":
        if not bridge.painter.saveBrush(" ".join(rest).replace("_", " ")):
            raise RuntimeError(f"step {step!r}: {bridge.status}")
    elif word == "fill":
        fill.setOn(True)
        if not fill.fillAt(float(rest[0]), float(rest[1])):
            raise RuntimeError(f"step {step!r}: {bridge.status}")
    elif word == "fillmode":
        fill.setOn(rest[0] == "on")
    elif word == "gap":
        fill.setGap(rest[0])
    elif word == "paintpick":
        layers.pick(rest[0])
    elif word == "paintset":
        layers.setLayer(rest[0], rest[1], json.loads(" ".join(rest[2:])))
    elif word == "paintmove":
        layers.moveTo(rest[0], int(rest[1]))
    elif word == "paintremove":
        layers.remove(rest[0])
    elif word == "depthtyped":
        dt = bridge.depthTyped
        if not bridge.run("layer:depth_typed") or not dt.open:
            raise RuntimeError(f"step {step!r}: Other depth… is not offered here: {bridge.status}")
        dt.setValue(float(rest[0]))
        if rest[1:] != ["open"]:
            dt.cancel() if rest[1:] == ["cancel"] else dt.end()
    elif word == "painttoggle":
        layers.setToggle(rest[0], rest[1] == "on")
