"""The layout check's stability pass (K2, "nothing moves under the pointer"): in each state, a few visible controls are
clicked with real input, and where every other control of the same panel sits is read before and after.

    lines = run_state(win, out, name, restore)   # fault lines (kind "stable"), and <out>/<name>-stable-<n>.png for each

It fails (one line per click) when, after the click (AFTER_MS, the panel's next-frame work landed):
  above   a clickable control of the clicked one's panel that sits above it, or before it on its row, moved more than
          TOL px (a line of text whose words changed may shift: it can't be mis-clicked);
  itself  the clicked control moved or changed size (a Play that turns to Stop keeps its box; then it is fine);
  popup   a popup the click opened moved its frame's top or left edge between AFTER_MS (its opening motion done) and
          POPUP_MS later (a popup that grows downward as its content fills in is fine).
Rows that appear below, a list growing downward, a panel elsewhere changing: all fine. What moves on its own (a meter, a
playhead, a blinking caret) is read twice before the click and left out.

Which controls: clickable, enabled, wholly shown, not a text box, not the canvas (AREA_MAX of the window), not one whose
words say it leaves the state or touches the machine (SKIP: open/save/export/delete/quit/play/record/download ... and
any "…", which opens a dialog), and only the top popup's when one is open. Spread over the panels, the lowest first
(it has the most above it), at most MAX_CLICKS per state and BUDGET_S, and a control tried in an earlier state of the
same run is not tried again (<out>/stable-tried.txt). After each click: Esc when it opened a popup, and when the
screen is not as it was, `restore()` opens the state again. ROSTRUM_CHECK_STABLE=0 turns the pass off; =strict makes
its finds fail the check (else they are listed in <out>/stable-finds.txt and the check still passes).
"""
from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path

from . import feel, layout_check

TOL = 2
MAX_CLICKS = 4
BUDGET_S = 6.0
AFTER_MS = 250
POPUP_MS = 300
AREA_MAX = 0.04
SKIP = re.compile(r"\b(open|save|export|import|render|bounce|delete|remove|clear|reset|discard|revert|quit|exit|close|"
                  r"new|play|stop|record|rec|listen|audition|hear|preview|download|install|generate|clean|transcribe|"
                  r"caption|speak|connect|report|send|browse|file|folder|show file|reveal)\b|…|\.\.\.|▶|●|⏺", re.I)
WORDS = ("objectName", "text", "tip", "help", "glyph", "label", "title", "name")
INPUT = ("QQuickTextInput", "QQuickTextEdit")


def wanted() -> bool:
    return os.environ.get("ROSTRUM_CHECK_STABLE", "1") != "0"


def strict() -> bool:
    """Finds fail the check (ROSTRUM_CHECK_STABLE=strict). Until the apps' first finds are fixed (2026-10-27: 11 in
    Sound, 3 in 2D, sent to their teams) they are reported, with their pictures, and the check still passes."""
    return os.environ.get("ROSTRUM_CHECK_STABLE", "1") == "strict"


def words(item, depth: int = 3) -> str:
    """What a control says: its own words and its children's (a Button's label is a Text inside it)."""
    got = [item.objectName()]
    for w in WORDS[1:]:
        v = item.property(w)
        if isinstance(v, str):
            got.append(v)
    if depth:
        got += [words(c, depth - 1) for c in item.childItems()]
    return " ".join(g for g in got if g)


def typing(item) -> bool:
    return layout_check.cls(item).startswith(INPUT) or any(layout_check.cls(c).startswith(INPUT) for c in item.childItems())


def pressable(item) -> bool:
    """Takes a click itself, or through a click area on it (a drawn button: a Rectangle with a MouseArea filling it)."""
    return item.isEnabled() and (layout_check.clickable(layout_check.Node(item, "", None, None, None, "", None)) or any(
        layout_check.cls(c).startswith(layout_check.CLICK[:1]) and c.isEnabled() and c.width() >= item.width() - TOL
        and c.height() >= item.height() - TOL for c in item.childItems()))


