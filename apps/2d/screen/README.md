# apps/2d/screen — the Rostrum2D screen

One workspace on one 2D document (no pages; the design is `../DESIGN.md`), built from the shared GUI kit (`shared/gui-kit/`).

```
top bar          Rostrum2D · File · document · what just happened · Undo / Redo · + Add · Import · Export · Ctrl+K · Help
centre           Canvas: the engine's frame at the playhead, fitted; the tool strip (Move V, Pen P, Draw B) at its top left;
                 the selected layers' boxes and handles; the context bar at the top-centre
right            Settings panel (the kit's Inspector): the selected item(s)' field operation, values at the playhead, key
                 marks; essentials first, folded groups, Find a setting (Ctrl+F); with Draw on, the brush instead
bottom           Timeline = the layers list: a name column (fold, rename, drag to reorder, lock, eye) and a bar per layer
                 with its keys and frames under a ruler with the markers; two heights (full / compact), remembered per tool
```

## Select first, then act (`screen2d/actions.py`, `action_rules.py`, `keys2d.py`, `action_slots.py`; the kit's ContextBar, ActionMenu, KeyMap)

- **2D's entries in the kit's one action list** (`actions.DATA`, plain data, read into kit `Action`s:
  `LIST = ActionList(ACTIONS, KEYS2D)`): id, label, `job` (its key from the key map: shared, or 2D's own in `keys2d.py`,
  refused at start-up if one takes a shared key), importance (`primary` = on the context bar), rank, group (menu
  dividers), `bar` (the button or side menu it sits under: Combine, Mask, Align, Distribute, Make, Match, Order),
  min / max targets, `when` (a condition in the one condition language on the selection's facts: `action_rules.Facts`),
  and `calls` (an operation, a target rule and argument rules such as `$new:group`, `$at`, `$top`; or the named rule
  `order`: `action_rules.py`) or `do` (the clipboard, copy style, rename). The kit's one guard leaves out what the
  selection doesn't allow (nothing is greyed). Each action is one change: all its calls in one apply; the operations
  are the ones agents call (`python/rostrum2d/ops_*.py`). A selection holding a locked layer is offered only Unlock.
- One `ActionHub` (`backend.actions`, `action_slots.py`) feeds four doors: the **context bar** (the kit's ContextBar at
  the top-centre of the canvas, hidden while playing or dragging; with Pen, Paint or typing on it shows that tool's
  options instead: `qml/ToolOptions.qml`), the **right-click menus** (a layer's name in the timeline, and the canvas: an
  unselected layer is selected alone first; sets of more than two choices fold into a side menu), **Ctrl+K**'s Do group
  and the **keys** (the kit's KeyMap). Esc steps back one level (the kit's `selection_rules.esc_step`: picked keys,
  then layers); arrows nudge 1 px, Shift 10 px, Alt 0.1 px, one change per press.
- The selection is read in one place, `LayerOrder.selected_layers()`.
- Lock and the eye on each layer row (`qml/LayerName.qml`): fields `locked` / `hidden`. A hidden layer is not drawn in the
  preview or an export (`scene.py` leaves it out) and has no box; `bounds.pick` skips locked layers.
- **Keys in the timeline** (`key_select.py`, `backend.keys`): click picks a key, Ctrl+click adds / removes, Shift+click
  the run between; a diamond on a layer's bar stands for all its keys at that frame. Picked keys move together (one
  change); Delete removes them. **A** opens the selected layers to their animated settings only; again folds them
  (`outline.rows(…, anim_only)`).
- Steps: `selectmany <id> <id> …`, `act <action>` (`group`, `ungroup`, `mask`, `union`, `align_left`, `distribute_x`,
  `match_w`, `lock`, `hide`, `delete`, `front` …), `nudge <dx> <dy>`, `actionmenu`, `actionbar`; keys (`key_steps.py`):
  `keypick <id>[,<id>…] [ctrl|shift]`, `keydrag2 <key> <from s> <to s>`, `keydelete`, `showanim`.

