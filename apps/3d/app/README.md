# apps/3d/app — the Rostrum3D screen

*Team Hem, H13, 2026-10-21.* The window a person uses to look at and change a 3D document: the same document,
operations and history that agents use through the MCP server (`rostrum3d.mcp`). Built on the shared GUI kit
(`shared/gui-kit`, `rostrum_gui.DocBridge`, `RostrumKit`).

## Layout

```
top bar        Rostrum3D · the shot's name · [Render]                   history · Search or run a command (Ctrl K)
left           Outliner: Scene (the item tree), Materials, Shots
centre         the live viewport (Storm, through the shot camera or a free camera); the last render over it
right          Inspector: the selected thing's settings at the playhead, with key marks
bottom (full)  Timeline: the shot's frames, the playhead, play, and the keys of what moves
```

- **Outliner.** A group's or import's children sit indented under it (the arrow folds them); an import's parts too.
  Click a row to select it. A mesh row shows its material's name at the right: click it to edit the material.
- **Inspector.** The kit's inspector, built from the selected type's field operation (`mesh.set`, `light.set` …):
  only the settings that apply right now are there (a sphere has no width; turn on depth of field and its f-stop
  appears). Values are shown at the playhead. A number or colour that can move goes through `value.set` at the
  playhead: still, it changes; animated, it gets (or changes) a key at that frame. The key mark at the right of a
  row: outlined = animated, filled = a key at this frame; clicking it starts or stops animating that setting.
- **Timeline.** One row per item that moves; the selected item opens into one row per animated setting. Click or
  drag the ruler or a row to move the playhead (the viewport draws that frame). Click a diamond to select the key
  (the inspector shows its time, value and ease); drag it to move it, in whole frames.
  The project's shared markers show as named flags on the ruler (placed in frames); a key drag lands on a marker's frame within 6 px.
- **Render** (top bar, or F12). One final picture (Cycles) of the playhead frame through the shot's camera, at the
  shot's size. It runs as a job with its own engine process (the viewport keeps working), through the same code as
  the MCP tool `render_still`: a project render version with its manifest under the project folder, or the render
  cache (`%USERPROFILE%\.rostrum\cache\render\`) when the screen has no project folder. The picture then shows over
  the viewport with its file path and time; Close or Esc hides it. A failure shows in red, never as a picture.

## Rules it keeps

- **Every change is an operation** in the document's one history, recorded as the person: an edit, a key mark,
  a key drag. A drag (a number scrub, a key drag) is one `doc.gesture` = one undo step. Ctrl+Z / Ctrl+Shift+Z.
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
.venv\Scripts\python.exe -m pytest -q apps\3d\app\tests                # two tests, about two seconds
```

Steps (`screen3d/steps.py`): `select <id>`, `frame <n>`, `set <setting> <value>`, `scrub <setting> <v> <v> …`,
`animate <setting>`, `keydrag <key id> <frame>`, `fold <id>`, `undo`, `redo`, `more`, `commands [text]`,
`run <command key>`, `play`, `render` (waits for the job), `closerender`; viewport: `orbit dx dy`, `pan dx dy`,
`zoom n`, `mode shot|free`, `exposure v`, `studio v`, `lights on|off`, `home`, `click x y`.
Offscreen screenshots: `QT_QPA_PLATFORM=offscreen QT_QPA_FONTDIR=C:/Windows/Fonts`. The kit must be importable
(`uv pip install -e shared/gui-kit`, or `PYTHONPATH=shared/gui-kit`).

## Files

```
main.py                 arguments, the document, the window, scripted steps and the screenshot
screen3d/bridge3d.py    Bridge3D: the kit's DocBridge + shot, playhead, play, outliner / timeline rows, key drag
screen3d/route.py       the one place a screen edit becomes an operation call (value.set at the playhead, key marks)
screen3d/outline.py     what the outliner and timeline list (no Qt)
screen3d/render_job.py  the Render button's job (rostrum3d.mcp.render.still, its own engine process)
screen3d/steps.py       scripted steps
screen3d/sample.py      the small sample document (not a template)
screen3d/viewport.py, viewcam.py, frames.py, qml/Viewport.qml    the live viewport
qml/                    Main, Outliner, KindIcon, Timeline, RenderButton, RenderView
```

## Not yet

- Adding, deleting, renaming, grouping or reordering items from the screen (the operations exist; the command bar
  runs the ones that need no input). No drag-and-drop in the outliner.
- Moving items in the viewport (no move / turn handles yet); picking a material or camera from a list instead of
  typing its id; a colour picker popup (the kit's).
- Render settings (samples, size, png / exr) on screen: it uses `render_still`'s defaults. One render at a time;
  no cancel. No video render button yet (`render_video` exists for agents).
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
