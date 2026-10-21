# apps/2d/screen — the Rostrum2D screen

Design, Draw and Animate pages on one 2D document, built from the shared GUI kit (`shared/gui-kit/`).

```
top bar          Rostrum2D · document · [Design | Draw | Animate] · history · Ctrl+K
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

## Draw and frame by frame

- **Pen** (`screen2d/strokes.py`): on Draw, with a `drawing` layer selected, a press-drag-release is one stroke = one
  `doc.gesture` = one undo step. Press previews `stroke.add` (fixed id, points so far) on the topmost unlocked paint
  layer of the frame shown at the playhead; each move previews `stroke.set {points}`. No frame shown there yet: the
  same change adds it first (`frame.add at=<current frame>`). Composition px become canvas px with the layer's x, y,
  anchor, scale and rotation (`rostrum2d.drawing.to_canvas`; a drawing inside a group is not offset by the group yet). Pressure comes from a pen (`PointHandler`), 1 for a mouse.
- **Brush** (`screen2d/brush.py`): the next stroke's settings, screen state (not the document). The panel is the kit's
  Inspector over `rostrum_paint.fields.BRUSH`: settings that don't apply are absent, deep ones behind More.
- **Frames** (`screen2d/framing.py`): a mark where each drawing starts and a bar for its hold (Draw bar and the
  drawing's Animate row). Buttons (only the ones that apply at the playhead) and shortcuts, each one change:
  Previous / Next (Alt+Left / Alt+Right), New drawing (Alt+N) / New from this (Alt+Shift+N), Hold longer / shorter
  (Alt+Up / Alt+Down), Onion skin (Alt+O, tinted neighbours from `rostrum_paint.see.onion`, over the layer's box).
- Steps: `draw <x> <y> <x> <y> …` (one stroke, composition px), `brush <setting> <value>`, `newframe [copy]`,
  `hold <+n|-n>`, `frame next|prev`, `onion on|off`.

## Run

```
.venv\Scripts\python.exe apps\2d\screen\main.py                                  # sample document
... main.py --script shot.py                                                     # what a script builds
... main.py --doc <project folder> <item>                                        # open / make; saves on change
... main.py --step "time 1.2" --step "select title" --step "page animate" --shot out.png
.venv\Scripts\python.exe -m pytest -q apps\2d\screen\tests                       # under a second
```
Steps: `select`, `page`, `time`, `set`, `scrub`, `animate`, `drag <layer> <dx> <dy>`, `keydrag <key> <t>`,
`open <layer>`, `fold <layer>`, `pick <x> <y>`, `undo`, `redo`, `more`, `commands`, `run`, `play`, and the Draw steps above
(`screen2d/steps.py`). Offscreen: `QT_QPA_PLATFORM=offscreen QT_QPA_FONTDIR=C:/Windows/Fonts`.

## Not yet

Text boxes on the canvas are estimates (from size and character count) until the engine reports laid-out boxes;
boxes ignore rotation (so does drawing). No canvas handles for resize / rotate, no adding layers from the screen except through
Ctrl+K, no live sync between two processes on one file (each saves; reopen to see the other's).
