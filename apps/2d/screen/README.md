# apps/2d/screen — the Rostrum2D screen

One workspace on one 2D document (no pages; the design is `../DESIGN.md`), built from the shared GUI kit (`shared/gui-kit/`).

```
top bar          Rostrum2D · File · document · what just happened · Undo / Redo · Export · Ctrl+K · Help
centre           Tool rail (qml/Rail2D.qml on the kit's ToolRail: icons only, groups open flyouts) in its own column; then the canvas: the engine's frame at the playhead, fitted;
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
  the top-centre of the canvas, hidden while playing or dragging; with strokes picked it shows only what applies to
  them: `qml/StrokeBar.qml`; no tool puts options or hint words over the canvas), the **right-click menus** (a layer's name in the timeline, and the canvas: an
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

- **Settings rows the screen changes after the field data** (`hooks.py`, `corner_rows.py`): Each corner is a split icon on the Corner radius row (and the way back on the first corner's row; the kit's row `button` with an `icon` and a `set`), not a row; an open path's Outline switch is not shown while it is on (`hooks._open_line`) and its line under the name says "Open path" / "Closed path"; a picture's, clip's or render's Fit (Cover / Contain / Stretch) is the folded "+ Fit in box" (the row's "Fit to frame" is the visible one); the Frame row's tip says when Cut here appears; Frame the view on a view the frame already shows says "Already framed" and changes nothing (`frame_actions.already`; `frame.fit` refuses it for agents).

## Creation tools, the view, snapping, painting on any element (H29)

- **R / O / T** (`screen2d/create.py`, `typing_session.py`, `qml/CreateOverlay.qml` in the canvas beside the tool rail):
  drag a rectangle or ellipse (Shift square / round, Alt from the centre, a click = 200 × 200), one change, selected,
  back to Move; T: click or drag a box and type on the canvas, one change per typing session (previews `text.set` per
  key), Esc / Ctrl+Enter ends; double-click a text to type in it again. No bar of options pops up while typing (no Done
  either: Esc, Ctrl+Enter or a click outside ends); from the first letter
  the new text is selected, so the settings panel shows its settings. A new text's colour is `text_ink.py` (one place): dark on a light spot of the frame, white on a dark one, read where it is created (a colour picked while typing wins). The settings panel's folded groups read "Width and slant" / "Ligatures and numbers" for a text (kit `sections.WORDS`; the group keys stay Font / Type); a text's Fill group is the Colour row's picker (`hooks.on_page` leaves its fields out, so no "+ Gradient and opacity" name is offered). Steps: `shape`, `shapedrag`, `text`, `textbox`, `typetext`, `edittext`.
- **The view** (`qml/CanvasView.qml`, `ViewInput.qml`, `ViewControls.qml`, `screen2d/spacekey.py`, `view_steps.py`):
  one mapping (Stage's `compScale`, `toComp`, `fromComp`, `inWell`) for everything over the canvas. Ctrl+wheel / pinch
  at the pointer, Space+drag or middle-drag, Ctrl+0 (fit the frame), Shift+1 (fit everything), Ctrl+1, F (Shift+2), Ctrl+= / Ctrl+−; the "Fit · 43 % ▾" menu. The
  canvas is the world (camera spec § 3.1): the engine draws the world rectangle the view shows, with a margin, at the
  size shown, the frame's quad holding the export (`screen2d/world_view.py`, `frames.py` keeps the last pictures; the
  engine's `frame.world`); a new picture only when the view leaves it or the size shown changes. Outside the frame
  it is dimmed (`qml/WorldFrame.qml`, `FrameChip.qml`, `screen2d/frame_view.py`). Playing looks through the frame: the
  export fitted in the well. Screen state only. Steps: `zoom`,
  `pan`, `fitsel`, `viewmenu`, `viewtime` (pan / zoom / drag timings).
- **Snapping** (`screen2d/snap.py` pure, `snapper.py` as `backend.snap`): moves and resize edges snap within 6 screen
  px to the frame's edges and centre, then other layers'; magenta lines; Ctrl during the drag = free, Shift = straight.
- **Box select** (`multi.boxSelect(…, mods)` through the kit's `selection_rules.box`): Shift adds, Ctrl the deepest.
- **Painting on any element** (`painter.py`, `brush_panel.py`, `strokes.py`): the Draw tool paints on the selected
  shape, text, picture or path (kept inside its outline by the engine), on a drawing, or with nothing selected makes a
  drawing. Each stroke is one `paint.stroke` change (the agent's operation too). Frame keys: `,` `.` step drawings,
  `=` `−` hold. Steps: `draw`, `paintlayer`, `painton selected|new|own|fill`, `painttime` (a stroke's cost, `stroke_time.py`).
  A shape or path with a painted fill is painted in place (`fill_aim.py`): B paints its painting through it (`strokes.py`
  with `fill`, `rostrum2d/paint_through.py`), the other users dotted (`paint_edge.py`).

## The brush panel and the settings panel while painting (H50, painting design phase 1)

- **The Brush group's flyout is the brush panel** (`BrushFlyout.qml`): the five paint tools Brush B, Eraser E,
  Fill G, Pick I, Select S (`paint_tool.py` as `backend.paintTool`: which is on is read from the brush's erase mode,
  Fill, Pick and Select strokes, so they never disagree; the rail's Brush icon is the last one used), then the 19
  shipped brushes (`brush_presets.py`: only existing brush settings, never a colour) as real strokes painted by the
  kit's engine (`image://brushes/<id>`). No context bar while painting (only the picked strokes' StrokeBar).
