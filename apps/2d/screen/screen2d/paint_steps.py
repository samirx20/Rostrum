"""Scripted steps for painting's panel and Fill (steps.py hands these over); each goes through the calls a click makes.

    fill <x> <y>                     G (Fill on), click at (x, y) (composition px); fails like the click (status)
    fillmode on|off | gap small|medium|large     Fill on / off (G) | Close gaps
    paintpick <paint id>             click a paint layer's name: strokes and fills go on it
    paintset <paint id> visible|opacity|mode|name <json value>    its eye, Opacity, Blend
    paintmove <paint id> <row>       drag it to that row of the list (0 = top) | paintremove <paint id> (right-click › Delete)
    painttoggle <field> on|off       Keep inside the outline (paintInside), Draw each frame (eachFrame)
"""
from __future__ import annotations

import json

WORDS = ("fill", "fillmode", "gap", "paintpick", "paintset", "paintmove", "paintremove", "painttoggle")


def do_paint_step(bridge, word, rest, step):
    fill, layers = bridge.fill, bridge.paintLayers
    if word == "fill":
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
    elif word == "painttoggle":
        layers.setToggle(rest[0], rest[1] == "on")
