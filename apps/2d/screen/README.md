# apps/2d/screen — the Rostrum2D screen

Design and Animate pages on one 2D document, built from the shared GUI kit (`shared/gui-kit/`).

```
top bar          Rostrum2D · document · [Design | Animate] · history · Ctrl+K
left             Layers: the composition's layers, top first; effects and masks under their layer; groups fold
centre           Canvas: the engine's frame at the playhead, fitted; the selected layer's box; drag moves it
right            Inspector: the selected item's field operation, values at the playhead, key marks
bottom (full)    Design: play + time + ruler   ·   Animate: keyframe timeline (layer rows, open into field rows)
```

## The rules it builds in

- **One animation model** (`screen2d/route.py`, the only place): a number or colour field keys may drive is edited
  through `value.set` with `at` = the playhead (a still field changes; an animated one gets a key there). The
  inspector shows values at the playhead. The key mark on a row: filled = a key at the playhead, outlined =
  animated, faint on hover = could be animated; clicking it adds the first key (`key.add`) or stops animating
  (`key.clear`).
- **Every drag is one undo step**: moving a layer on the canvas (`value.set` x / y at the playhead) and moving a
  key on the timeline (`key.set` t) are each one `doc.gesture`.
- **Preview ≡ export**: the canvas is rendered by `rostrum2d.engine.Engine`, off the GUI thread, newest request
  wins (`screen2d/frames.py`; `open_engine` is the one line to swap).
- Click empty canvas: the composition is selected (size, frame rate, length, background).

## Run

```
.venv\Scripts\python.exe apps\2d\screen\main.py                                  # sample document
... main.py --script shot.py                                                     # what a script builds
... main.py --doc <project folder> <item>                                        # open / make; saves on change
... main.py --step "time 1.2" --step "select title" --step "page animate" --shot out.png
.venv\Scripts\python.exe -m pytest -q apps\2d\screen\tests                       # under a second
```
Steps: `select`, `page`, `time`, `set`, `scrub`, `animate`, `drag <layer> <dx> <dy>`, `keydrag <key> <t>`,
`open <layer>`, `fold <layer>`, `pick <x> <y>`, `undo`, `redo`, `more`, `commands`, `run`, `play`
(`screen2d/steps.py`). Offscreen: `QT_QPA_PLATFORM=offscreen QT_QPA_FONTDIR=C:/Windows/Fonts`.

## Not yet

Text boxes on the canvas are estimates (from size and character count) until the engine reports laid-out boxes;
boxes ignore rotation. No canvas handles for resize / rotate, no adding layers from the screen except through
Ctrl+K, no live sync between two processes on one file (each saves; reopen to see the other's).
