# apps/2d/screen — the Rostrum2D screen

One workspace on one 2D document (no pages; the design is `../DESIGN.md`), built from the shared GUI kit (`shared/gui-kit/`).

```
top bar          Rostrum2D · File · document · what just happened · Undo / Redo · + Add · Import · Export · Ctrl+K · Help
centre           Canvas: the engine's frame at the playhead, fitted; the tool strip (Move V, Pen P, Draw B) at its top left;
                 the selected layers' boxes and handles; the action bar under the selection
right            Settings panel (the kit's Inspector): the selected item(s)' field operation, values at the playhead, key
                 marks; essentials first, folded groups, Find a setting (Ctrl+F); with Draw on, the brush instead
bottom           Timeline = the layers list: a name column (fold, rename, drag to reorder, lock, eye) and a bar per layer
                 with its keys and frames under a ruler with the markers; two heights (full / compact), remembered per tool
```

## Select first, then act (`screen2d/actions.py`, `layer_order.py`, `qml/ActionBar.qml`, `qml/ActionMenu.qml`)

- **One list of actions on the selected layers** (`actions.ACTIONS`, data): Group, Ungroup, Clip, Auto layout, Make swap
  set, Make rig, Mask with top layer (and the other mattes), Release mask, Union / Subtract / Intersect / Exclude, Align,
  Distribute, Match size, Copy / Paste style, Lock / Unlock, Hide / Show, Duplicate, Delete, the four order moves, Rename.
  Each has a key (`layer:<name>`), label, shortcut, importance (`bar` = on the action bar), group (menu dividers) and
  `valid(Facts)`; `available(doc, ids, state)` returns only what the selection allows (nothing is greyed). Each action is
  one change: all its operation calls in one apply. The operations are the ones agents call (`group.make`, `mask.make`,
  `shape.boolean`, `layer.align`, `style.apply`, `layer.lock` …, `python/rostrum2d/ops_*.py`).
- Four places read it: the **action bar** (a floating bar just under the selection; Move tool only, hidden while playing or
  dragging; its buttons and "⋯" for the whole list), the **right-click menus** (a layer's name in the timeline, and the
  selection on the canvas), **Ctrl+K** and the **shortcuts** (Ctrl+G, Ctrl+Shift+G, Ctrl+D, Delete, F2, Ctrl+], Ctrl+[,
  Ctrl+A, Esc, arrows nudge 1 px, Shift 10 px, one change per press).
- The selection is read in one place, `LayerOrder.selected_layers()` (the kit's `selection`, plus whatever the canvas's
  Shift+click holds in `multi.py`). A selection holding a locked layer is offered only Unlock.
- Lock and the eye on each layer row (`qml/LayerName.qml`): fields `locked` / `hidden`. A hidden layer is not drawn in the
  preview or an export (`scene.py` leaves it out) and has no box; `bounds.pick` skips locked layers.
- Steps: `selectmany <id> <id> …`, `act <action>` (`group`, `ungroup`, `mask`, `union`, `align_left`, `distribute_x`,
  `match_w`, `lock`, `hide`, `delete`, `front` …), `nudge <dx> <dy>`, `actionmenu`, `actionbar` (print what they offer).

## The timeline (`qml/LayerTimeline.qml`, `LayerRows.qml`, `LayerName.qml`, `LayerTrack.qml`, `screen2d/outline.py`, `bar_drag.py`)

