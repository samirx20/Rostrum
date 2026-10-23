"""The automatic layout check: walks a live window's item tree and lists every layout fault a person would see.

    faults = check(win)                     # [Fault]: kind, item path, where (window px), what
    layout_mark.mark(win, faults, "out.png")  # the window's picture with each fault boxed and numbered

What counts as a fault (AGENTS.md › Rules: every look pass runs it, at several real window sizes):
  overlap   two visible controls in the same layer cross each other (a popup over the page is another layer; a small
            control wholly inside a much bigger one — a button on the canvas, a row's own button — is not a fault)
  cut       text cut off: elided with no hover to show the whole line (or elided to make room for a text beside it,
            hover or not), wider than its box, or cut by a clipping panel
  outside   a control partly outside the window, or sticking out of the panel it sits on
  grid      a settings row's field or key diamond off the panel's columns (SPEC 8.0, Theme.qml fieldFor / labelColumnFor):
            every field starts at its row's field column and is a whole field or a pair half wide, every diamond sits in
            the gutter at the row's right, and every row of one list has its field at the same x
  small     something clickable smaller than MIN_CLICK in either direction
  stray     text that shows as a mark, not words: a sliver of a half-scrolled line, or text elided to "…" or one character
            (see stray())
A "control" is something clickable (a MouseArea, a tap/drag handler, a text field) or a line of text that is not
inside one. `ignore`: item-path fragments an app knows are deliberate (e.g. the canvas' own drag handles).
"""
from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QRectF

MIN_CLICK = 16            # px (logical): smaller than this is hard to hit with a mouse
LIST_INDENT = 40   # Qt reports a rich-text list's indent in contentWidth though its lines wrap inside the box (the guide page)
SLACK = 2                 # px: anti-aliasing and rounding never count
SHORT = 80                # px: a text taller than this is a block of text, not a row (a sliver of it is just scrolling)
CONTAIN = 4               # a control wholly inside one this many times its area is layered on it, not crossing it
CLICK = ("QQuickMouseArea", "QQuickTapHandler", "QQuickDragHandler", "QQuickTextInput", "QQuickTextEdit")
FLICK = ("QQuickFlickable", "QQuickListView", "QQuickGridView", "QQuickScrollView")


@dataclass
class Fault:
    kind: str
    path: str
    rect: tuple
    what: str

    def line(self) -> str:
        x, y, w, h = (round(v) for v in self.rect)
        return f"{self.kind:8} {tail(self.path)}  at {x},{y} {w}x{h}: {self.what}"


def tail(path: str, n: int = 4) -> str:
    """The last n steps of an item path (the full path is in faults.json)."""
    parts = path.split("/")
    return (".../" if len(parts) > n else "") + "/".join(parts[-n:])


@dataclass
class Node:
    item: object
    path: str
    rect: QRectF          # in the window, before clipping
    seen: QRectF          # the part not clipped away by an ancestor
    clipper: object       # the nearest clipping ancestor (None: the window)
    layer: str
    parent: "Node | None"


def cls(o) -> str:
    return o.metaObject().className()


def scrolls(o) -> bool:
    """A scrolling list or area, including an app's own QML type built on one (its class is "LayerRows_QMLTYPE_7",
    a ListView underneath): a half-scrolled row in it is not cut text."""
    m = o.metaObject()
    while m is not None:
        if m.className().startswith(FLICK):
            return True
        m = m.superClass()
    return False


def short(o) -> str:
    name = o.objectName() or cls(o).split("_QML")[0].replace("QQuick", "")
    text = o.property("text") if cls(o).startswith(("QQuickText", "Button", "IconButton")) else None
    return f"{name}({str(text)[:24]!r})" if isinstance(text, str) and text else name


def walk(win) -> list[Node]:
    """Every visible item, with its place in the window, its clipped part and its layer."""
    root = win.contentItem()
    out: list[Node] = []

    def visit(item, parent, path, clip, clipper, layer, opacity):
        opacity *= item.opacity()
        if not item.isVisible() or opacity < 0.05 or item.width() <= 0 or item.height() <= 0:
            return
        rect = item.mapRectToScene(QRectF(0, 0, item.width(), item.height()))
        seen = rect.intersected(clip)
        if seen.isEmpty():
            return
        c = cls(item)
        if c.startswith(("QQuickOverlay", "QQuickPopupItem")) or item.z() >= 10:
            layer = f"{layer}/{path.rsplit('/', 1)[-1]}"           # a popup, menu or raised panel: its own layer
        node = Node(item, path, rect, seen, clipper, layer, parent)
        out.append(node)
        if item.clip():
            clip, clipper = seen, node
        for i, child in enumerate(item.childItems()):
            visit(child, node, f"{path}/{short(child)}#{i}", clip, clipper, layer, opacity)

    whole = QRectF(0, 0, root.width(), root.height())
    for i, child in enumerate(root.childItems()):
        visit(child, None, f"{short(child)}#{i}", whole, None, "page", 1.0)
    return out


