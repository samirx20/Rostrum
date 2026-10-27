# Drag, snap and the canvas view: how an app plugs in

*Team Sam, S35, 2026-10-22. Builds INTERACTION.md Part 5 pieces 9 (drag and snap) and 15 (canvas view). The rules
themselves are INTERACTION.md 1.10 (drag feel), 1.11 (snapping) and 1.12 (zoom and pan).*

## The pieces

| Piece | File | Does |
|---|---|---|
| Snap | `rostrum_gui/snap.py` | No Qt. `Target(kind, name, at)`: something a drag may catch (`kind` from `RANK`: frame, marker, playhead, edge, centre, key, measure, section, beat, guide, layout, spacing, grid; an unknown kind fails). `snap(value, targets, scale, free, step)` → `Caught(value, target)`: the strongest kind within **6 screen px** (scale = screen px per unit; 0 fails), nearest among one kind; nothing within reach → the nearest `step` (whole frames in time) or the value as dragged. `free` (Ctrl, or the Snap switch off) catches nothing. `frames(dt, fps)` → "+6 f"; `label(words, caught)` → "+6 f · drop"; `tie(value, caught)` → "#drop" / "#drop+0.2" on a marker (rostrum_core.marker_times' syntax), else the number. |
| Drag | `rostrum_gui/drag.py` | `PointerDrag(x, y, open)`: one press. It opens the document drag (`open()` → an `edits.Drag` / `Scrub`) only once the pointer has moved **4 px**, so a click records nothing. `move(x, y, mods)` → True while it is a drag; `preview(calls)`; `cancel()` (Esc: the document goes back, no undo step); `release()` → the one change, or None. `Mods.of(modifiers)`: Ctrl = `free`, Alt = `copy`, Shift = `straight`. **Esc cancels every PointerDrag in one place** (`drag_esc.py`: once a press is a drag it holds the window's Esc, before any popup, field or "step back" hears it; released or cancelled, Esc is the window's again). `grabbed(x0, y0)`: where the thing goes now, the grab point kept under the pointer. `hint_of(mods, kind)` ("keep ratio · from centre", "15° steps") for the chip's second line. `straight(dx, dy)`, `turn_steps(deg)` (15°). Label words: `words_xy`, `words_size`, `words_angle`, `words_span`, `words_db`. `DragView` (QObject): what QML shows while a drag runs: `text`, `x`, `y`, `caught`, `lineAt`, `lineName`, `vertical`; `show(...)`, `clear()`. |
| Canvas view | `rostrum_gui/canvasview.py` | `CanvasView` (QObject): `zoom`, `panX`, `panY`, `fitted`, `label` ("Fit · 50 %"). `view = canvas × zoom + pan`, in one place: `to_view` / `to_canvas` (QML: `toView` / `toCanvas`). `zoomAt(z, x, y)` keeps the canvas point under the pointer; `zoomBy` (pinch); `wheel(ax, ay, x, y, modifiers)` (Ctrl zooms, Shift sideways). Pan: `pans(button)` (middle, or any with `setSpace(true)`), `panPress` / `panMove` / `panRelease`, `panBy`. `job(name)` runs the key map's view jobs `zoom_in`, `zoom_out`, `fit_all`, `actual_size`, `fit` (F: the selection from `setSelection`, else everything from `setContent`). Zoom 1 %–6400 %; a fit stops at 400 % and follows the window's size; a fit with no view size or an empty box fails. |
| Snap line | `qml/RostrumKit/SnapLine.qml` | The thin magenta line with the caught thing's name in a chip. `at`, `name`, `vertical`, optional `from` / `to`. |
| Value chip | `qml/RostrumKit/DragLabel.qml` | The value chip by the pointer (INTERACTION.md 1.22 rule 8): 16 px below-right of `at`, flips near the parent's edge, never covers `avoid` (the dragged thing's box), tabular figures; `hint` adds what a held key does; it stays 600 ms after the drag ends, held still. `beside: true`: just right of `at` (a timeline row's dragged key). `text`, `hint`, `at`, `avoid`. |

Hook up in QML:

```qml
SnapLine  { visible: dv.caught; at: dv.lineAt; name: dv.lineName; vertical: dv.vertical }
DragLabel { text: dv.text; hint: dv.hint; at: Qt.point(dv.x, dv.y) }   // dv.show(text, x, y, …, hint=hint_of(mods, "turn"))
```

Keys: the window's `KeyMap` already makes the shortcuts and calls `hub.key(job)`; the app's hub sends the view jobs
(`canvasview.JOBS`) to `view.job(job)`. No key strings are typed in the view.

The view is screen state: no undo step, never saved, never moved by an agent.

## Adoption notes

**Team Hem (2D).** Nothing in `apps/` was changed. Move over, then delete the app copies:
- `screen2d/time_snap.py`: `RANK`, `Target`, `snap`, `label` → kit `snap.Target` / `snap.snap(t, found, scale=px_per_second, free=ctrl, step=1 / fps)` / `snap.frames` + `snap.label`. Keep only `targets(bridge, …)` (2D's own list of what can be caught). The drag passes its **scale** (px per second) instead of a pre-made seconds distance. Kind names: 2D's `edge`, `key`, `measure`, `beat`, `marker`, `playhead` exist as they are. `TimeSnap` → kit `DragView` (`show(text, x, y, line_at, line_name)`); place the label from the dragged key's time and row as today.
- `bar_drag.py`'s marker tie → `snap.tie(value, caught)`.
- `screen2d/snap.py` (the canvas box snap: edges and centre lines of a box on two axes, with the extent lines) stays 2D's for now; its `DISTANCE` and `threshold(zoom)` → `snap.DISTANCE` / `snap.reach(zoom)`, and `straight` → `drag.straight`. If 3D or the Editor needs box snapping, it moves into the kit then.
- `snapper.py`: keep the target gathering; read Ctrl / Shift through `drag.Mods.of(modifiers)`.
- `qml/CanvasView.qml` (zoom, pan, fit, fitBox, steps) → kit `CanvasView`; `Stage.qml` maps through `toView` / `toCanvas`; `ViewControls.qml` shows `view.label` and its menu calls `view.job(...)`; replace the typed `Shortcut { sequence: "Ctrl+0" }` with the key map. Kit zoom steps add 1 %; kit fit margin is 32 px (2D had 24). `view_steps.py` calls the same slots.
- `qml/DragLabel.qml`, `qml/SnapLine.qml` → kit `DragLabel` / `SnapLine` (the kit label takes `text` instead of reading `backend.timeSnap`).
- Every press-to-drag (handles, bars, keys) → `drag.PointerDrag`, which gives the 4 px rule and Esc in one place.

**Team Priyam (Sound).**
- `screensound/timing.py`: keep `Grid` and the tempo maths; its grid step is the `step` argument. `snap(t, root, free, grid)` becomes: gather `Target`s (markers, playhead, clip edges, section edges, bars / beats) and call `snap.snap(t, targets, scale=px_per_second, free=free or not grid.on, step=…)`; for a grid in beats, snap in beats (pass the beat and px per beat) and turn the result back into seconds through the tempo map. Today Sound snaps only to the grid; markers and the playhead now come first, within 6 px (not 8).
- A drop on a marker writes `snap.tie(...)` ("#drop+0.25"), the form `write_like` already keeps.
- `LaneInput.qml`, `RollInput.qml`, `BarRuler.qml` each test "4 px" themselves → `drag.PointerDrag` (and Esc cancels through it).
- The drag label and line → kit `DragLabel` / `SnapLine` via a `DragView`.

## Not built yet

- A Theme token for the snap magenta (it sits in `SnapLine.qml` until Theme gets one).
- Equal-gap feedback (showing the distance of equal spacing) and the faint copy left where the item was.
- The view controls widget itself ("Fit · 50 % ▾" and its menu): `CanvasView.label` is ready for it.
- A kit demo and layout-check states for SnapLine / DragLabel.