- One rows list (`backend.layers`, `outline.rows`): a row per layer (bar, keys, a drawing's frames), then, while it is open,
  a row per animated setting, its effects and masks, and its own layers. Open / fold with the name's arrow (`toggleFold`).
- **Bars** (`drags.py`, `bar_drag.py`): a bar's middle drags with `layer.shift`, its ends with `layer.trim`; the dragged edge
  snaps to a shared marker or the playhead within a few px (else whole frames); let go on a marker and the layer is tied to
  it (`layer.shift {to: "#marker"}`, `layer.trim {start|end: "#marker"}`). One drag = one gesture = one undo step.
  Steps: `bardrag <layer> <move|start|end> <from s> <to s|#marker_name>`.
- Two heights (Main.qml `timelineByTool`): full (every row) or compact (header, ruler, the selected layer's row; the name is a
  menu of all layers); Move and Pen remember the full one, Draw the compact one.

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

## Draw tool and frame by frame

- **Pen** (`screen2d/strokes.py`): with the Draw tool on and a `drawing` layer selected (none selected: the first stroke makes the drawing layer in the same change), a press-drag-release is one stroke = one
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

## Paths (Pen tool)

- **Pen** (`screen2d/pen.py`, `qml/PenOverlay.qml`; button or P): click = corner point, press-drag = smooth point,
  click the first point = close, Enter / Escape = done. The finished path is one change (`layer.add` + `path.set`).
- With a path layer selected its points (square = corner, round = smooth) show; **click a point** and only its in / out
  handles show (while the pen draws, the newest point's). A drag is one `path.set_point` gesture (handles stay opposite;
  Alt moves one alone). A path inside a group is not offset by the group yet.
- Steps: `pen <x,y> <x,y,hx,hy> … [close]`, `pointpick <layer> <i>`, `pointdrag <layer> <i> <dx> <dy> [in|out]`.

## Handles and multi-select (Move tool)

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
  an auto layout or driven by an expression: refused loudly). A plain click on another layer resets to one.
- One source for "where a layer's box is on screen": `bounds.boxes` carries each layer through its groups' whole chain (position,
  turn, scale, anchor), so a layer inside a turned group outlines, picks, resizes and moves where it shows (drags are read in the
  parent's frame, `bounds.parent_delta`). It reads each layer at the **stepped** time the engine draws (Timing › Steps on it, its
  group or the composition), so the outline sits on the drawn picture, not the playhead's. A turned group with uneven scale
  (a skew) is approximated. Resize knobs show the arrow matching their on-screen direction (`transform.resize_cursor`, 45° snaps).
- Steps: `resize <layer> <nw|n|ne|e|se|s|sw|w> <dx> <dy> [shift] [alt]`, `rotate <layer> <deg> [shift]`,
  `boxselect <x0> <y0> <x1> <y1>`, `shiftpick <layer>`, `movesel <dx> <dy>`.

## Curves

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
- **Layers timed from a marker:** the timeline, curve editor, drawing frames, inspector values and key marks show every
  time where it plays (composition seconds, like the playhead); a drag or edit writes it back in the layer's own seconds
  (`Bridge2D.placed()` / `own_t()` / `offset()` are the one way across; a key on its own marker stays on it).
