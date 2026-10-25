"""Scripted steps for a painting opened on its own (painting_open.py); each is the call a click or key makes.

    paintingopen <painting id>     the Library's Open (the row's ↗ button): the painting alone, the brush on
    paintingclose                  the path chip's scene name (back to the scene, picking and tool as they were)
    paintinguse <layer id>         Used by › that layer: back with it picked
    opentime <painting id> [n] [profile]
                                   what opening it from the Library (its Open) and closing it again cost the screen's
                                   thread, n times each (default 6): rostrum_gui/select_steps.py `cost`
"""
from __future__ import annotations

WORDS = ("paintingopen", "paintingclose", "paintinguse", "opentime")


def do_open_step(bridge, word, rest, step):
    if word == "opentime":
        from rostrum_gui.select_steps import cost, print_profile, said
        n = int(next((a for a in rest[1:] if a.isdigit()), 6))
        got = cost([("open", lambda: bridge.library.paintings.open(rest[0])), ("close", bridge.opened.close)], n, "profile" in rest)
        if bridge.opened.id:
            raise RuntimeError(f"step {step!r}: the painting stayed open: {bridge.status}")
        for label in ("open", "close"):
            print(said(f"opentime {rest[0]} {label}", got[label]))
        if "profile" in got:
            print_profile(got["profile"])
    elif word == "paintingopen":
        bridge.opened.open(rest[0])
        if bridge.opened.id != rest[0]:
            raise RuntimeError(f"step {step!r}: the painting didn't open: {bridge.status}")
    elif word == "paintingclose":
        bridge.opened.close()
    else:
        bridge.opened.goToUse(rest[0])
