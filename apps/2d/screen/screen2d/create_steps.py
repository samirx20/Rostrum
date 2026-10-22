"""Scripted steps for the creation tools (steps.py hands these over); each goes through the calls the mouse and keys make.

    shape <rect|ellipse> x0 y0 x1 y1 [shift] [alt]   press at (x0, y0), drag to (x1, y1), let go (composition px)
    shapedrag <rect|ellipse> x0 y0 x1 y1 [shift] [alt]   the same, held before letting go (for a picture of the live outline)
    shapeend x1 y1 [shift] [alt]                     let go of a shapedrag
    text <x> <y> <words…>                            T, click at (x, y), type, Esc (_ for spaces, | for a new line)
    textbox <x0> <y0> <x1> <y1> <words…>             T, drag a box, type, Esc
    typetext <x> <y> <words…>                        the same, but typing is not ended (for a picture of the cursor)
    edittext <layer> <words…>                        double-click the text, replace all of it, Esc
    endtext                                          Esc
"""
from __future__ import annotations

WORDS = ("shape", "shapedrag", "shapeend", "text", "textbox", "typetext", "edittext", "endtext")
SLOP = 4.0


def _words(rest) -> str:
    return " ".join(rest).replace("|", "\n")


def _typed(c, body):
    for i in range(1, len(body) + 1):                       # key by key, as typing is
        c.typeText(body[:i])


def do_create_step(bridge, word, rest, step):
    c = bridge.create
    flags = [w for w in rest if w in ("shift", "alt")]
    rest = [w for w in rest if w not in ("shift", "alt")]
    shift, alt = "shift" in flags, "alt" in flags
    if word in ("shape", "shapedrag"):
        kind, x0, y0, x1, y1 = rest[0], *map(float, rest[1:5])
        bridge.setTool(kind)
        c.beginShape(kind, x0, y0, SLOP)
        c.dragShape(x1, y1, shift, alt)
        if word == "shape":
            c.endShape(x1, y1, shift, alt)
    elif word == "shapeend":
        c.endShape(float(rest[0]), float(rest[1]), shift, alt)
    elif word in ("text", "typetext"):
        bridge.setTool("text")
        c.beginText(float(rest[0]), float(rest[1]), 0)
        _typed(c, _words(rest[2:]).replace("_", " "))
        if word == "text":
            c.commitText(c.body)
    elif word == "textbox":
        x0, y0, x1, y1 = map(float, rest[:4])
        bridge.setTool("text")
        c.beginText(min(x0, x1), min(y0, y1), abs(x1 - x0))
        _typed(c, _words(rest[4:]).replace("_", " "))
        c.commitText(c.body)
    elif word == "edittext":
        c.editText(rest[0])
        _typed(c, _words(rest[1:]).replace("_", " "))
        c.commitText(c.body)
    elif word == "endtext":
        c.commitText(c.body)