## The timeline (`qml/LayerTimeline.qml`, `LayerRows.qml`, `LayerName.qml`, `LayerTrack.qml`, `screen2d/outline.py`, `bar_drag.py`)

- One rows list (`backend.layers`, `outline.rows`): a row per layer (bar, keys, a drawing's frames), then, while it is open,
  a row per animated setting, its effects and masks, and its own layers. Open / fold with the name's arrow (`toggleFold`).
- **Bars** (`drags.py`, `bar_drag.py`): a bar's middle drags with `layer.shift`, its ends with `layer.trim`; the dragged edge
  snaps to a shared marker or the playhead within a few px (else whole frames); let go on a marker and the layer is tied to
  it (`layer.shift {to: "#marker"}`, `layer.trim {start|end: "#marker"}`). One drag = one gesture = one undo step.
  Steps: `bardrag <layer> <move|start|end> <from s> <to s|#marker_name>`.
- Two heights (Main.qml `timelineByTool`): full (every row) or compact (header, ruler, the selected layer's row; the name is a
  menu of all layers); Move and Pen remember the full one, Draw the compact one.

## Creation tools, the view, snapping, painting on any element (H29)

- **R / O / T** (`screen2d/create.py`, `typing_session.py`, `qml/CreateOverlay.qml` in the canvas under the tool strip):
  drag a rectangle or ellipse (Shift square / round, Alt from the centre, a click = 200 × 200), one change, selected,
  back to Move; T: click or drag a box and type on the canvas, one change per typing session (previews `text.set` per
  key), Esc / Ctrl+Enter ends; double-click a text to type in it again. While typing the context bar has Font, Weight,
  Size, Colour, Done (`qml/ToolOptions.qml`). Steps: `shape`, `shapedrag`, `text`, `textbox`, `typetext`, `edittext`.
- **The view** (`qml/CanvasView.qml`, `ViewInput.qml`, `ViewControls.qml`, `screen2d/spacekey.py`, `view_steps.py`):
  one mapping (Stage's `compScale`, `toComp`, `fromComp`, `inWell`) for everything over the canvas. Ctrl+wheel / pinch
  at the pointer, Space+drag or middle-drag, Ctrl+0, Ctrl+1, F (Shift+2), Ctrl+= / Ctrl+−; the "Fit · 43 % ▾" menu. The
  engine is asked for the frame at the size shown, up to Full (`shown.setView`). Screen state only. Steps: `zoom`,
  `pan`, `fitsel`, `viewmenu`.
- **Snapping** (`screen2d/snap.py` pure, `snapper.py` as `backend.snap`): moves and resize edges snap within 6 screen
  px to the frame's edges and centre, then other layers'; magenta lines; Ctrl during the drag = free, Shift = straight.
- **Box select** (`multi.boxSelect(…, mods)` through the kit's `selection_rules.box`): Shift adds, Ctrl the deepest.
- **Painting on any element** (`painter.py`, `brush_panel.py`, `strokes.py`): the Draw tool paints on the selected
  shape, text, picture or path (kept inside its outline by the engine), on a drawing, or with nothing selected makes a
  drawing. Each stroke is one `paint.stroke` change (the agent's operation too). The Paint bar: tip, Size, Colour,
  Opacity (gives way on narrow windows), Eraser E, `[` `]`, + Paint layer, Painting on: *x* ▸. Frame keys: `,` `.`
  step drawings, `=` `−` hold. Steps: `draw`, `paintlayer`, `painton selected|new`.

## The rules it builds in

- **One animation model** (`screen2d/route.py`, the only place): a number or colour field keys may drive is edited
  through `value.set` with `at` = the playhead (a still field changes; an animated one gets a key there). The
  inspector shows values at the playhead. The key mark on a row: filled = a key at the playhead, outlined =
  animated, faint (always shown) = could be animated; clicking it adds the first key (`key.add`) or stops animating
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
`export <format> [alpha=on|off] [depth=8|16] [quality=<q>] [range=<a→b>]`, `exportpanel open [format]|close` (`screen2d/steps.py`), and the kit's
`exportsheet open [format]|close`, `exportwhere <folder>`, `exportnow [replace|both|cancel]`, `job-show <percent>`, `job-failed <words>`. Offscreen: `QT_QPA_PLATFORM=offscreen QT_QPA_FONTDIR=C:/Windows/Fonts`.

## Files (≡ menu, Ctrl+N / Ctrl+O / Ctrl+Shift+S / Ctrl+S; the kit's one model: shared/gui-kit/FILES.md)

- **Saving is automatic.** Every project window is live (`rostrum_core.live` + `LiveLink` in `Bridge2D`, for any
  document with a folder, however it was opened): each change is on disk at once, through the same door as the agent
  server, and an agent's change shows in the window on the next LiveLink tick. No Save, no unsaved dot, no
  "Save changes?", no recovery copy.
- **A file is a project folder.** New makes `Documents\Rostrum2D\Untitled` (then 2, 3 …) with one blank composition
  (1920 × 1080, 25 fps, 10 s) as `docs\main.mtn`, and opens it; a New project left untouched is removed when left.
  Open takes a project folder (or a `.mtn` file); Open recent lists the last 10 still on disk (`rostrum_core/recent.py`,
  the same list the MCP server reads). Open sample opens the person's own copy of the Lull sample (`rostrum_core.samples`).
- **Duplicate…** copies the whole project to a new folder; imported pictures inside it are pointed into the copy (one
  change in the copy). The window stays on the original and says so, with **Open the copy**. **Save a version**
  (Ctrl+S) opens History's name field with the time as the name. **Show folder**, **Start screen…**.
- **Starting:** the last project where it was left; with nothing to reopen, the kit's start screen. A damaged or newer
  project is refused in words ("… Nothing was changed.") and the app still starts.
- `--sample` / `--script` are in-memory windows for checks and pictures (no folder, not saved).
- Code: `screen2d/files2d.py` (2D's adapter: blank, resolve, repoint, picture), `session.py` (one window per open
  document), `file_commands.py` (Ctrl+K), kit `rostrum_gui/project_files.py`, `qml/RostrumKit/FilesMenu.qml`,
  `StartScreen.qml`.
- Steps (`screen2d/file_steps.py`, `_` for spaces): `new [name]`, `openproject <path>`, `startscreen open|close`,
  `version [name]`, `duplicateproject <name>`, `filemenu open|close`. Test: `shared/gui-kit/tests/test_docfiles.py`.

## Export

- **Export** (the top bar's Export, Ctrl+E; Ctrl+Shift+E exports again) opens the kit's Export sheet in the inspector's place
  (`shared/gui-kit/EXPORT.md`), filled by `screen2d/exporter.py` (`Exporter`, the kit's `ExportSheet`) and
  `qml/ExportSettings.qml`: What for in words with the file type (video to share .mp4, video for editing .mov, for the web
  .webm, GIF, still frames, frames for the Editor, Lottie, motion for RostrumSound: `export_rows.WHAT_FOR`), then only the
  settings that apply (transparency where the format can carry it, bit depth, quality), the range (everything, or marker to
  marker), where it goes (the project's `renders/<item>/vNNN/` with a manifest; Browse for a folder: a file there is never
  replaced without Replace / Keep both / Cancel), Export. It runs as a background job (the top bar's job chip, Cancel); done,
  the message line says "Exported <file> · Play · Show in folder", the sheet shows what was read back (Lottie: what it
  couldn't carry), and the document gets a version "Exported v003". A failure is red, in words; no unfinished file is left.
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

- **Problems** (`screen2d/problems.py`, the kit's Problems chip): half a second after a change, off the GUI thread with an
  engine of its own, the same list agents get from `inspect_diagnose` (`rostrum2d.diagnose_engine.everything`). The top bar
  shows "N problems" only while there are any; its list says each in words with how to fix it, and a click selects the item
  (and goes to its moment when it has one: `Problems.jump`). Steps: `problems open|close` (waits for the list).
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
