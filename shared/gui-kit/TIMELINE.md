# The timeline kit (INTERACTION.md 1.6, 1.12; Part 5 piece 6)

*S35, 2026-10-22.* One time view, one ruler and one header for every timeline (2D's layers, Sound's arrangement and
piano roll, later 3D and the Editor). Snapping and drag feel are piece 9 (`drag.py`, `snap.py`, `SnapLine.qml`).

## The pieces

| Piece | Does |
|---|---|
| `rostrum_gui/timeview.py` | **`TimeView`**: which stretch of time is on screen. `start`, `span`, `fit`, `length`; `x_of(t, width)` / `t_of(x, width)`; `zoom(factor, frac)` keeps the moment under the pointer; `zoom_step` (Ctrl+= / Ctrl+−, around the playhead); `scroll`, `set_start`; `show_all` (Ctrl+0); `fit_to(a, b)` (F); `wheel(...)` (Ctrl zooms, Shift or a sideways swipe scrolls); `follow(t)` turns the page while playing. Never leaves the timeline; zooming out all the way is fit again. Bad input raises `ValueError`. **`TimeViewObject`**: the same for QML (`start`, `span`, `fit`, `length`, one `changed` signal; slots `zoomAt`, `zoomStep`, `scrollBy`, `setStart`, `showAll`, `fitTo`, `wheel`, `follow`, `setLength`). Screen state: no undo step, agents never move it. |
| `Ruler.qml` | Top to bottom, each band only when it has a use: the **range band** (`rangeBand`, `range`; drag → one `rangeSet(a, b)`, double-click → `rangeCleared()`), the **marker band** (`MarkerFlag.qml`: shared markers solid with a chain, own markers hollow; a name stops before the next flag and shows whole on hover), the **time scale** (first label inside the left edge, a label that would be cut is left out; `upper: [{at, text}]` adds a second line above, e.g. bars). Press / drag on the scale → `scrubbed(t)`. `view:` a `TimeViewObject` for zoom, scroll and the wheel. `newMarker()` (the app's M, the kit's Add marker button) opens `MarkerNamer.qml`: `nextMarkerName` selected ("Marker N"; TimeRuler: the first free name), a **Shared** switch when `canShare`, Enter → `markerAdded(name, shared, at)`. The ruler only emits; the app's operations do the work. |
| `TimelineHeader.qml` | Three slots, `transport` (▶, time, ⟳ Loop), `context` (the key bar, frame tools) and `view` (◇ Marker, snap, zoom, fit), and **⊟** (`foldClicked`, `compact`). Too narrow: the context slot gives way first (`contextFolded`: put those actions in the app's ⋯). |
| `HScroll.qml` | The slim scroll bar for a `TimeViewObject`, only while zoomed in (drawn 8 px, clickable 16 px). |

All existing Ruler properties and signals still work (`unit`, `duration`, `fps`, `first` / `last`, `value`,
`markers`, `editMarkers`, `scrubbed`, `markerMoved` / `Renamed` / `Removed`, `xOf` / `tOf` / `fOf` / `xOfSec` /
`secOf`). A marker without `shared` counts as shared (today every flag is the project's).

**Look and layout check:** `python shared/gui-kit/demo/timeline_preview.py [out]`. It runs four states (whole, zoomed,
naming, compact) at the four sizes, with long texts. Results: `C:\Users\Sam\.rostrum\waves\results\kit\s35\timeline\`.

## Adoption notes

**Team Priyam (Sound):**
- Replace `screensound/view.py` with `rostrum_gui.timeview.TimeView`. The maths is the same. The differences:
  - `length` is held by the view: call `set_length(song length)` when the song changes, instead of passing it in each call;
  - `span` is a property, not `span(length)`;
  - `fit_to(a, b)` sets `auto` only when `chosen=True` (pass it for the screen's own fit to a track's notes).
- In `view_slots.py`, either keep the bridge's `viewStart` / `viewSpan` / `viewFit` and forward them to the view, or put a
  `TimeViewObject` on the bridge (`backend.timeView`) and bind QML to it.
  `viewWheel` → `TimeView.wheel`; `zoomStep` → `zoom_step(factor, playhead)`; `_moved` → `follow(t)`.
- Swap `qml/HScroll.qml` for the kit's `HScroll { view: backend.timeView }` and delete the app copy.
- `BarRuler` → kit `Ruler`:
  - `upper` gets the bar labels (`[{at: seconds, text: "Bar 5"}]`, spaced as BarRuler's `every` does today);
  - `rangeBand: true`, with `range: backend.timeRange` and `onRangeSet: backend.setRange(a, b)` (the grid snap moves into
    piece 9's snap);
  - `onScrubbed: backend.setTime(t)`; the punch range stays Sound's own band (PunchBand).
- M → `ruler.newMarker()`; `onMarkerAdded` runs the marker operation. `canShare` = the song is in a project.

**Team Hem (2D):**
- `TimeRuler.qml` already wraps the kit Ruler and keeps working unchanged.
- To adopt:
  - give it `view: backend.timeView` (a `TimeViewObject` with `setLength(duration)` on load or edit) for Ctrl+wheel zoom
    at the pointer, Shift+wheel scroll and page-follow;
  - `rangeBand: true` with the 2D time range;
  - the kit's Add marker button (`AddMarker { askOn: ruler }`, as LayerTimeline does) asks the name first; on the name
    box's Enter the ruler sends `markerAdded`, and the app adds the marker (2D: RulerMenu). `addsMarkers: true` makes the
    `TimeRuler` add it itself (`markerEdit.addNamed(name, at)`, on the playhead's frame) for an app with no handler of
    its own; never both, or each marker is added twice;
  - `canShare` (Shared / own markers) is still open;
  - per marker, `shared: false` for the scene's own markers.
- Move the header row of `LayerTimeline.qml` (play, time, Preview size, Keys / Curves, the hint and its fold chevron) into
  `TimelineHeader`:
  - transport = play + time;
  - context = Preview size, Keys / Curves;
  - view = ◇ Marker, zoom, fit;
  - ⊟ replaces the chevron.
- Remove the fixed `height: markers ? 34 : 22`: the Ruler's `implicitHeight` now adds the bands it shows.
- The rows (`LayerRows`, `FrameMarks`, `CurveEditor`) keep using `ruler.xOf` / `tOf`, which now follow the view.

## Marker right-click menu and the view control (S36)

- **Marker menu.** Right-click a flag (the ruler's `editMarkers` on, and `markerSource: <the screen's MarkerWatch>`): **Rename marker**
  (starts the flag's name field), **Move to playhead**, **Colour ▸**, **Keep it only here / Share with the project** (only when the
  document is in a project), **Delete marker**. It is built from the marker operations (`marker.rename / move / colour / remove`)
  through the one action list (`rostrum_gui/marker_menu.py` → `ActionList`, drawn by `ActionMenu`), so only what applies shows
  (Move to playhead is absent when the marker already stands there). `MarkerWatch.menu(id, playhead, shared)` gives the rows and
  `MarkerWatch.choose(id, row, playhead, shared)` runs the choice as ONE marker change (undo takes it back with the rest). Share / own
  is the app's data: the ruler emits `markerShareToggled(id, nowShared)`.
- **View control.** `ViewControl { view: <CanvasView> }`, bottom-right of the main view: "Fit · 50 % ▾"; its menu is Fit, 50 %, 100 %,
  200 %, Zoom in, Zoom out with the key map's keys (a step already on is absent). `CanvasView.menu()` / `pick(value)` /
  `zoomTo(percent)` (`view_menu.py`, `view_place.py`). Screen state only.

## The key timeline (K2: 2D's, for every app with keys)
`LayerTimeline` is 2D's bottom timeline, now the kit's: header (play, time, Add marker, Keys | Curves, the height switch),
`TimeRuler` (seconds, marker flags; `frameTicks` for a tick per frame), the playhead, marker lines, snap line, drag label
and the key's Ease menu. The rows are the app's, plugged in: `rows` (a Flickable, laid under the ruler with the kit's edge
fade and scroll bar), `curves` (shown while Curves is on), `overlay` (drawn over the rows: 2D's beat lines), `footer` (room kept under the rows for an app's own row: 3D's Simulate row), `compactExtra`
(rows that stay in compact). A row's time side is `LayerTrack` (bar, `KeyDot` diamonds merged by `KeyGroups.js`,
`StretchBand` stretches, spring tails, repeat ghosts) with `cells` for the app's own marks (2D: `FrameMarks`, a drawing's
cells). `AnimPanel` is the picked animation over the settings (`allowed` hides it: 2D while drawing); `EaseCurve` its curve.
2D plugs them in at `apps/2d/screen/qml/Main.qml` and `LayerRows.qml`; 3D at `apps/3d/app/qml/SceneList.qml`.

**The curve view (`CurveEditor.qml`, PR2).** The `curves` slot takes the kit's `CurveEditor { visible: backend.curves.on;
ruler: <timeline>.ruler; labelWidth: <timeline>.labelWidth }`. `backend.curves` is an app's subclass of
`rostrum_gui/curve_view.py` `CurveView` (2D: `screen2d/curves.py`, 3D: `screen3d/curves3d.py`), which answers small hooks:
`state` (the data, then the selection), `picked_items` / `scene_items`, `fields_of(item)` (its animated (owner, prop),
parts too), `field_label` / `item_label`, `limits`, `picked_keys` / `pick_key`, `snap_targets`, `time_limits`, and
optionally `item` (2D: placed), `key_time` (2D: a layer's offset, keys on markers), `curve`. Everything else is the kit's:
which curves (the picked items', or every animated item's with nothing picked or **All curves** chosen; `canAll` only
where All shows more), the legend grouped under each item's name (click a curve or an item: hide / show), each curve fitted to its own value
range, a key drag (`key.set` {t, v}, snapped, kept in range) and a handle drag (`key.set` {ease: custom, x1 y1 x2 y2})
as one doc gesture each, and a right-click on a key = the key's Ease list (`backend.keyBar.askMenu`: the tangent kinds
are the eases). The curve numbers are `rostrum_core/keys/curve.py` (`curve_of`, `handles_of`). Screen steps, the same in
every app: `rostrum_gui/curve_steps.py` (`curves on|off|all|mine`, `curvedrag`, `handledrag`). `AnimPanel` has an
**All curves** button (`backend.curves.showAll()`) wherever the app has a curve view.

They read the app's `backend` (the same names 2D's has): `time`, `playing`, `togglePlay`, `setTime`, `frameInfo`, `markers`,
`markerEdit`, `select`, `selected`, `multi`, `layers`, `curves`, `keys`, `keyBar`, `stretch`, `timeSnap`, `beginBarDrag` /
`barDragTo` / `beginKeyDrag` / `keyDragTo` / `endDrag`. The rows' data (`rowData`: keys, stretches, bar, lines) come from
`rostrum_core.keys.animations(owner, names)`; the operations behind them (`anim.ease`, `key.scale`, `key.paste`,
`key.stagger`) are registered with `rostrum_core.keys.register_anim_ops` on the app's own items.

## Animation layers
A stack of moves laid over the Base, each with a weight (a breath over a walk; rostrum_core/keys/layers.py). The kit's
`AnimLayers.qml` goes in the play cell through `LayerTimeline { layers: AnimLayers {} }`: one small ⧉ button (lit while a
layer is chosen) opening a popover with the layers top first, the Base at the bottom and + New layer. A row: click
picks it (a person's new keys and value changes go on it, `route` in rostrum_gui/anim_layers.py; the rows show only
its keys, the app passes `rows_layer()` to its row lister), double-click renames, the switch turns it on / off,
Add | Replace, the weight slider (one drag = one change; once the weight has a key, the slider keys it at the
playhead), ⋯ for Key the weight here, Move up / down, Delete layer and its keys. The app plugs the model
(`AnimLayers(bridge)`, `backend.animLayers`) and registers the operations (`register_layer_ops`,
`register_key_ops(…, layers=True)`). 3D: apps/3d/app/screen3d/layers3d.py. 2D: not plugged yet.

## Not built yet
- The marker right-click menu (Rename · Share with the project / Keep it here only · Colour · Delete, with "3 things
  tied") and "the same name as a shared and an own marker is refused" (core marker operations).
- The range shown faintly over the rows (the host draws it from `ruler.xOfSec(range.start / end)`).
- Space+drag / middle-drag pan, Alt+wheel row height, the "Fit · 50 % ▾" view menu, compact mode's row choice (apps).