- **Auto layout** (a group's Auto layout field, `rostrum2d/layout.py`): the inspector shows spacing controls only once
  the group has a layout; a laid-out layer has no X / Y (the layout places it; **Set apart**, behind More, gives them
  back) and a hugged size is absent. The canvas boxes follow the layout.

## Run

```
.venv\Scripts\python.exe apps\2d\screen\main.py                                  # the last project, else a new one
... main.py --sample                                                             # the built-in sample (not saved)
... main.py --script shot.py                                                     # what a script builds
... main.py --doc <project folder> <item>                                        # open / make; saves on change
... main.py --open <docs\main.mtn or project folder>                             # open it as a person does (File > Save)
... main.py --sample --step "time 1.2" --step "select title" --step "time 1" --shot out.png --size 1646x850 --lookcheck
.venv\Scripts\python.exe -m pytest -q apps\2d\screen\tests                       # under a second
```
Steps: `select`, `selectmany`, `act`, `nudge`, `tool move|pen|draw`, `time`, `set`, `scrub`, `animate`, `drag <layer> <dx> <dy>`, `keydrag <key> <t>`,
`bardrag`, `open <layer>`, `fold <layer>`, `pick <x> <y>`, `find <text>`, `group <name>`, `reveal <field>`, `undo`, `redo`, `more`, `commands`, `run`, `play`, and the Draw steps above;
`export <format> [alpha=on|off] [depth=8|16] [start=<s>] [end=<s>]`, `exportpanel open [format]|close` (`screen2d/steps.py`). Offscreen: `QT_QPA_PLATFORM=offscreen QT_QPA_FONTDIR=C:/Windows/Fonts`.

## Files (File menu, Ctrl+N / Ctrl+O / Ctrl+S / Ctrl+Shift+S)

- **A file is a project folder.** New makes `Documents\Rostrum2D\Untitled 1` (then 2, 3 …) with one blank composition
  (1920 × 1080, 25 fps, 10 s) as the document `docs\main.mtn`, and opens it. Open takes a `.mtn` file (or a project
  folder); Open recent lists the last 8 that still exist. Save as asks a name and makes a new project folder next to
  the others: a copy of the whole project (other documents, markers, imported pictures, renders; never the recovery
  copy), with this window's version saved in it and imported pictures pointed into the copy (one change in the history).
  The window then shows the new project; the old one stays as it was last saved.
- **Saving is by hand.** An edit puts a dot after the name (title bar and top bar: `Spring promo •`). Every 60 seconds
  while there are unsaved changes a **recovery copy** is written to `<project>\.rostrum\recovery\` (the same format as a
  save); the saved document is never touched. Save writes the document and its history and deletes the recovery copy.
  Opening a project whose recovery copy is newer than its saved document asks "Restore unsaved changes?" (Restore /
  Discard). Closing, New or Open with unsaved changes asks Save / Don't save / Cancel.
- **The screen and agents on the same project.** `--doc <folder> <item>` (the launchers, agents, the MCP server) keeps
  saving after every change, so an agent always reads what the person did and never works on an old copy; nothing is
  ever "unsaved" there. In a window saved by hand, Save first checks that nobody else (an agent, another window) saved
  the document since this window read it; if someone did, it refuses and overwrites nothing ("use Save as to keep your
  version"), so a person's Save can never wipe an agent's work and the other way round.
- **Absent, not greyed:** Save is in the menu and Ctrl+K only while there is something to save; the recent list leaves
  out the open project. A document without a folder (the sample, `--script`) offers "Save…", which asks a name.
- **Fails loudly:** a failed save, open or Save as is said in red in the top bar; as a step it exits nonzero.
- Where things are found (engine, ffmpeg, fonts, the projects folder, the settings file with the recent list, whether
  Rostrum3D is installed) is in one place: `apps/2d/python/rostrum2d/settings.py`. Without Rostrum3D the Add menu and
  Ctrl+K have no 3D render layer. The File menu also has **Open sample**.
- Code: `screen2d/projects.py` (folders, recovery copy, Save as; no Qt), `files.py` (the menu's actions, `files` in QML),
  `recent.py`, `session.py` (one window per open document), `file_commands.py` (Ctrl+K), `qml/FileMenu.qml`,
  `qml/FileFlow.qml` (the questions, shortcuts, open dialog), `qml/AskDialog.qml`.
- Steps (`screen2d/file_steps.py`, `_` for spaces): `new [name]`, `save`, `saveas <name>`, `openproject <path>`,
  `autosave`, `restore`, `discard`, `filemenu open|close`, `askclose`. Test: `tests/test_recovery.py`.

## Export

- **Export** in the top bar opens a small panel (`qml/ExportPanel.qml`, `screen2d/exporter.py`): pick a format (mp4, ProRes 4444,
  WebM, GIF, PNG sequence, Lottie), then only the settings that apply to it (transparency where the format can carry it, bit
  depth for png, from / to seconds for everything but Lottie), then Export. It runs as a job off the GUI thread with a progress
  bar, then shows the file, frames, size and what was read back (png / gif: the first frame; Lottie: what it couldn't carry), or
  the error in red. Where it goes: the project's `renders/<item>/vNNN/` (with a manifest) when the document has a folder, else
  the person's Videos folder (Documents when there is none), never the hidden cache.
- The formats and their settings are data (`rostrum2d.io.formats.FORMATS` + Lottie, listed by `rostrum2d.mcp.exporting`); the
  MCP tool `render_export` runs the same code (`exporting.run`), so a person and an agent get the same files.

## Add and import

- **+ Add** (top bar, `qml/AddMenu.qml`, `screen2d/adding.py`): a small menu of only new content, most important first:
  shape, text, path (turns the Pen on), image, video (each asks for a file), drawing (turns Draw on), camera, 3D render. Groups and rigs
  are made from a selection (Group, Make rig), never added empty. A choice is one change (`layer.add` + the type's field operation, centred in the
  composition), selected, one undo step. The list is data (`adding.ENTRIES`); the popup is the kit's `Menu`.
- **Import** (top bar, `qml/ImportPanel.qml`, `screen2d/importer.py`): from a file (SVG, PDF with its page, PSD, image,
  video; what the file is decides which settings show) or a Figma file key + frame + your own token (typed into the panel,
  never stored, printed or sent anywhere but Figma). One change, one undo step; afterwards the layers that came in and the
  list **Didn't come across** (clip paths, filters, shadings, fonts that aren't here, baked PSD effects …). An error shows in
  the panel and the status line and nothing is imported.
- Layers: every path layer (imported or drawn with the pen) has the path icon. Glyph buttons (Export ↗) say what they do
  under the pointer after half a second (the kit's `HoverTip`).
- Import runs off the GUI thread (`screen2d/import_job.py`) with a progress bar and **Cancel** ("Cancelled — nothing imported."):
  the worker only plans (`importing.plan`: read / download / parse / place), the one change (`importing.apply`, one undo step)
  is made back on the GUI thread. An SVG / PDF page / PSD / Figma frame lands centred in the composition, scaled to fit inside it,
  under one group; **Keep original size** (only shown for those kinds) puts it in at its own size and place.
- One door: `rostrum2d.io.importing` (`run` = `plan` + `apply`: file → importer tree → calls → one `doc.apply` → report); the MCP
  tool `run_import` calls `run` (its `fit` is off by default: the source's own size and place).
- Steps: `add <type>` (`add image <path>`), `addmenu open|close`, `import <path> [page=<n>] [text=outline] [keep=on]` (waits),
  `importstart <path>` (doesn't wait), `importpanel open [path]|close`.

## Problems, steps and curves

- **Problems** (`screen2d/problems.py`, `qml/ProblemsPanel.qml`): half a second after a change, off the GUI thread with an
  engine of its own, the same list agents get from `inspect_diagnose` (`rostrum2d.diagnose_engine.everything`). The top bar
  shows "N problems" only while there are any; the panel says each in words with how to fix it, and a click selects the item.
  Steps: `problems open|close` (waits for the list).
- **Steps** (Timing › Steps on a composition, group or layer; `rostrum2d/stepped.py`): on twos / threes / fours is how the
  scene is evaluated, never baked into the keys.
- **Colour curves**: the kit's curve control (`RostrumKit/CurveField.qml`) for a param marked `control="curve"`: drag a
  point, press an empty spot to add one, double-click to remove; each drag is one change. A curve param's `max` is the top of its range: the
  stroke's **Width along the line** goes 0 to 4 (a multiplier; the dashed line at 1 = unchanged), a colour curve 0 to 1. Step `inspectorscroll <px>`
  scrolls the inspector for screenshots.
- **Picks** (a text field naming one other thing, `control="pick"`): Track matte and Follows path are a choice of the
  layers beside it (a path layer for Follows path), Timed from / Ends at marker a choice of the project's markers, each with
  **None** first. With nothing to pick the row is absent. Long labels wrap to two lines instead of being cut.

## Not yet

Text on the canvas is measured by the engine (rostrum2d/textsize.py); drawing ignores rotation. No live sync between two
processes on one file (each saves; reopen to see the other's).