- **The settings panel** (`brush_panel.py`, the kit Inspector on the painter): "Painting · <layer> · <kind>", the
  brush's name (`BrushHead.qml`: a plain label ▾ that opens the panel, the one place a brush is chosen), the quick rows (`brush.QUICK`, per tool in `brush.TOOL_PARTS`: the Eraser has no Colour, Fill is Colour + Close gaps, Pick and Select none; Size, Opacity, Colour,
  Pressure → size / opacity), "Edit brush ›" (every setting, `Brush.editing`), then "Painting on" (`PaintTarget.qml`:
  Layer ▾, Inside the outline, Draw each frame, from the first moment) and the paint layers (`PaintOn.qml`).
- **On the canvas**: the target's edge dashed; the pointer is the brush ring; `[` `]` size, Shift+`[` `]` hardness,
  Alt + right-drag sizes (left–right) and softens (up–down). Steps: `preset`, `painttool`, `brushedit`, `keytap`,
  `mousedrag … right altkey [hold]`.
- **Fill** (`filler.py` as `backend.fill`, G or the bar's Fill while the target has paint): a click is one
  `paint.fill` (ops_fill.py) with the brush's colour and opacity, on the highlighted paint layer (or a new one when
  + Paint layer is armed), Close gaps small / medium / large in the bar. The fill is a kit **fill** item in the paint
  layer's `strokes`: an outline traced from the flood fill (`rostrum_paint.fill`), laid by `canvas.stamp` like a
  stroke, so the canvas PNG the engine draws holds it (preview = export). A click on a line or in an open area is
  refused by the operation (status), nothing changes.
- **Paint on <element>** (`paint_layers.py` as `backend.paintLayers`, `PaintOn.qml` in the kit Inspector's `below`
  slot, under the brush): the paint layers at the playhead, top first (eye, click = strokes and fills go on it, drag =
  `paint.move`, right-click › Delete = `paint.remove`), the highlighted one's Opacity (one gesture) and Blend
  (`paint.set`), the element's Keep inside the outline / Draw each frame (`<type>.set`), Onion skin while drawing each
  frame (with Draw on it is here, not above the timeline).
- Steps (`paint_steps.py`): `fill <x> <y>`, `fillmode on|off`, `gap <size>`, `paintpick`, `paintset`, `paintmove`,
  `paintremove`, `painttoggle`.

## Alt picks a colour, lasso for strokes, Set depth, the focused area (H31)