def candidates(win, spots: dict, tried: set) -> list:
    whole = win.width() * win.height()
    full = [s for s in spots.values() if pressable(s.node.item)
            and layout_check.near(s.node.seen, s.rect) and s.rect.width() * s.rect.height() <= AREA_MAX * whole
            and min(s.rect.width(), s.rect.height()) >= layout_check.MIN_CLICK
            and s.node.item.property("danger") is not True and not typing(s.node.item) and not SKIP.search(words(s.node.item))]
    layers = {s.node.layer for s in full}
    top = max(layers, key=lambda la: (la != "page", la.count("/")), default="page")
    full = [s for s in full if s.node.layer == top and sig(s) not in tried]     # an open popup takes the clicks
    by_panel: dict[str, list] = {}
    for s in sorted(full, key=lambda s: -s.rect.top()):
        by_panel.setdefault(s.panel, []).append(s)
    order, rows = [], list(by_panel.values())
    while any(rows):
        order += [r.pop(0) for r in rows if r]
    return order


def sig(s) -> str:
    """The same control in another state of the run (its item path without the child numbers and words)."""
    return re.sub(r"#\d+|\('.*?'\)", "", s.node.path)


def before_it(o, c) -> bool:
    """`o` sits above `c`, or on its row and to its left."""
    if o.rect.bottom() <= c.rect.top() + TOL:
        return True
    return o.rect.top() < c.rect.bottom() and c.rect.top() < o.rect.bottom() and o.rect.right() <= c.rect.left() + TOL


def corner(a, b) -> float:
    return max(abs(a.left() - b.left()), abs(a.top() - b.top()))


def try_one(win, c, wait, hover) -> tuple[list, list, dict, set]:
    """Click `c`; ([(spot, after rect, why)], new popup layers, the spots before, keys that moved on their own)."""
    from PySide6.QtCore import QPoint, Qt
    from PySide6.QtTest import QTest
    from . import laid_out
    centre = c.rect.center()
    hover(win, centre)
    first = feel.spots(win)
    wait(80)
    laid_out.now(win)
    before = feel.spots(win)
    alive = {k for k in before if k in first and feel.shift(first[k].rect, before[k].rect) > TOL / 2}
    if c.key not in before:
        return [], [], before, alive
    c = before[c.key]
    QTest.mouseClick(win, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, QPoint(int(centre.x()), int(centre.y())))
    wait(AFTER_MS)
    laid_out.now(win)
    after = feel.spots(win)
    found = []
    if c.key in after and feel.shift(c.rect, after[c.key].rect) > TOL:
        found.append((c, after[c.key].rect, "itself"))
    for k, o in before.items():
        if k != c.key and k not in alive and o.panel == c.panel and k in after and before_it(o, c) \
                and pressable(o.node.item) and corner(o.rect, after[k].rect) > TOL:     # (words can't be mis-clicked)
            found.append((o, after[k].rect, "above"))
    layers = sorted({s.node.layer for s in after.values()} - {s.node.layer for s in before.values()})
    if layers:
        wait(POPUP_MS)
        late = feel.spots(win)
        for la in layers:
            frame, now = popup_frame(after, la), popup_frame(late, la)
            if frame is not None and now is not None and corner(frame, now) > TOL:    # (growing down is fine)
                spot = next(s for s in after.values() if s.node.layer == la)
                found.append((feel.Spot(f"popup {la}", frame, spot.node, c.panel), now, "popup"))
    return found, layers, before, alive


def popup_frame(spots: dict, layer: str):
    """The popup's own frame: the outermost item of its layer (its content filling in later is not the frame moving)."""
    s = next((s for s in spots.values() if s.node.layer == layer), None)
    if s is None:
        return None
    n = s.node
    while n.parent is not None and n.parent.layer == layer:
        n = n.parent
    return n.rect


def picture(win_before, win_after, c, found, path) -> None:
    """Before | after side by side: the clicked control in cyan, each mover in pink where it was and where it went."""
    from PySide6.QtCore import QRectF
    from PySide6.QtGui import QColor, QFont, QImage, QPainter, QPen
    w, h = win_before.width(), win_before.height()
    img = QImage(w * 2 + 12, h, QImage.Format.Format_RGB32)
    img.fill(QColor("#ffffff"))
    p = QPainter(img)
    p.drawImage(0, 0, win_before)
    p.drawImage(w + 12, 0, win_after)
    p.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
    for dx, word in ((0, "before the click"), (w + 12, "after")):
        p.fillRect(QRectF(dx, 0, 120, 18), QColor(0, 0, 0, 200))
        p.setPen(QColor("white"))
        p.drawText(QRectF(dx + 4, 0, 116, 18), 0x81, word)
        p.setPen(QPen(QColor("#00c7be"), 3))
        p.drawRect(c.rect.translated(dx, 0).adjusted(-2, -2, 2, 2))
        for i, (o, now, _) in enumerate(found, 1):
            r = (o.rect if dx == 0 else now).translated(dx, 0).adjusted(-1, -1, 1, 1)
            p.setPen(QPen(QColor("#ff2d55"), 2))
            p.drawRect(r)
            tag = QRectF(r.left(), max(0, r.top() - 14), 22, 14)
            p.fillRect(tag, QColor("#ff2d55"))
            p.setPen(QColor("white"))
            p.drawText(tag, 0x84, str(i))
    p.end()
    if not img.save(str(path)):
        raise RuntimeError(f"stability pass: could not save {path}")