def clickable(node: Node) -> bool:
    item = node.item
    if cls(item).startswith(CLICK[:1]) and not item.isEnabled():
        return False
    return cls(item).startswith(CLICK) or any(cls(ch).startswith(CLICK[1:3]) and ch.property("enabled")
                                              for ch in item.children() if not hasattr(ch, "childItems"))


def bare(node: Node) -> bool:
    """An invisible click area on its own (not a drawn control)."""
    return cls(node.item).startswith("QQuickMouseArea")


def has_text(node: Node) -> bool:
    return cls(node.item).startswith("QQuickText") and not cls(node.item).startswith(("QQuickTextInput", "QQuickTextEdit")) \
        and bool(str(node.item.property("text") or "").strip())


def atom_of(node: Node, atoms: dict) -> Node:
    """The control a node belongs to: a MouseArea filling its parent is that parent; text inside a control is it."""
    p = node.parent
    while p is not None:
        if id(p) in atoms:
            return atoms[id(p)]
        p = p.parent
    return node


def controls(nodes: list[Node]) -> list[Node]:
    atoms: dict[int, Node] = {}
    for n in nodes:
        if clickable(n):
            whole = cls(n.item).startswith(("QQuickTextInput", "QQuickTextEdit")) or near(n.rect, n.parent.rect)                 if n.parent is not None and not cls(n.item).startswith(CLICK[1:3]) else False
            a = n.parent if whole else n         # a text box is its field; a MouseArea filling its parent is that parent
            atoms[id(a)] = a
    for n in nodes:
        if has_text(n) and atom_of(n, atoms) is n:
            atoms[id(n)] = n
    return list(atoms.values())


def near(a: QRectF, b: QRectF) -> bool:
    return all(abs(x - y) <= SLACK for x, y in ((a.left(), b.left()), (a.top(), b.top()), (a.right(), b.right()), (a.bottom(), b.bottom())))


def inside(a: QRectF, b: QRectF) -> bool:
    return a.adjusted(SLACK, SLACK, -SLACK, -SLACK).intersected(b) == a.adjusted(SLACK, SLACK, -SLACK, -SLACK)


def is_under(n: Node, up: Node) -> bool:
    while n is not None:
        if n is up:
            return True
        n = n.parent
    return False


def area(r: QRectF) -> float:
    return r.width() * r.height()


def hover_shows(node: Node) -> bool:
    """Elision is intended when a hover tip on the text or a near ancestor shows the whole line."""
    n = node
    for _ in range(4):
        if n is None:
            return False
        if any("HoverTip" in cls(ch) for ch in n.item.children()):
            return True
        n = n.parent
    return False


def squeezed_by(n: Node, nodes: list[Node]) -> "Node | None":
    """The sibling text an elided text gives way to (H54: a layer's name cut to "Dra…" for its "2 drawings" note). A
    hover tip excuses text cut by the panel's edge, never text cut for a secondary line on the same row."""
    return next((o for o in nodes if o.parent is n.parent and o is not n and has_text(o) and o.rect.left() >= n.rect.right() - SLACK
                 and o.rect.top() < n.rect.bottom() and n.rect.top() < o.rect.bottom()), None)


def stray(n: Node, say, nodes: list[Node]) -> None:
    """Text that shows as a stray mark, not as words (S36: a "." above "Last changed by" was the top 5 px of the next
    row's "Group" header peeking out of the settings list's bottom edge):
      a sliver  a scrolling list or panel shows under half of a short text, a line or two (a half-scrolled row reads as a
                dot or a scratch; a long block of text in a scroll area is not a sliver). An item whose type name
                holds "EdgeFade" laid over the sliver (a fade into the panel's colour) makes it fine.
      a speck   text with hover help elided down to "…" or one character
      clipped   a one-line text with clip on whose line is taller than its box"""
    t, w = n.item, n.item.width()
    shown = str(t.property("text"))[:20]
    line = max(t.property("contentHeight") or 0, 1)              # the text's height (all its lines)
    faded = any("EdgeFade" in cls(o.item) and o.seen.intersects(n.seen) for o in nodes)
    if n.clipper and scrolls(n.clipper.item) and n.rect.height() < SHORT and n.seen.height() < 0.5 * n.rect.height() - SLACK             and not faded:
        say("stray", n, f"only {n.seen.height():.0f} of {n.rect.height():.0f} px of the text shows "
                        f"({shown!r} peeks out of {tail(n.clipper.path, 2)}: reads as a stray mark)")
    elif t.property("truncated") and len(str(t.property("text"))) > 2 and w < 1.2 * line:
        say("stray", n, f"text elided down to {w:.0f} px: only '…' or one character shows ({shown!r})")
    elif t.clip() and t.property("contentHeight") > t.height() + SLACK and t.property("lineCount") <= 1:
        say("stray", n, f"text line {t.property('contentHeight'):.0f} px tall clipped to a {t.height():.0f} px box")


