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

## Paths (Design page)

- **Pen** (`screen2d/pen.py`, `qml/PenOverlay.qml`; button or P): click = corner point, press-drag = smooth point,
  click the first point = close, Enter / Escape = done. The finished path is one change (`layer.add` + `path.set`).
- With a path layer selected its points (square = corner, round = smooth) and handles show; a drag is one
  `path.set_point` gesture (handles stay opposite; Alt moves one alone).
- Steps: `pen <x,y> <x,y,hx,hy> … [close]`, `pointdrag <layer> <i> <dx> <dy> [in|out]`.

## Handles and multi-select (Design page)

- A selected layer's outline turns with it. With one layer selected (not a path, whose points show instead) it has 4 corner +
  4 edge knobs (`qml/Handles.qml`; an edge knob is absent on a small box) and a turn zone just outside each corner (open-hand
  cursor). Resize: the opposite side stays put; **Shift** keeps the proportion, **Alt** resizes from the centre. Turn: about the
  anchor, **Shift** snaps to 15°. Maths: `screen2d/transform.py`; slots: `screen2d/handle_slots.py`.
- What a resize changes: shapes, images, groups -> Width / Height (and X / Y); every other type (text, video, drawing, ...) ->
  Scale from a corner, Stretch X / Y from an edge. An animated field gets a key at the playhead; an expression-driven one refuses
  loudly; a layer in an auto layout changes size only (the layout places it). Each drag is one undo step.
- **Several layers** (`screen2d/multi.py`, `backend.multi`): drag on empty canvas = a rubber band; layers whose boxes touch it
  are selected (not a layer inside a selected group). **Shift+click** adds / removes one. The first is the inspector's;
  every outline shows, handles only for a single layer. Dragging any one moves them all in one undo step (not layers in
  an auto layout or driven by an expression: refused loudly). A click or the layers panel resets to one.
- Click-to-pick turns the pointer back by the layer's rotation, so a turned layer picks where it shows. A group's turn isn't passed
  to its layers' boxes yet.
- Steps: `resize <layer> <nw|n|ne|e|se|s|sw|w> <dx> <dy> [shift] [alt]`, `rotate <layer> <deg> [shift]`,
  `boxselect <x0> <y0> <x1> <y1>`, `shiftpick <layer>`, `movesel <dx> <dy>`.

## Curves (Animate page)

- The timeline's **Keys / Curves** switch shows the selected layer's animated number fields as value curves, overlaid,
  one colour each (the legend names them; click one to hide it). Drag a key (time and value, `key.set`) or a Bézier
  handle (`key.handles`: the stretch's ease becomes `custom`); each drag is one undo step. Handles show only for the
  selected key's stretches with a cubic ease. Agents: `inspect_curve`. Steps: `curves on|off`,
  `curvedrag <key> <dt> <dv>`, `handledrag <key> <1|2> <dx> <dy>`.

## Markers and auto layout

- **Shared markers** (in a project folder only; the controls are absent otherwise): **Add marker** (time bar, timeline
  header) puts one at the playhead's frame. On the ruler a flag drags (one `marker.move` on release, whole frames),
  renames on double-click (Enter keeps, Esc cancels) and shows × on hover to delete. Each is one marker operation in the
  project's marker history (`rostrum_gui/markers.py`), the same ones agents call with `edit_markers`. Steps:
  `marker add <s>`, `marker move|rename|remove <name> …` (`_` for spaces).
- **Auto layout** (a group's Auto layout field, `rostrum2d/layout.py`): the inspector shows spacing controls only once
  the group has a layout; a laid-out layer has no X / Y (the layout places it; **Set apart**, behind More, gives them
  back) and a hugged size is absent. The canvas boxes follow the layout.

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
`export <format> [alpha=on|off] [depth=8|16] [start=<s>] [end=<s>]`, `exportpanel open [format]|close` (`screen2d/steps.py`). Offscreen: `QT_QPA_PLATFORM=offscreen QT_QPA_FONTDIR=C:/Windows/Fonts`.

## Export

- **Export** in the top bar opens a small panel (`qml/ExportPanel.qml`, `screen2d/exporter.py`): pick a format (mp4, ProRes 4444,
  WebM, GIF, PNG sequence, Lottie), then only the settings that apply to it (transparency where the format can carry it, bit
  depth for png, from / to seconds for everything but Lottie), then Export. It runs as a job off the GUI thread with a progress
  bar, then shows the file, frames, size and what was read back (png / gif: the first frame; Lottie: what it couldn't carry), or
  the error in red. Where it goes: the project's `renders/<item>/vNNN/` (with a manifest) when the document has a folder, else
  the render cache.
- The formats and their settings are data (`rostrum2d.io.formats.FORMATS` + Lottie, listed by `rostrum2d.mcp.exporting`); the
  MCP tool `render_export` runs the same code (`exporting.run`), so a person and an agent get the same files.

## Add and import

- **+ Add** (top bar, `qml/AddMenu.qml`, `screen2d/adding.py`): a small menu of only what applies on this page, most important
  first. Design: shape, text, path (turns the pen on), image, video (each asks for a file), group, camera. Draw: drawing.
  Animate: camera, rig, group. A choice is one change (`layer.add` + the type's field operation, centred in the
  composition), selected, one undo step. The list is data (`adding.ENTRIES`); the popup is the kit's `Menu`.
- **Import** (top bar, `qml/ImportPanel.qml`, `screen2d/importer.py`): from a file (SVG, PDF with its page, PSD, image,
  video; what the file is decides which settings show) or a Figma file key + frame + your own token (typed into the panel,
  never stored, printed or sent anywhere but Figma). One change, one undo step; afterwards the layers that came in and the
  list **Didn't come across** (clip paths, filters, shadings, fonts that aren't here, baked PSD effects …). An error shows in
  the panel and the status line and nothing is imported.
- One door: `rostrum2d.io.importing.run` (file → importer tree → calls → one `doc.apply` → report); the MCP tool `run_import`
  calls the same function.
- Steps: `add <type>` (`add image <path>`), `addmenu open|close`, `import <path> [page=<n>] [text=outline]`,
  `importpanel open [path]|close`.

## Not yet

Text boxes on the canvas are estimates (from size and character count) until the engine reports laid-out boxes;
drawing ignores rotation. No adding layers from the screen except through
Ctrl+K, no live sync between two processes on one file (each saves; reopen to see the other's).
