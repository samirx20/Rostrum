# apps/3d/app — the Rostrum3D screen

*Team Hem, H13, 2026-10-21.* The window a person uses to look at and change a 3D document: the same document,
operations and history that agents use through the MCP server (`rostrum3d.mcp`). Built on the shared GUI kit
(`shared/gui-kit`, `rostrum_gui.DocBridge`, `RostrumKit`).

## Layout

The window of docs/3d-design/SPEC.md §1 (brief 1, 2026-10-24; the person's tour: `python/rostrum3d/guides/window.md`).

```
top bar        mark ▾  project › shot ▾   Build|Animate|Render (centred)   ↶ ↷ History  Search  Shot camera · Quick ▾  Render  ?  – ▢ ✕
rail (left)    Select · Shapes · Lights · Camera (kit ToolRail, flyouts filled from adding.py's `rail`) · Materials ball (MaterialsList)
centre         the live viewport (Quick = Storm, Final = Cycles in place; through the shot camera or a free camera); the last render over it
right          the settings panel: the kit's sections layout (the kind's own group open, changed groups open, a row of names)
bottom (full)  the scene list (240 px) with the keys on the same rows; 204 px, 284 on the Animate page
```

- **Import** (importing.py, ImportFiles.qml, ImportDrop.qml, KeepSizeRow.qml). The rail's Import group (Ctrl+I) opens a file
  dialog per format (ops_import.FORMATS) and lands the file on the surface under the view's centre; a file dragged from
  Explorer lands under the drop point (picked like a click; a ring shows the spot while it hovers). One `import.add`
  per file, one undo step, selected. A rescaled file: `unit_note` on the status line once and Keep original size
  (`import.keep_size`) in the panel until the next edit. Real-input walk: tests/import_walk.py.
- **Copies and scatter** (brief 24; copies_actions.py, copies_qt.py, copies_live.py, copies_gizmo.py, bridge_copies.py).
  Right-click a shape › Make copies › Line · Grid · Circle · On a surface… (`copies.make`; the last arms a click on the
  surface); right-click a surface while something else was selected › Scatter '<it>' on '<surface>' (`copies.scatter`;
  `bridge.menuSelect` keeps what was selected for that one menu); right-click a copies item › Change near › Scale · Turn ·
  Push · Colour (`effector.add`, near = the other selected item, else a new small sphere beside the copies, selected).
  The new copies item is selected with its Count row focused (`revealField`). The grey line under Count is the scene
  reply's `copies` info ("212 of 400 in Hero 01"). Dragging Count or a Spacing / Radius amount sends the window's view one
  `copies` request per pointer move (no document change, no scene) and writes the change on release (one undo step;
  copies_live.Scrubs takes over the kit's scrub slots, which needs `kit_state.HOOKS` — see the report). A click on one copy
  (the pick reply's `copy`, `source`, `place`) selects the copies item and that copy ("Copy 7 of Buds"); the gizmo moves it
  live (`copies` with `held`) and the drop writes `copies.hold`. Real-input walk: tests/copies_walk.py.
- **Scene list** (SceneList.qml). A group's or import's children sit indented under it (the arrow folds them); an
  import's parts too; a combine is a row with the Combine icon, its inputs under it, a minus before a Subtract's cutters.
  Click a row to select it; Ctrl+click adds, Shift+click picks a run. Two or more solids selected: the settings panel's
  Combine row (screen3d/actions3d.py, hover preview: action_preview3d.py). A row shows its material's name at the right (while the name has its
  whole room): click it to edit the material. Materials and shots are not rows: the rail's Materials ball and the
  shot crumb list them.
- **Files** (kit): the mark's menu, start screen, Open recent, document name (screen3d/files_3d.py); the render sheet
  (F12, the top bar's Render, Ctrl+E) is the kit's export sheet (screen3d/export3d.py, qml/ExportSettings3D.qml; its
  measured time: screen3d/estimate_sheet.py, qml/RenderEstimate.qml).
- **Inspector.** The kit's inspector, built from the selected type's field operation (`mesh.set`, `light.set` …):
  only the settings that apply right now are there (a sphere has no width; turn on depth of field and its f-stop
  appears). Values are shown at the playhead. A number or colour that can move goes through `value.set` at the
  playhead: still, it changes; animated, it gets (or changes) a key at that frame. The key mark at the right of a
  row: outlined = animated, filled = a key at this frame; clicking it starts or stops animating that setting.
- **Keys** (the right of the bottom panel). On each scene row; the selected item opens into one row per animated setting. Click or
  drag the ruler or a row to move the playhead (the viewport draws that frame). Click a diamond to select the key
  (the inspector shows its time, value and ease); drag it to move it, in whole frames.
  The project's shared markers show as named flags on the ruler (placed in frames); a key drag lands on a marker's frame within 6 px.
- **Render** (top bar, or F12) opens the render sheet (guides/rendering.md): This frame or the shot; Quality and Size,
  which are the shot's own render settings (a shot edit, saved; `rostrum3d/render_fields.py`); Save as and, only for
  an EXR, Passes (its layers, also the shot's own; brief 15); the measured
  time ("Measuring…", then "About 6 min · 120 frames · 3.0 s a frame", the probe's picture, a note when the card was
  busy, a budget with the one-setting changes that fit); Render. The render runs as a job with its own engine process,
  through the same code as `render_still` (a frame) and the project's render versions (a shot). The scripted
  `render` step still makes one still through screen3d/render_job.py (the picture over the viewport; Esc hides it).

- **Add, Duplicate, Delete.** The rail's Shapes, Lights and Camera flyouts add those; the Materials chip has New
  material; the shot crumb has New shot (only once a camera exists). Groups come with the multi-selection actions (later). A new item goes into the selected group (or the group holding the selected item),
  gets selected, and is one undo step. **Duplicate** (Ctrl D) copies the selected item, material or shot with its keys,
  children and parts under new ids (`item.duplicate`); **Delete** (Del) removes it (`item.remove`, `material.remove`,
  `shot.remove`). Both work only while something they work on is selected; the shot the screen shows has no Delete.
- **Pickers.** A field that names another item (a mesh's, import's or part's material; a shot's camera) shows as a
  drop-down of those items by name. The field says so itself (`kind` on its param in `fields.py`); `Bridge3D._rows`
  turns such a text row into a choice, the write is still the field's own operation with the id.
- **Cancel** (in Render's place while a render runs, or Esc): ends the render's own engine process by its handle, the screen goes back
  to idle and says "Render cancelled". No picture, nothing red; nothing of it is left on disk (its half-made `.partial` folder is removed).

## Rules it keeps

- **Every change is an operation** in the document's one history, recorded as the person: an edit, a key mark,
  a key drag. A drag (a number scrub, a key drag) is one `doc.gesture` = one undo step. Ctrl+Z / Ctrl+Shift+Z.
- **Viewport bar** (top right of the viewport): Shot camera, Exposure, Studio light (only while the studio lights the view),
  Scene lights, Contact shadows with its strength (only while on; H20), Depth of field (only through a shot camera whose
  depth of field is on; H20).
- **Look: Quick / Final** (Shift+F, or the "Final" toggle in the viewport bar). Final runs Cycles in the viewport with the
  Render button's settings (one place: the shot's render settings, `rostrum3d/render_fields.py`, read through `screen3d/render_job.py` cycles_of); it cleans up
  sample by sample, and a thin progress line along the bottom reads "Final · 64 of 128 samples · 12 s" (then "Final · done ·
  128 samples · 31 s"). Orbiting, editing or moving the playhead restarts it. Exposure, Studio light, Scene lights, Contact
  shadows and Depth of field are Quick-only and are hidden in Final. With under about 300 MB of graphics memory free it
  steps down to half the pixels ("Final at half size: the graphics card is nearly full"); if still short, or Cycles fails, it
  goes back to Quick and says why in the viewport's status line. While the Render button's render runs, Final waits
  ("Final waits for the render"), so two Cycles never share the card.
- **Screen state is not the document:** selection, playhead, folding, the viewport's camera and light settings.
- **Rule of individuality:** controls that don't apply are absent, never greyed out (the inspector from
  `valid_when`; Render turns into "Rendering frame n…" while it runs).
- Agent and script changes show up in place (the bridge listens to the document).

## Run

```
.venv\Scripts\python.exe apps\3d\app\main.py                          # the window, on a small sample set
... main.py --script my_set.py                                         # on what a script builds
... main.py --doc <project folder> <item>                              # a saved document (made if missing), saved after every change
... main.py --step "select cam" --step "frame 24" --step "orbit 40 0" --shot out.png    # scripted, quits by itself
... main.py --size 1646x900 ...                                         # the window's size (default 1600x960)
... main.py --check-layout <folder> [--quick]                           # the layout check: every state in screen3d/layout_states.py
                                                                        # at 1280x720, 1366x768, 1646x900, 1920x1080 (--quick: QUICK states, 1646x900)
.venv\Scripts\python.exe -m pytest -q apps\3d\app\tests                # six tests, about two seconds
```

Steps (`screen3d/steps.py`): `select <id>`, `frame <n>`, `set <setting> <value>`, `scrub <setting> <v> <v> …`,
`animate <setting>`, `keydrag <key id> <frame>`, `fold <id>`, `undo`, `redo`, `more`, `commands [text]`,
`run <command key>`, `play`, `add <mesh:sphere|light:sun…|camera|material|shot>`, `duplicate`, `delete`, `rail shapes|lights|camera`, `page build|animate|render`, `stretch <key id>`, `ease <preset>`, `keys-stretch <grabbed key> <frame> <picked key> …` (Alt+drag), `keys-menu <key id>` (right-click: Ease list), `panel poses|onion` (each toggles its own panel), `pose <name>`, `onion on|off|keys|frames`, `materials`, `shots`, `view`, `mouse x y`, `wait ms`,
`snap path`, `renderstart` / `cancelrender` (don't wait), `render` (waits for the job), `closerender`; viewport: `orbit dx dy`, `pan dx dy`,
`zoom n`, `mode shot|free`, `exposure v`, `studio v`, `lights on|off`, `home`, `viewclick x y` (selects, or places the shape picked in the Shapes flyout).
A scripted run (--shot, --step, --check-layout) never writes into a real project: `--doc` opens a scratch copy (`screen3d/scratch_doc.py`).
Offscreen screenshots: `QT_QPA_PLATFORM=offscreen QT_QPA_FONTDIR=C:/Windows/Fonts`. The kit must be importable
(`uv pip install -e shared/gui-kit`, or `PYTHONPATH=shared/gui-kit`).

## Files

```
main.py                 arguments, the document, the window, scripted steps and the screenshot
screen3d/bridge3d.py    Bridge3D: the kit's DocBridge wired up (its mix-ins: bridge_signals, bridge_shots shot + page, bridge_scene
                        scene list + selection, bridge_time playhead + key drags, bridge_rows settings rows + the screen's facts)
screen3d/pose_thumbs.py a saved pose's small picture, kept in the shared cache (never in the document)
screen3d/key_steps.py   the scripted steps for picked keys (keys-stretch, keys-menu)
screen3d/route.py       the one place a screen edit becomes an operation call (value.set at the playhead, key marks)
screen3d/outline.py     what the scene list and its keys show (no Qt)
screen3d/render_job.py  the Render button's job (rostrum3d.mcp.render.still, its own engine process)
screen3d/steps.py       scripted steps
screen3d/sample.py      the small sample document (not a template)
screen3d/layout_states.py  the screen states the layout check runs (add one with every new screen or panel)
screen3d/scratch_doc.py    scripted runs open a scratch copy of --doc's project
screen3d/viewport.py, viewcam.py, frames.py, qml/Viewport.qml    the live viewport
screen3d/copies_*.py    copies: actions (right-click), the pick + the line under Count + On a surface, live Count / Spacing drags, one copy's gizmo
screen3d/bridge_copies.py   Bridge3D's copies mix-in (right-click on a surface, the Count line)
screen3d/adding.py      the rail's flyouts, New material / shot, Duplicate, Delete (operation calls, one undo step each)
screen3d/files_3d.py, export3d.py   the kit's file pieces and Export sheet, filled for 3D
qml/                    Main, Rail3D, Icon3D, SceneList, KindIcon, RenderButton, RenderView, Viewport, ExportSettings3D
```

## Not yet

- Renaming, grouping or reordering items from the screen (the operations exist; the command bar runs the ones that need
  no input). No drag-and-drop in the scene list. An aim target (`aimItem`) is still a typed id.
- Moving items in the viewport (no move / turn handles yet); a colour picker popup (the kit's).
- Render settings (samples, size, png / exr) on screen: it uses `render_still`'s defaults. One render at a time. No video render button yet (`render_video` exists for agents).
- More than one shot on screen at a time (`--shot-id` picks one); keys of materials and shots (they don't animate
  in v1).
- Polish seen in the H13 screenshots: a long inspector (e.g. a mesh with Aim) clips its last row (More) instead of
  scrolling; long labels are cut ("Index of refracti…"); the playhead line runs a little below the last timeline row.

## Shared-layer requests (for Team Sam)

- `screen3d/route.py` is the same rule as `apps/2d/screen/screen2d/route.py` over a different fields table. Once
  keys and the evaluator move to `rostrum_core`, one `rostrum_gui.route` taking the app's `animatable(kind)` and
  `param(kind, name)` would serve both.
- The key-drag gesture and the timeline (rows + ruler + diamonds) are near copies of 2D's; a kit `KeyTimeline`
  with a seconds or frames ruler would serve both.

## Attribution rows

Nothing new: PySide6 / Qt (LGPL-3.0, dynamically linked) is already recorded.
