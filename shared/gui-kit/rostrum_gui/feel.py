"""The critic's feel tools: what a press shows at once, and whether anything moved under the pointer
(the interaction plan's section 3; FEEL.md shows a checker using them). Real input only: `press` is a callable that
does QTest on the window; these tools only watch and grab.

    shot = first_frame(win, lambda: QTest.mousePress(win, Qt.LeftButton, Qt.NoModifier, p))
    shot.image, shot.ms, shot.drew        # the window right after the next frame on screen; ms for info only
    before = positions(win)                # {key: QRectF}: every visible control in window px ("Play#1f3a2b0")
    ... click ...
    moved(before, positions(win))          # [(key, before, after)] for each control whose box moved > 2 px
    s = strip(win, action)                 # feel_strip.py: a grab every 50 ms for 1 s after `action`
    frozen_gaps(s); contact_sheet(s, "strip.png")

A key is the control's objectName (or its QML type) and its object's address, so a button whose words change
("Play" -> "Stop") is still the same key, and two rows with one objectName are two keys.
"""
from __future__ import annotations

import time
from dataclasses import dataclass

from PySide6.QtCore import QRectF

from . import layout_check
from .feel_strip import Strip, contact_sheet, frozen_gaps, strip  # noqa: F401  (the strip tools live there)

FIRST_FRAME_MS = 1000     # a window that draws nothing this long after a press is grabbed anyway (drew=False)


@dataclass
class FirstFrame:
    image: object         # QImage: the window as the next frame after the press showed it
    ms: float             # press start to that frame (wall time: for info, never a budget on a busy machine)
    drew: bool            # False: no frame came within FIRST_FRAME_MS (a window that isn't drawing); grabbed anyway


def first_frame(win, press) -> FirstFrame:
    """Run `press()` (real input), wait for exactly the next frameSwapped of `win`, grab it."""
    from PySide6.QtCore import QEventLoop, QObject, Qt, QTimer
    loop, got = QEventLoop(), []

    def swapped():                                  # (the render thread may send it: the quit is queued to `loop`'s)
        if not got:
            got.append(time.perf_counter())
            QTimer.singleShot(0, loop, loop.quit)

    conn = win.frameSwapped.connect(swapped, Qt.ConnectionType.DirectConnection)
    t0 = time.perf_counter()
    try:
        press()
        win.update()                                # a press that changed nothing still gets its frame
        if not got:
            QTimer.singleShot(FIRST_FRAME_MS, loop, loop.quit)
            loop.exec()
    finally:
        QObject.disconnect(conn)
    image = win.grabWindow()
    if image.isNull():
        raise RuntimeError("first_frame: the window gave no picture")
    return FirstFrame(image, ((got[0] if got else time.perf_counter()) - t0) * 1000, bool(got))


@dataclass
class Spot:
    """One visible control, as the stability pass reads it."""
    key: str
    rect: QRectF          # in the window
    node: object          # layout_check.Node (its item, path, layer, clipper)
    panel: str            # the panel it sits in (layout_stable: "same panel")


def key_of(item) -> str:
    import shiboken6
    name = item.objectName() or layout_check.cls(item).split("_QML")[0].replace("QQuick", "")
    return f"{name}#{shiboken6.getCppPointer(item)[0]:x}"


def panel_of(node, win_area: float) -> str:
    """The outermost clipping ancestor in the node's own layer that is smaller than most of the window (a Panel, the
    settings list, a toolbar, a popup's frame); none: the layer itself."""
    best, p = None, node.parent
    while p is not None and p.layer == node.layer:
        if p.item.clip() and layout_check.area(p.rect) < 0.6 * win_area:
            best = p
        p = p.parent
    return key_of(best.item) if best is not None else f"layer:{node.layer}"


def spots(win) -> dict[str, Spot]:
    """Every visible control of `win` (layout_check.controls: clickables, and lines of text not inside one)."""
    nodes = layout_check.walk(win)
    whole = win.width() * win.height()
    return {key_of(n.item): Spot(key_of(n.item), QRectF(n.rect), n, panel_of(n, whole)) for n in layout_check.controls(nodes)}


def positions(root_or_win, near=None) -> dict[str, QRectF]:
    """{key: QRectF in window px} of every visible control; given an item, only those inside it; given `near` (a QRectF
    or an item), only those touching it."""
    from PySide6.QtQuick import QQuickWindow
    win = root_or_win if isinstance(root_or_win, QQuickWindow) else root_or_win.window()
    got = spots(win)
    if not isinstance(root_or_win, QQuickWindow):
        top = key_of(root_or_win)
        got = {k: s for k, s in got.items() if k == top or any(key_of(a.item) == top for a in layout_check.ancestors(s.node))}
    if near is not None:
        zone = near if isinstance(near, QRectF) else near.mapRectToScene(QRectF(0, 0, near.width(), near.height()))
        got = {k: s for k, s in got.items() if s.rect.intersects(zone)}
    return {k: s.rect for k, s in got.items()}


def shift(a: QRectF, b: QRectF) -> float:
    """The largest edge move between two boxes, px."""
    return max(abs(a.left() - b.left()), abs(a.top() - b.top()), abs(a.right() - b.right()), abs(a.bottom() - b.bottom()))


def moved(before: dict, after: dict, tol: float = 2) -> list[tuple[str, QRectF, QRectF]]:
    """Each control in both whose box moved or resized more than `tol` px (a control gone or new is not "moved")."""
    return [(k, before[k], after[k]) for k in before if k in after and shift(before[k], after[k]) > tol]
