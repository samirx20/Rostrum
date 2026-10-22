"""The automatic look check: words cut off or lying on top of each other, in the window as it is now.

Eyes alone miss these at sizes nobody happened to try, so `main.py --look` runs this after the steps (at any
`--size`) and fails when it finds one. It walks the live Qt Quick items, so it checks what is really drawn:

- **cut off**: a text item that elides (`truncated`), is wider than its box without wrapping, runs out of the
  window, or is cut by a clipping parent that is not a scroll area (a list scrolled half a row is fine);
- **covered**: a word whose middle lies under another panel drawn over it (a strip spilling into the next panel);
- **overlap**: two visible words whose drawn boxes cross by more than a couple of pixels.

To share with Rostrum2D it belongs in shared/gui-kit (asked of the kit's owner); it knows nothing of Sound.
"""
from __future__ import annotations

from PySide6.QtCore import QRectF
from PySide6.QtQml import QQmlExpression, qmlContext
from PySide6.QtQuick import QQuickItem

SLACK = 2.0                       # px: anti-aliasing and rounding, not a real overlap
ALIGN_RIGHT, ALIGN_CENTER, ALIGN_BOTTOM, ALIGN_VCENTER = 2, 4, 64, 128


def _is(item, cls: str) -> bool:
    mo = item.metaObject()
    while mo is not None:
        if mo.className() == cls:
            return True
        mo = mo.superClass()
    return False


def _shown(item) -> bool:
    while item is not None:
        if not item.isVisible() or item.opacity() <= 0.01:
            return False
        item = item.parentItem()
    return True


def _aligns(t) -> tuple[int, int]:
    """(horizontal, vertical) alignment as numbers: enum properties can't be read from Python, QML can."""
    got = QQmlExpression(qmlContext(t), t, "[horizontalAlignment, verticalAlignment]").evaluate()[0]
    vals = got.toVariant() if hasattr(got, "toVariant") else got
    return int(vals[0]), int(vals[1])


def _text_rect(t) -> QRectF:
    """The box the words are drawn in (not the whole Text item), in window coordinates."""
    w, h = float(t.width()), float(t.height())
    cw, ch = float(t.property("contentWidth") or 0), float(t.property("contentHeight") or h)
    horizontal, vertical = _aligns(t)
    x = w - cw if horizontal == ALIGN_RIGHT else (w - cw) / 2 if horizontal == ALIGN_CENTER else 0.0
    y = (h - ch) / 2 if vertical == ALIGN_VCENTER else h - ch if vertical == ALIGN_BOTTOM else 0.0
    return t.mapRectToScene(QRectF(x, y, cw, ch))


def _clip_parent(item):
    p = item.parentItem()
    while p is not None:
        if p.clip():
            return p
        p = p.parentItem()
    return None


def _name(t) -> str:
    words = " ".join(str(t.property("text") or "").split())
    return words[:40] + ("…" if len(words) > 40 else "")


def _texts(win):
    out, todo = [], [win.contentItem()]
    while todo:
        item = todo.pop()
        todo.extend(item.childItems())
        if _is(item, "QQuickText") and str(item.property("text") or "").strip() and _shown(item):
            out.append(item)
    return out


def check(win) -> list[str]:
    """Every cut-off or overlapping word in the window, as plain lines; empty when it looks right."""
    problems, boxes = [], []
    bounds = QRectF(0, 0, win.width(), win.height())
    for t in _texts(win):
        r = _text_rect(t)
        clip = _clip_parent(t)
        if clip is not None:
            area = clip.mapRectToScene(QRectF(0, 0, clip.width(), clip.height()))
            scrolls = _is(clip, "QQuickFlickable")
            if not area.intersects(r):
                continue        # scrolled away (lists, and the time views that scroll by moving their content)
            if not scrolls and not area.contains(r.adjusted(SLACK, SLACK, -SLACK, -SLACK)):
                problems.append(f'cut off by its panel: "{_name(t)}" at {r.x():.0f},{r.y():.0f}')
        if t.property("truncated"):
            problems.append(f'shortened with "…": "{_name(t)}" at {r.x():.0f},{r.y():.0f} ({t.width():.0f} px wide)')
        elif int(t.property("lineCount") or 1) == 1 and float(t.property("implicitWidth") or 0) > t.width() + SLACK                 and t.width() > 0:
            problems.append(f'wider than its place: "{_name(t)}" at {r.x():.0f},{r.y():.0f} '
                            f'({t.property("implicitWidth"):.0f} > {t.width():.0f} px)')
        if not bounds.contains(r.adjusted(SLACK, SLACK, -SLACK, -SLACK)):
            problems.append(f'outside the window: "{_name(t)}" at {r.x():.0f},{r.y():.0f}')
        if _covered(win, t, r):
            problems.append(f'covered by another panel: "{_name(t)}" at {r.x():.0f},{r.y():.0f}')
        boxes.append((t, r))
    for i, (a, ra) in enumerate(boxes):
        for b, rb in boxes[i + 1:]:
            cross = ra.intersected(rb)
            if cross.width() > SLACK and cross.height() > SLACK and not _related(a, b):
                problems.append(f'on top of each other: "{_name(a)}" and "{_name(b)}" at {cross.x():.0f},{cross.y():.0f}')
    return problems


def _top_at(item, pt):
    """The topmost item that draws something at a window point; mouse areas and plain containers draw nothing."""
    if not item.isVisible() or item.opacity() <= 0.01:
        return None
    inside = item.contains(item.mapFromScene(pt))
    if item.clip() and not inside:
        return None
    for child in sorted(reversed(item.childItems()), key=lambda c: -c.z()):   # drawn last = on top
        hit = _top_at(child, pt)
        if hit is not None:
            return hit
    return item if inside and item.flags() & QQuickItem.ItemHasContents else None


def _covered(win, t, r: QRectF, owner_levels: int = 3) -> bool:
    """A word whose middle is under something that is not part of its own control (another panel drawn over it)."""
    top = _top_at(win.contentItem(), r.center())
    if top is None:
        return False
    owner = t
    for _ in range(owner_levels):
        owner = owner.parentItem() or owner
    return top is not t and not _related(top, owner) and not _related(top, t)


def _related(a: QQuickItem, b: QQuickItem) -> bool:
    """One inside the other (a label and its own placeholder) is drawn on purpose."""
    for x, y in ((a, b), (b, a)):
        p = x.parentItem()
        while p is not None:
            if p is y:
                return True
            p = p.parentItem()
    return False
