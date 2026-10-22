"""A quick look check of the window as it is drawn: words that run into each other, or are cut off by the window's edge.
No test suite: `main.py --lookcheck` runs it after the steps (and before --shot) at any --size, prints each problem and
exits nonzero. Until the kit's own layout checker (Team Sam, S28) lands, this is how 2D screens are checked at several
window sizes (Sam's ~1646 px wide, 1366, 1280).

What it reads: every visible piece of text (Text, TextInput) in the window, as painted: its painted width, its
alignment, and what its clipping parents (a scrolled list, an elided box) leave visible. Two pieces of text whose
visible parts overlap by more than a pixel or two = a problem; text running past the window's edge = a problem.
A text cut short with "…" is not a problem (it gives way on purpose; its hover shows all of it) but is listed.
"""
from __future__ import annotations

from PySide6.QtCore import QRectF
from PySide6.QtQml import QQmlEngine, QQmlExpression

TEXTS = ("QQuickText", "QQuickTextInput", "QQuickTextEdit")
SLACK = 2.0             # px: anti-aliased edges touching are not an overlap


def _is_text(item) -> bool:
    return any(item.metaObject().className().startswith(t) for t in TEXTS)


def _shown(item) -> bool:
    """Visible and not faded out, up the whole chain."""
    o, it = 1.0, item
    while it is not None:
        if not it.isVisible():
            return False
        o *= it.opacity()
        it = it.parentItem()
    return o > 0.05


def _painted(item) -> QRectF:
    """The text as painted, in window coordinates (an aligned text paints only part of its box)."""
    w, h = item.width(), item.height()
    cw = float(item.property("contentWidth") or w)      # past the box when it overflows (and isn't clipped)
    ch = float(item.property("contentHeight") or h)
    align = int(_read(item, "horizontalAlignment") or 1)
    x = 0.0 if align & 1 or align & 8 else (w - cw if align & 2 else (w - cw) / 2)   # Left/Justify, Right, Center
    valign = int(_read(item, "verticalAlignment") or 32)
    y = 0.0 if valign & 32 else (h - ch if valign & 64 else (h - ch) / 2)            # Top, Bottom, VCenter
    return item.mapRectToScene(QRectF(x, y, cw, ch))


def _read(item, name):
    """An enum property as a number (PySide can't convert QQuickText's own enums through item.property)."""
    ctx = QQmlEngine.contextForObject(item) or QQmlEngine.contextForObject(item.window().contentItem())
    return QQmlExpression(ctx, item, name).evaluate()[0] if ctx else None


def _visible(item, rect: QRectF) -> QRectF:
    """What clipping parents leave of `rect` (an empty rect: scrolled away)."""
    it = item.parentItem()
    while it is not None:
        if it.clip():
            rect = rect.intersected(it.mapRectToScene(it.boundingRect()))
        it = it.parentItem()
    return rect


def _walk(item, out):
    for c in item.childItems():
        if not c.isVisible():
            continue
        ink = c.property("color") if _is_text(c) else None
        if _is_text(c) and str(c.property("text") or "").strip() and _shown(c) and (ink is None or ink.alpha() > 0):
            r = _visible(c, _painted(c))
            if r.width() > 1 and r.height() > 1:
                out.append((c, r))
        _walk(c, out)


def _name(item) -> str:
    return repr(str(item.property("text"))[:40])


def check(win) -> tuple[list[str], list[str]]:
    """(problems, notes) for the window `win` (a QQuickWindow) as it is now."""
    texts: list = []
    _walk(win.contentItem(), texts)
    bounds = QRectF(0, 0, win.width(), win.height())
    problems, notes = [], []
    for i, (a, ra) in enumerate(texts):
        if not bounds.contains(ra.adjusted(SLACK, SLACK, -SLACK, -SLACK)):
            problems.append(f"{_name(a)} runs past the window's edge at {_rect(ra)}")
        if a.property("truncated"):
            notes.append(f"{_name(a)} is cut short with … (hover shows it)")
        for b, rb in texts[i + 1:]:
            hit = ra.intersected(rb)
            if hit.width() > SLACK and hit.height() > SLACK and not _related(a, b) and not _same(a, ra, b, rb):
                problems.append(f"{_name(a)} at {_rect(ra)} overlaps {_name(b)} at {_rect(rb)}")
    return problems, notes


def _related(a, b) -> bool:
    """One text inside the other (a placeholder over its own input box) is drawn there on purpose."""
    def up(x):
        while x is not None:
            yield x
            x = x.parentItem()
    return a in set(up(b.parentItem())) or b in set(up(a.parentItem()))


def _same(a, ra: QRectF, b, rb: QRectF) -> bool:
    """The same words in the same place: one widget's two layers (a number box's text and its edit box), not a clash."""
    near = all(abs(p - q) <= 1 for p, q in zip(ra.getRect(), rb.getRect()))
    return near and a.property("text") == b.property("text")


def _rect(r: QRectF) -> str:
    return f"({r.x():.0f},{r.y():.0f} {r.width():.0f}×{r.height():.0f})"
