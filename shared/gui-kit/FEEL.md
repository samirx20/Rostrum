# Feel tools: checking how an action feels

Three tools for a checker or critic (`rostrum_gui/feel.py`, `feel_strip.py`), plus the layout check's stability pass
(`layout_stable.py`). They answer the interaction plan's three questions with real input: did the press show at
once, did anything move under the pointer, and did the screen freeze. They watch and take pictures. The press
itself is always yours: QTest on the window, on the control a person sees.

```python
from PySide6.QtCore import QPoint, Qt
from PySide6.QtTest import QTest
from rostrum_gui import feel

# 1. First-frame picture: what the very next frame after the press showed
shot = feel.first_frame(win, lambda: QTest.mousePress(win, Qt.LeftButton, Qt.NoModifier, p))
shot.image.save("press.png")       # look at it: is the button pressed, the row lit, the message there?
shot.ms, shot.drew                 # wall time to that frame (for information only); drew=False: no frame came, grabbed anyway

# 2. Positions before and after: did anything move under the pointer?
before = feel.positions(win)                  # {key: QRectF} of every visible control, window px
QTest.mouseClick(win, Qt.LeftButton, Qt.NoModifier, p)
after = feel.positions(win)
feel.moved(before, after, tol=2)              # [(key, before, after)] for each control that moved or resized > 2 px
feel.positions(panel_item)                    # only the controls inside one item
feel.positions(win, near=QRectF(...))         # only those touching a zone (or pass an item)

# 3. Picture strip: a grab every 50 ms for 1 s after an action
s = feel.strip(win, lambda: QTest.keyClick(win, Qt.Key_G, Qt.ControlModifier), ms=1000, every=50)
s.first_change_ms                  # when the screen first answered (None: never)
feel.frozen_gaps(s)                # [(start_ms, end_ms)], longest first: stillness that ended in a change
feel.contact_sheet(s, "strip.png") # every picture in one sheet, its time on each; changed ones framed in orange
```

Reading the results:
- A key is the control's objectName (or QML type) and its object's address. A button whose words change
  ("Play" to "Stop") keeps its key, so `moved` sees it if it changed size.
- A frozen gap over 0.2 s with no working mark in it is a finding (principle 2). The stillness after the last change
  is the screen at rest, not a gap.
- The strip's 50 ms is the most often it takes a picture, not a promise: a grab draws the window, and on a busy
  machine that takes time. `s.times` is what really happened. Measure speed with thread cycles (`cpu_ms`), not
  with these times.
- Never use `QTest.qWait` around these. Use `pointer.wait` (the window keeps its own event loop and the workers run).

## The stability pass in the layout check

`main.py --check-layout <folder> [--quick]` runs it after each state's sizes. It clicks up to 4 controls per state,
for about 6 s at most, and skips any control already tried in an earlier state. It fails a click (fault kind
`stable`, with a before | after picture `<state>-stable-<n>.png`) when either of these happens:

- a control above the clicked one in its panel (or before it on its row), or the clicked control itself, moved
  more than 2 px;
- a popup it opened moved after its first frame.

New rows below, a list growing downward, and other panels changing are all fine. Things that move on their own
(meters, the playhead) are left out.

It never clicks:
- controls whose words say they leave the state or touch the machine (open, save, export, delete, play, record,
  download, anything with "…");
- text boxes, or the canvas;
- the page behind an open popup.

After each click it presses Esc if the click opened a popup. If the screen still isn't as it was, it opens the
state again.

- `ROSTRUM_CHECK_STABLE=0` turns the pass off. Until the apps' first finds are fixed (2026-10-27: Sound 11, 2D 3), finds are
  reported in `<out>/stable-finds.txt` with their pictures and the check still passes; `ROSTRUM_CHECK_STABLE=strict`
  fails them (the default once the app teams have fixed theirs).
- `<folder>/stable.json` lists clicks, finds and seconds per state.
- The run's last lines give the totals.

A control that should move when clicked needs no opt-out. Make it keep its box: a label that changes keeps the
width of its longest label, and a new row goes below or into a slot kept for it. There is no per-app skip list on purpose: if a move
is truly right, tell the kit team so the rule can change for every app.