def check(win, ignore=()) -> list[Fault]:
    nodes = [n for n in walk(win) if not any(s in n.path for s in ignore)]
    found: list[Fault] = []
    say = lambda kind, n, what, r=None: found.append(Fault(kind, n.path, (n.seen if r is None else r).getRect(), what))  # noqa: E731
    atoms = controls(nodes)
    for i, a in enumerate(atoms):
        for b in atoms[i + 1:]:
            if a.layer != b.layer or is_under(a, b) or is_under(b, a) or (bare(a) and has_text(b)) or (bare(b) and has_text(a)):
                continue             # (words lying on a card's own click area are its label, not a crossing)
            x = a.seen.intersected(b.seen)
            if x.width() <= SLACK or x.height() <= SLACK:
                continue
            small, big = (a, b) if area(a.seen) <= area(b.seen) else (b, a)
            if inside(small.seen, big.seen) and area(big.seen) >= CONTAIN * area(small.seen):
                continue
            say("overlap", a, f"crosses {tail(b.path)}", x)
    win_rect = QRectF(0, 0, win.width(), win.height())
    for n in nodes:
        if has_text(n):
            t, w = n.item, n.item.width()
            beside = squeezed_by(n, nodes) if t.property("truncated") else None
            if beside is not None:
                say("cut", n, f"text cut off to make room for {short(beside.item)} beside it (a hover tip doesn't excuse that)")
            elif t.property("truncated") and not hover_shows(n):
                say("cut", n, "text cut off (elided, and no hover shows the whole line)")
            elif t.property("contentWidth") > w + SLACK + (LIST_INDENT if str(t.property("text")).startswith("<!DOCTYPE") else 0):
                say("cut", n, f"text {t.property('contentWidth'):.0f} px wide in a {w:.0f} px box")
            elif t.property("contentHeight") > t.height() + SLACK and t.property("lineCount") > 1:
                say("cut", n, f"text {t.property('contentHeight'):.0f} px tall in a {t.height():.0f} px box")
            if n.seen.width() < n.rect.width() - SLACK or (n.seen.height() < n.rect.height() - SLACK
                                                           and not (n.clipper and scrolls(n.clipper.item))):
                say("cut", n, f"text cut by {tail(n.clipper.path, 2) if n.clipper else 'the window'}")
            stray(n, say, nodes)
    for a in atoms:                  # what a clipping panel or scroll list hides (a half-scrolled row) is not outside
        if a.clipper is None and not inside(a.rect, win_rect):
            say("outside", a, "partly outside the window", a.rect)
        panel = next((p for p in ancestors(a) if cls(p.item) == "QQuickRectangle" and p.item.property("color").alpha() > 0
                      and area(p.rect) >= 3 * area(a.rect)), None)
        if panel is not None and not inside(a.seen, panel.rect) and inside(a.rect, win_rect):
            say("outside", a, f"sticks out of its panel {tail(panel.path, 2)}", a.seen)
        if clickable(a) and min(a.rect.width(), a.rect.height()) < MIN_CLICK:
            say("small", a, f"clickable area {a.rect.width():.0f}x{a.rect.height():.0f} px (under {MIN_CLICK} px)", a.rect)
    grid(nodes, say)
    return found


def grid(nodes: list[Node], say) -> None:
    """Settings rows (InspectorRow: objectName "row:<id>", fields "grid:field", key marks "grid:key") sit on the grid."""
    left: dict[str, tuple[float, Node]] = {}          # the list's first field's window x, to compare the rest with
    for n in nodes:
        name = n.item.objectName()
        if name not in ("grid:field", "grid:key"):
            continue
        row = n.parent
        while row is not None and not row.item.objectName().startswith("row:"):
            row = row.parent
        if row is None or row.item.property("labelColumn") is None:
            continue
        x, w, rw = n.rect.x() - row.rect.x(), n.rect.width(), row.rect.width()
        lc, gut = row.item.property("labelColumn"), row.item.property("gutter")
        if name == "grid:key":
            if abs(x + w / 2 - (rw - gut / 2)) > SLACK:
                say("grid", n, f"key mark centred at {x + w / 2:.0f}, not in the gutter (centre {rw - gut / 2:.0f})")
            continue
        field = rw - gut - lc
        half = (field - 4) / 2
        ok = (abs(x - lc) <= SLACK and (abs(w - field) <= SLACK or abs(w - half) <= SLACK))             or (abs(x - (lc + half + 4)) <= SLACK and abs(w - half) <= SLACK)
        if not ok:
            say("grid", n, f"field at {x:.0f} ({w:.0f} wide), the columns are {lc:.0f} ({field:.0f} wide, pair halves {half:.0f})")
        first = left.setdefault(row.parent.path if row.parent else "", (n.rect.x(), n))
        if abs(first[0] - n.rect.x()) > SLACK and not abs(x - (lc + half + 4)) <= SLACK:
            say("grid", n, f"field starts at window x {n.rect.x():.0f}, the list's other fields at {first[0]:.0f}")


def ancestors(n: Node):
    p = n.parent
    while p is not None:
        yield p
        p = p.parent
