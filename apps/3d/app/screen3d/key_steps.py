"""The scripted steps for picked keys on the timeline (steps.py hands the `keys-…` words here).

    keys-stretch <grabbed key id> <frame> <picked key id> …   Alt+drag the grabbed (first or last) picked key to <frame>
    keys-menu <key id>                                        right-click a key: the Ease list
"""
from __future__ import annotations

from PySide6.QtTest import QTest


def do(bridge, win, word, rest):
    fps = bridge.shot_info()["fps"]
    if word == "keys-stretch":
        grab, frame, picked = rest[0], float(rest[1]), rest[2:]
        bridge.keys.click(picked, "", [])
        if not bridge.keys.beginStretch(grab, bridge.doc.item(grab)["t"]):
            raise RuntimeError(f"keys-stretch: {grab} is not the first or last of the picked keys")
        bridge.keys.dragTo(frame / fps, 0.0)
        bridge.keys.endDrag()
    elif word == "keys-menu":
        bridge.keys.click([rest[0]], "", [])
        QTest.qWait(300)
        bridge.keyBar.askMenu(win.width() * 0.5, win.height() - 120)
        QTest.qWait(300)
    else:
        raise RuntimeError(f"unknown step {word!r}")
