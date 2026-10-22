# The timeline kit (INTERACTION.md 1.6, 1.12; Part 5 piece 6)

*S35, 2026-10-22.* One time view, one ruler and one header for every timeline (2D's layers, Sound's arrangement and
piano roll, later 3D and the Editor). Snapping and drag feel are piece 9 (`drag.py`, `snap.py`, `SnapLine.qml`).

## The pieces

| Piece | Does |
|---|---|
| `rostrum_gui/timeview.py` | **`TimeView`**: which stretch of time is on screen. `start`, `span`, `fit`, `length`; `x_of(t, width)` / `t_of(x, width)`; `zoom(factor, frac)` keeps the moment under the pointer; `zoom_step` (Ctrl+= / Ctrl+−, around the playhead); `scroll`, `set_start`; `show_all` (Ctrl+0); `fit_to(a, b)` (F); `wheel(...)` (Ctrl zooms, Shift or a sideways swipe scrolls); `follow(t)` turns the page while playing. Never leaves the timeline; zooming out all the way is fit again. Bad input raises `ValueError`. **`TimeViewObject`**: the same for QML (`start`, `span`, `fit`, `length`, one `changed` signal; slots `zoomAt`, `zoomStep`, `scrollBy`, `setStart`, `showAll`, `fitTo`, `wheel`, `follow`, `setLength`). Screen state: no undo step, agents never move it. |
| `Ruler.qml` | Top to bottom, each band only when it has a use: the **range band** (`rangeBand`, `range`; drag → one `rangeSet(a, b)`, double-click → `rangeCleared()`), the **marker band** (`MarkerFlag.qml`: shared markers solid with a chain, own markers hollow; a name stops before the next flag and shows whole on hover), the **time scale** (first label inside the left edge, a label that would be cut is left out; `upper: [{at, text}]` adds a second line above, e.g. bars). Press / drag on the scale → `scrubbed(t)`. `view:` a `TimeViewObject` for zoom, scroll and the wheel. `newMarker()` (the app's M) opens `MarkerNamer.qml`: "Marker N" selected, a **Shared** switch when `canShare`, Enter → `markerAdded(name, shared, at)`. The ruler only emits; the app's operations do the work. |
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
  - `canShare`, and `onMarkerAdded` → the marker add operation (today `markerEdit.add(at)` takes only the time: it needs the name and Shared too);
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

## Not built yet
- The marker right-click menu (Rename · Share with the project / Keep it here only · Colour · Delete, with "3 things
  tied") and "the same name as a shared and an own marker is refused" (core marker operations).
- The range shown faintly over the rows (the host draws it from `ruler.xOfSec(range.start / end)`).
- Space+drag / middle-drag pan, Alt+wheel row height, the "Fit · 50 % ▾" view menu, compact mode's row choice (apps).