def line(c, found, shot) -> str:
    x, y, w, h = (round(v) for v in c.rect.getRect())
    what = "; ".join(f"{i}. {layout_check.tail(o.node.path, 2) if why != 'popup' else o.key} ({why}) by "
                     f"{now.left() - o.rect.left():+.0f},{now.top() - o.rect.top():+.0f}"
                     + (f" size {now.width() - o.rect.width():+.0f},{now.height() - o.rect.height():+.0f}" if why != "above" else "")
                     for i, (o, now, why) in enumerate(found, 1))
    return f"stable   {layout_check.tail(c.node.path)}  at {x},{y} {w}x{h}: clicking it moved {what}  ({Path(shot).name})"


def run_state(win, out, name: str, restore) -> list[str]:
    """The pass on the state shown in `win`; `restore()` opens the state again and returns its window."""
    from . import pointer
    out = Path(out)
    t0, lines, n = time.monotonic(), [], 0
    tried_file = out / "stable-tried.txt"
    tried = set(tried_file.read_text(encoding="utf-8").splitlines()) if tried_file.is_file() else set()
    todo = candidates(win, feel.spots(win), tried)
    while todo and n < MAX_CLICKS and time.monotonic() - t0 < BUDGET_S:
        c = todo.pop(0)
        tried.add(sig(c))
        n += 1
        shot_before = win.grabWindow()
        found, layers, before, alive = try_one(win, c, pointer.wait, pointer.hover)
        if found:
            shot = out / f"{name}-stable-{len(lines) + 1}.png"
            picture(shot_before, win.grabWindow(), c, found, shot)
            lines.append(line(c, found, shot))
        more = n < MAX_CLICKS and time.monotonic() - t0 + REOPEN_S[0] + 1 < BUDGET_S
        win = settle_back(win, layers, before, alive, timed(restore) if more and restore else None)
        if win is None:
            break
        todo = [s for s in todo if s.key in feel.spots(win)]       # (a reopened state has new controls: a new list)
        if not todo:
            todo = candidates(win, feel.spots(win), tried)
    tried_file.write_text("\n".join(sorted(tried)), encoding="utf-8")
    took = time.monotonic() - t0
    log = out / "stable.json"
    data = json.loads(log.read_text(encoding="utf-8")) if log.is_file() else {}
    data[name] = {"clicked": n, "finds": len(lines), "s": round(took, 2)}
    log.write_text(json.dumps(data, indent=1), encoding="utf-8")
    print(f"stable {name}: clicked {n} control(s), {len(lines)} find(s), {took:.1f} s", flush=True)
    return lines


REOPEN_S = [2.0]          # what opening a state again took last (an app's song may take 5 s: then the pass stops instead)


def timed(restore):
    def again():
        t = time.monotonic()
        try:
            return restore()
        finally:
            REOPEN_S[0] = time.monotonic() - t
    return again


def settle_back(win, layers, before: dict, alive: set, restore):
    """Back to the state: Esc for a popup the click opened; open the state again when the screen differs from before
    the click (what a click toggled without moving anything stays toggled: the state's next clicks see that)."""
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest
    from . import pointer
    if layers:
        QTest.keyClick(win, Qt.Key.Key_Escape)
        pointer.wait(80)
    now = feel.spots(win)
    same = set(before) == set(now) and not feel.moved({k: s.rect for k, s in before.items() if k not in alive},
                                                       {k: s.rect for k, s in now.items()}, TOL)
    if same or restore is None:
        return win if same else None
    try:
        return restore()
    except Exception as e:  # noqa: BLE001  a state whose steps can't run twice: its pass ends; the next state opens anew
        print(f"stable: could not open the state again ({type(e).__name__}: {e}); the pass stops for this state", flush=True)
        return None
