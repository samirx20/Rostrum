"""Scripted steps for a painting opened on its own (painting_open.py); each is the call a click or key makes.

    paintingopen <painting id>     the Library's double-click (Open): the painting alone, the brush on
    paintingclose                  the path chip's scene name (back to the scene, picking and tool as they were)
    paintinguse <layer id>         Used by › that layer: back with it picked
"""
from __future__ import annotations

WORDS = ("paintingopen", "paintingclose", "paintinguse")


def do_open_step(bridge, word, rest, step):
    if word == "paintingopen":
        bridge.opened.open(rest[0])
        if bridge.opened.id != rest[0]:
            raise RuntimeError(f"step {step!r}: the painting didn't open: {bridge.status}")
    elif word == "paintingclose":
        bridge.opened.close()
    else:
        bridge.opened.goToUse(rest[0])