- **Alt picks a colour** (`paint_pick.py` as `backend.colourPick`): while Draw is on, holding Alt (an event filter on the
  window reads the key) turns the pointer into a picker; a swatch beside it shows the colour of the engine's frame at that
  point (what the canvas shows: `frames.provider`'s newest picture, not layer data); a click sets the brush colour the way
  the bar's Colour does (`painter.setValue("color")`). Steps: `altpick <x> <y> [click]`, `altoff`.
- **Lasso** (`stroke_select.py` as `backend.strokeSelect`, geometry in `stroke_geom.py`, `StrokeOverlay.qml`, `StrokeBar.qml`):
  Ctrl+drag, or **Select strokes** in the bar then drag, picks the strokes (of what the pen paints on, unlocked paint
  layers) with more than half their points inside; they are outlined, the bar swaps to "N strokes · drag to move · Copy ·
  Paste · Delete · Done Esc". A press in their box and drag moves them; a corner of the box scales them, the knob above
  it turns them (below the box when the context bar would cover it). Each drag previews `stroke.set {points}` and records
  ONE `stroke.transform {dx, dy | scale | turn}`: the call an agent types (rostrum2d/paint_transform.py). Delete =
  `stroke.remove`, Copy / Paste = `paint.stroke` of the same brush (24 px down and right). Esc clears.
  Steps: `lasso x,y … [open]`, `selectstrokes on|off`, `strokesmove`, `strokesturn`, `strokesdelete`, `strokescopy`,
  `strokespaste`, `strokesclear`, `clickarea`, `clickat` (`stroke_steps.py`).
- **Set depth ▾** (actions.py `depth_far|middle|near`, rule `depth` in action_rules.py): on drawings of a composition that
  has a frame: `layer.set_depth` (kept where shown) then `background.fit` (Cover the frame's move) on those it applies to, in one change (3 / 1 / 0.25, the `background.add` defaults). ⋯ Cover the frame's move (cover_move.py) and the warning band (cover_band.py, CoverBand.qml) on a picked backdrop.
  Without a camera it is absent, in Ctrl+K too (a key pressed for it says why in the status line: the action's `why`).
- **Focused area** (`backend.setFocusArea`, tools2d.py; Main.qml): the keyboard focus or a click in the canvas, timeline or
  settings sets it; `inspect_screen`'s `focus` reads it (`screen_seen.py`). The kit's AppShell version (S34) can replace it.

## Animating: the key bar, K, retiming, Stagger, `,` `.` (H30)

- **Key block** (`qml/KeyPanel.qml`, `EaseCurve.qml`, `screen2d/key_bar.py`, `backend.keyBar`; the one ease list in `eases.py`):
  at the top of the settings panel only while keys are picked. Ease ▾, the curve (fitted whole in its box, overshoot
  included; drag its two handles: `key.handles`), one
  key's Time and Value, a spring's Bounce and Speed (`key.set {bounce, speed}`; the words become stiffness / damping in one
  place, `rostrum_core/keys/spring.py`, and `scene.py` sends the engine those). Every picked key changes; each pick, edit
  or whole drag is one change. A key's right-click opens the same list; F9 / Shift+F9 / Ctrl+Shift+F9 / Ctrl+Alt+J are
  actions on the one list (`ease_*`, valid while keys are picked). The rows draw a tiny line / curve / step between keys.
- **K** (`actions.py` `key_here`, rule `pose`): `key.add {fields: "pose", t}` on each selected layer, one change; the
  message says "Keyed 4 settings on 3 layers" (`action_rules.said`).
- **Box-pick** (`LayerRows.qml` box, `KeySelect.box`): drag on an empty part of the rows. **Stretch** (`KeyDot.qml` Alt+press,
  `KeySelect.beginStretch`): `key.scale {around, by}` around the other end. **Copy / paste keys** (`key_edits.py`): with keys
  picked Ctrl+C copies their ids (the latest copy wins over layers); Ctrl+V pastes onto the selected layers at the
  playhead (`key.paste {from, at}`, one call per layer, one change; a layer without a copied setting is skipped and named in the top bar).
- **`,` / `.`** (`key_edits.stepEvent`): keys, markers, drawings, bar starts and ends; of the selected layers or all.
- **Stagger…** (`qml/StaggerPopover.qml`, `screen2d/stagger.py`, `backend.stagger`): an action on the bar (2+ layers);
  the popover (kit Popover: light, never dims the window) previews `layer.stagger {by, order}` live in one open gesture; Enter or click away keeps it and closes it, Esc takes it back.
- Steps (`key_steps.py`): `keybox`, `keystretch`, `ease`, `easekey`, `easecurve`, `spring`, `keytime`, `keyvalue`,
  `easemenu`, `keyhere`, `keycopy`, `keypaste`, `stagger <f> [order] [open]`, `event prev|next`.

## H31 keys: snapping in time, the drag label, ease plays once, Stagger on keys, After the last key

- **One snapping in time** (`screen2d/time_snap.py`): key drags (`drags.py`, `key_moves.py`), the key stretch, bar drags
  (`bar_drag.py`) and the curve editor's key drags (`curves.py`) all ask it where a time lands. Targets, strongest first:
  shared markers, the playhead, other layers' bar ends and keys (every layer shown; never what the drag moves), the
  music's bar starts, then its beats (`backend.soundtrack.bar_times()` / `beat_times()`); within 6 screen px, else a
  whole frame; Ctrl = free. Each answer says what it caught: a bar edge let go on a marker ties as before, and a moved
  bar's shift is measured from where the previews left it, so the edge lands exactly on its target.
- **The drag label and the snap line** (`backend.timeSnap`, `qml/DragLabel.qml`, `qml/SnapLine.qml`): "+6 f", "−3 f",
  "+6 f · drop" beside the dragged edge or key on its layer's row (placed from the drag's time and row, never the
  pointer: right for the mouse, steps and agents alike); a thin magenta line at the time it caught, only while snapped.
  SnapLine.qml is the one place 2D's snap colour lives (the canvas's snap lines use it too).
- **An ease picked plays once** (`screen2d/ease_play.py`, `playback.once`): picking an ease plays the stretch it shapes
  on the canvas, then the playhead goes back. Screen state only; drags never play; the Key block's ⋯ turns it off.
- **Stagger on picked keys** (`stagger.py`): keys picked on two or more layers → `key.stagger {by, order}` (each
  layer's picked keys move together, one change). The spatial orders compare layers in composition px through their
  groups and the camera (`rostrum2d/placement.centres_at`, the engine's `place`).
- **After the last key** (Key block ⋯: Stay · Repeat · Back and forth · Carry on; `key.set {after}` on a field's last
  key): written out as plain keys in one place, `rostrum_core/keys/after.py`, read by Python's evaluation and by the
  scene sent to the engine (preview = export).
- Steps: `keydrag2 <key> <from> <to> [snap] [hold]`, `keystretch … [snap] [hold]`, `bardrag … [snap] [hold]` (`hold`:
  not let go, for a picture mid-drag), `keyafter <stay|repeat|pingpong|carry>`, `easeplay on|off`, `keymore` (the key
  bar's ⋯), `wait <ms>`.

## Sound in 2D (H31: `screen2d/soundtrack*.py`, `waveform.py`, `qml/SoundRow.qml`, `BeatLines.qml`, `TimeRuler.qml`)

- **One audio engine** (AGENTS.md rule 9): 2D has no mixer and no player of its own. `bridge.soundtrack`
  (`soundtrack.py`) picks the scene's song (the comp's `soundtrack` field: a Sound item id; empty = the project's
  first Sound item), asks RostrumSound's engine for its mix and plays it with RostrumSound's live player.
- **Sound's side, used as is:** `rostrum_sound.soundtrack` (no Qt: `find`, `read`, `render` cached by content and
  engine version in `<cache>/soundtrack/`, `grid` = beats and bar starts in seconds, `stamp`, `facts`) and
  `rostrum_sound.live_play.LivePlay` (the one live player, shared with the Sound screen; `warm` opens it stopped).
- **Render** (`soundtrack_render.py`): one worker thread, newest request wins, one engine process ended by its own
  handle. Re-rendered when `stamp` changes (the song's file, the shared markers, the pick; checked once a second).
  The waveform's peaks are read once per mix file (`waveform.py`, keyed by the content-named file), never per paint.
- **Playing** (`soundtrack_play.py`): `playback.py` calls `play` / `stop` and plays from 0 on a loop; the picture
  follows `heard()` (the speaker's position; it waits up to 1.5 s for the output to start). Dragging in the ruler plays
  a 90 ms burst (`scrub`). 🔊 in the timeline header mutes (screen state, 2D only).
- **Loud, never silent:** no engine, a broken song, a missing marker or no sound output is said once in the status
  line and stays on the Sound row in red; the picture keeps its own clock.
- **Screen:** the Sound row is the layers list's footer (`LayerRows.qml`; kept in compact, `compactHeight` counts
  it); its name (or a right-click) opens its menu: Show beats (only while the song has a tempo) draws `BeatLines.qml`,
  Open in RostrumSound (`tools/rostrum.ps1 sound -Doc`); its speaker mutes the sound in 2D only; Shift+, / Shift+. step beats (`stepBeat`; the key map's `prev_beat` /
  `next_beat`). `beat_times()` / `bar_times()` feed time snapping (`time_snap.py`). Scene settings › Soundtrack is a
  choice of the project's Sound items (`soundtrack_rows.py`), absent when there are none.
- **Agents:** `inspect_soundtrack` (what plays: item, length, tempo, bars, markers) and `comp.set {soundtrack}`.
  The field never reaches the 2D engine (`scene.python_only`).
- Steps (`soundtrack_steps.py`): `sound wait | mute on|off | beats on|off | beat prev|next | scrub <s> | play <s> |
  wav <path> | pick <item|-> | menu | open [dry] | problem <png>`. Layout states: `sound-row`,
  `sound-beats`, `sound-compact`, `sound-menu` (a project made by `soundtrack_steps.sound_project`).

## H33 (rig): the Bone tool, Mirror pose, faint marks past the keys, beat words

- **The Bone tool J** (`screen2d/bone_tool.py` as `backend.boneTool`, `qml/BoneTool.qml`; RIG.md › Drawing bones by hand):
  in the tool rail and on J only while a rig is in hand; draws bones joint by joint with `bone.draw`; the bones overlay
  stays visible but does not take the pointer while it is on. Leaving the rig ends it (back to Move).
- **Mirror pose ▾** on the context bar (actions.py `mirror_*`, fact `mirrorable`): `pose.mirror` at the playhead.
- **Faint marks past the keys** (`screen2d/key_ghosts.py`, rows' `ghosts` / `tails` from `outline.rows`, drawn in
  `qml/LayerTrack.qml`): Repeat and Back and forth show faint copies of the keys after the last one, read from
  `rostrum_core.keys.after.extend` (what playback and the export read); a spring still moving at its next key shows a faint
  tail to where it would have settled (`easing.spring` with the key's own physics), with a hover tip.
- **Beat words** (`screen2d/beat_words.py`, the one place): with a tempo in the project's music, a key's label says
  "… at bar 5" / "bar 5 beat 3" (hooks.label_of), the Key block shows "bar 5 beat 3" beside one key's Time, and the time
  drag's snap label names bars and beats the same way. A time within half a frame of a beat is on it.
- Steps: `bonedrag`, `boneclick`, `bonehover`, `boneend`, `bonerealclick <bone> [ctrl]` (a real mouse click; Ctrl held), `bonerealdrag <bone> <dx> <dy>` (a real press, drag, release); `lipsync start|wait|snap <png>`.
  Layout states: `bone-tool`, `mirror-pose-menu`, `key-faint-copies`, `key-beat-words`.

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
- **A change describes only what it touched**: the bridge describes through one `rostrum2d.scene_keep.Keeper` (equal to
  `scene.describe`; untouched items keep their node objects, decided by the document's copy on write), and
  `Engine.load` sends the engine only the new nodes (`scene_change.py`). A marker move or a 3D render finishing makes
  the keeper describe everything again (`_render_all`).
- **Drawings' pictures are made off the GUI thread**: a change to a drawing describes the scene with stand-ins for
  pictures not made yet (`scene.describe(later=…)`), `screen2d/paint_pictures.py` makes them (the same `canvas.png`
  export uses), then the scene is described again and drawn. Painting's wet ink (`wet.py`, `wet_ink.py`) shows the
  stroke meanwhile, in world px anywhere on the canvas (the frame at home or not); its whole-stroke restamp also runs
  on a worker, and the eraser's ink shows the world the canvas shows, drawn once without its layer. Python's thread hand-over is 1 ms in the screen (`session.SWITCH_S`), so a worker never holds the
  screen's thread up for longer.
- Click empty canvas: the composition is selected (size, frame rate, length, background).

## Draw tool and frame by frame

- **Pen** (`screen2d/strokes.py`): with the Draw tool on and a `drawing` layer selected (none selected: the first stroke makes the drawing layer in the same change), a press-drag-release is one stroke = one
  `doc.gesture` = one undo step. Press previews `stroke.add` (fixed id, points so far) on the topmost unlocked paint
  layer of the frame shown at the playhead; each move previews `stroke.set {points}`. No frame shown there yet: the
  same change adds it first (`frame.add at=<current frame>`). Composition px become canvas px through the layer's
  place at the press (the engine's `place`: through its groups, the camera and tilt; `rostrum2d/placement.py`, the one
  mapping `paint.stroke` in comp px uses too). While painting, the target's true edge (rounded corners, ellipse, a
  path's shape, a text's letters) is drawn instead of its box (`screen2d/paint_edge.py`, from the frame's `place`). Pressure comes from a pen (`PointHandler`), 1 for a mouse.
- **Brush** (`screen2d/brush.py`): the next stroke's settings, screen state (not the document). The panel is the kit's
  Inspector over `rostrum_paint.fields.BRUSH` minus the bar's settings: settings that don't apply are absent, deep ones
  behind More.
- **Frames** (`screen2d/framing.py`): a mark where each drawing starts and a bar for its hold (Draw bar and the
  drawing's Animate row). Buttons (in the panel: `DrawEachFrame.qml`, in Draw and in Move; only the ones that apply at the playhead) and shortcuts, each one change:
  Previous / Next (Alt+Left / Alt+Right), New drawing (Alt+N) / New from this (Alt+Shift+N), Hold longer / shorter
  (Alt+Up / Alt+Down), Onion skin (Alt+O, tinted neighbours from `rostrum_paint.see.onion`, over the layer's box).
- Steps: `draw <x> <y> <x> <y> …` (one stroke, composition px), `brush <setting> <value>`, `newframe [copy]`,
  `hold <+n|-n>`, `frame next|prev`, `onion on|off`.

## Paths (Pen tool)

- **Pen** (`screen2d/pen.py`, `qml/PenOverlay.qml`; button or P): click = corner point, press-drag = smooth point,
  click the first point = close, Enter / Escape = done. The finished path is one change (`layer.add` + `path.set`).
- With a path layer selected its points (square = corner, round = smooth) show; **click a point** and only its in / out
  handles show (while the pen draws, the newest point's). A drag is one `path.set_point` gesture ending with `path.fit` (the box follows the reshaped path; handles stay opposite;
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
  every outline shows, and one **box round all of them** (`Multi.groupBox`) has the same knobs and turn zones as a single layer: resize scales every layer about the opposite side (Alt: the centre), turn turns them about the box's centre, one drag = one undo step (`screen2d/group_slots.py`, `qml/Handles.qml` with `group: true`). A resized shape / image / group changes Width / Height, any other type its Scale (corner) or Stretch (edge); each layer keeps its place inside the box. Refused loudly for a layer in an auto layout or driven by an expression. Dragging any one moves them all in one undo step (not layers in
  an auto layout or driven by an expression: refused loudly). A plain click on another layer resets to one.
- One source for "where a layer's box is on screen": `bounds.boxes` carries each layer through its groups' whole chain (position,
  turn, scale, anchor), so a layer inside a turned group outlines, picks, resizes and moves where it shows (drags are read in the
  parent's frame, `bounds.parent_delta`). It reads each layer at the **stepped** time the engine draws (Timing › Steps on it, its
  group or the composition), so the outline sits on the drawn picture, not the playhead's. A turned group with uneven scale
  (a skew) is approximated. Resize knobs show the arrow matching their on-screen direction (`transform.resize_cursor`, 45° snaps).
- Steps: `resize <layer> <nw|n|ne|e|se|s|sw|w> <dx> <dy> [shift] [alt]`, `rotate <layer> <deg> [shift]`,
  `boxselect <x0> <y0> <x1> <y1>`, `shiftpick <layer>`, `movesel <dx> <dy>`, `groupresize <handle> <dx> <dy> [shift] [alt]` and `grouprotate <deg> [shift]` (the box round the selected layers; `selectmany` first).

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

### Step names for scripted runs (`--step "<name> <words>"`; the full list with every word is the docstring of `screen2d/steps.py`)

| To do this | Step |
|---|---|
| Real mouse and keys in the window | `mouseclick <x> <y> [right] [ctrl\|shift]`, `mousedrag <x0> <y0> <x1> <y1> [right] [alt] [hold]`, `mousemove <x> <y>`, `keytap <key> [shift\|alt\|ctrl]` (`keytap z ctrl`, `keytap escape`, `keytap f2`), `typekeys <text>` (`_` is a space) |
| Click or drag a named control | `clickobj <objectName> [fx fy] [right]`, `dragobj <objectName> fx0 fy0 fx1 fy1`, `clickarea canvas\|timeline\|settings` |
| Pick | `select <id>`, `selectmany <id> <id> …`, `pick <x> <y>`, `boxselect <x0> <y0> <x1> <y1>`, `shiftpick <layer>` |
| Run an action of the list | `act <job>` (an action that has a key: `group`, `delete`, `front`, `align_left` …) · `do <action id>` (any action of the list: `distribute_x`, `match_w` …) · `nudge <dx> <dy>` |
| Make things | `shape rect\|ellipse x0 y0 x1 y1`, `text <x> <y> <words>`, `textbox …`, `edittext <layer> <words>`, `pen …`, `draw …`, `add <type>` |
| Settings | `set <field> <json>`, `scrub`, `animate <field>`, `find <text>`, `group <name>`, `reveal <field>` |
| Time | `time <s>`, `play <s>`, `marker add\|move\|rename\|remove`, `bardrag`, `keydrag`, `event prev\|next` |
| Look | `--shot <png>` (after the last step), `--lookcheck`; `--check-layout <folder>` runs every screen state (`--quick`: the important ones at 1646×900, ~2 min) |

A step that leaves an error in the status line fails the run.

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
- **Project sound** (a toggle in the settings, like Transparency, only for MP4 and only when the project has sound; on by default): the scene's
  soundtrack, else the project's main mix (`rostrum2d/project_sound.py`), mixed by RostrumSound's engine, cut to the
  export's range and put under the picture by the bundled LGPL FFmpeg (`rostrum2d/io/export_sound.py`) before the file is
  renamed. If the mix or the muxing fails, the export fails: never a silent MP4 when sound was asked. Agents:
  `render_export {format: "mp4", sound: true|false}` (default as on the screen).

## Add and import

- **Tool rail** (`qml/Rail2D.qml` fills the kit's `ToolRail.qml` / `ToolFlyout.qml` with 2D's tools; icons: the kit's `ToolIcon.qml`, 2D's `ShapeIcon.qml` and `PaintToolIcon.qml`): icons only, its own column
  left of the canvas. Select V · Shapes (Rectangle R, Ellipse O) · Pen P · Text T · Brush B | Add from a file… Ctrl+I (one door
  for picture, video, SVG, Lottie, PDF, PSD: the file picker, then `importer.dropFiles`; with a rendered 3D item in the project
  (`render3d.placeable`) the button opens a list of those items after it) · Library Ctrl+L · Sound (only while the selection can take a cue) · Camera C
  (the first use adds one) · Bone J (only with a rig in hand). Hand H / Zoom Z are keys only (no rail group). A group with more than one entry opens a
  flyout beside the rail; its icon is its last-used tool. Shapes has `pickOnClick`: a click picks the shown shape, press-and-hold or the corner mark opens the flyout. A 3D render goes through `screen2d/adding.py` (one change,
  centred, selected, one undo step); Ctrl+K's Add commands are the same (`file_commands.py`: never a bare `layer.add` that would make an empty layer;
  "Add from a file…" is the one command for files). Every entry does its job on the click.
  Step: `flyout <group>|close`.
- **Import** (Add from a file…: the file picker, then the file comes in at once with the defaults, as a drop does:
  `importer.dropFiles`; a PDF of several pages asks which page first: the panel opens with its Page box). The panel (`qml/ImportPanel.qml`, `screen2d/importer.py`) opens for a pasted Figma link, for that page question, or by
  itself when something didn't come across; it can also take a file (SVG, PDF with its page, PSD, image,
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
- Steps: `add <type>` (`add image <path>`), `flyout <group>|close`, `import <path> [page=<n>] [text=outline] [keep=on]` (waits),
  `importstart <path>` (doesn't wait), `importpanel open [path]|close`.

## Problems, steps and curves

- **Problems** (`screen2d/problems.py`, the kit's Problems chip): half a second after a change, off the GUI thread with an
  engine of its own, the same list agents get from `inspect_diagnose` (`rostrum2d.diagnose_engine.everything`). The top bar
  shows "N problems" only while there are any; its list says each in words with how to fix it, and a click selects the item
  (and goes to its moment when it has one: `Problems.jump`). Steps: `problems open|close` (waits for the list).
- **Steps** (Timing › Animate on, on a composition, group or layer; `rostrum2d/stepped.py`): on twos / threes / fours is how the
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

## Characters (H32: `rig_view.py`, `rig_drag.py`, `rig_poses.py`, `rig_lipsync.py`, `rig_blinks.py`, `rig_mouths.py`)

- **Make rig** is the context bar's first button on a group (or layers) whose parts are named like a body, outside a rig
  (fact `body_parts`; `promoted` in `actions.py`: a secondary action promoted now joins the bar on its own).
- **Bones from part names** on the context bar for a rig with no bones whose parts are named like a body (`rig.guess_bones`).
- **Attach to bone** (`rig_attach.py`): select a part of the rig, Ctrl+click a bone on the overlay (Ctrl read at the press or the release); one change (`bind.set` to
  that bone, rigid, or `bind.add`). Absent when it is already attached there.
- The rig's bar in the timeline shows its bones' and IK chains' keys (one diamond per time; moved and deleted like any
  keys); opened, a row per keyed bone (`outline._owned`).
- **Bone overlay** (`qml/BoneOverlay.qml`, `backend.rig`) while a rig, or anything inside one, is selected with Move: posed
  bones from the canvas's engine (`frames.ask` → `bones`, `place`). Drag a circle = fix the joint (`rig.move_joint`); drag a
  bone = turn it (FK, `value.set rotation`) or, in an IK chain (orange), pull the chain (`value.set targetX/Y`); a click picks
  the bone; right-click a chain's end › Pin / Unpin (`ik.pin`). One drag = one undo step. K on a rig = `rig.key`.
- **Poses** under the settings (`qml/RigPoses.qml`, `backend.poses`): Save pose, click = apply at the playhead, slider = part
  of the way (one change on release), right-click › Delete.
- **Lip sync…** on a mouth swap set (`qml/LipSyncSheet.qml`, `backend.lipsync`): the project's voice lines from RostrumSound
  (`rostrum_core.lipsync.voice.lines`), a row per mouth shape guessed from the drawings' names, Apply = one `lipsync.apply` (a line not heard
  before is listened to off the screen's thread first, with "Step n of 3", a moving bar and the window free). **Add blinks…** on an eyes swap set (`qml/BlinkSheet.qml`): Every,
  Varies by, open / closed / half, Apply = one `blink.add`.
- Steps (`rig_steps.py`): `bones`, `jointdrag`, `posedrag`, `bonepick`, `pin`, `posesave`, `poseapply`, `poseblend`,
  `lipsync open|line|shape|apply|close`, `blinks open|every|vary|pick|apply|close`. Test character: `rig_sample.py`.

## Sizes, Fill the frame, Effects, the frame, Grain (H32 steps)

- **Scene settings › Format** (`size_rows.py`, `rostrum2d/frame_sizes.py` = the one list: Wide 16:9, 4K 16:9, Vertical 9:16,
  Square 1:1, Post 4:5; "Custom" when the numbers match none; the names alone, the numbers are right under them). A pick is `comp.size`; Width and Height stay typeable.
- **Fill the frame** / **Fit inside the frame** (`layer.fill_frame`, `ops_frame.py`): scales the selection (turn kept) to cover or
  sit inside its parent's frame, centred; first on the context bar for a picture or clip, else in the ⋯ menu / Ctrl+K.
- **Effects ▾** on the context bar (any layer but a camera): Blur, Glow, Gradient (shapes and text), Frosted glass, Shadow,
  Grain, Trail, Smear = `effect.add`. Grain (H33) is drawn by the engine on the layer's own look (`engine/render/src/scene/grain.rs`,
  a shader; amount, size, colour, moving or still, seed); for the whole shot, put it on a group holding everything.
  Old documents' whole-picture grain layer (H32, `grain:` recipe in a video layer's `src`, `P/grain.py`) still opens.
- **The frame on the canvas** (`frame_drag.py`, `qml/FrameHandles.qml`, `backend.frameDrag`): C or a click on its name tab
  picks the frame (its outline and tab turn accent blue). Picked: drag inside it (even over layers) or on the tab moves it,
  snapping its edges and centre to layers' and its centre to home (Ctrl frees, Shift straight); a corner square zooms
  (bigger box = zoom down, about the centre, Alt: the opposite corner); just outside a corner turns it (Shift: 15° steps,
  upright within 2°); a click without a drag picks what is under it. Writes x, y, zoom, rotation through `route.value_call`
  (a keyed field gets a key at the playhead), one drag = one undo step; a locked frame refuses. Steps: `frame pick`,
  `frame drag <dx> <dy>`, `frame corner <dx>`, `frame turn <deg>`, `frametime drag|zoom|turn [n]` (`frame_steps.py`).
