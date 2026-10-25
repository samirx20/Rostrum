import QtQuick
import RostrumKit

// Every click and drag on the Editor's piano roll / drum rows, in one place (the same rules as LaneInput):
// click selects alone, Ctrl+click adds / removes, Shift+click the run between; a press that moves 4 px or more
// drags every selected item in time and (notes) in pitch (Ctrl: no snapping, Shift: only in time, Alt: a copy;
// one undo step). Empty space: a click clears the selection (the playhead stays; only the ruler moves it), a drag draws a box (Ctrl adds),
// a double-click adds a note (or, on the drum rows, a hit). The Draw tool (B; V is Select): a click on empty space adds
// a note Note ▾ long (drag on: longer) or a hit; on the drum rows Draw is the step tool: a click on an empty step adds a hit,
// a click on a hit removes it, a drag along a row paints (or, from a hit, erases) every grid step it passes (Shift+click an accent,
// Alt+click soft; one undo step per stroke: backend.stepPress / stepTo / stepEnd). A new note or hit goes in the grid cell under the pointer (timing.snap). The two tools' buttons are on the dock's top line (EditorHeader). A note's right end (its last 6 px, inside the note: a click
// just past it is empty space, so Draw adds the next note there) sets its length (every selected note by the same amount, one undo
// step; the pointer shows ↔ over it); its left end (its first 6 px, at most a third of it) moves its start, the end staying put.
// Right-click: the item's actions (the kit's short menu, then Quantise, Humanise, Transpose ▸), or on empty space what
// belongs there (Add note here, Paste here, Select all on this track, Select every C4: backend.rollMenu).
MouseArea {
    id: m
    property var grid
    property var bars
    property var flick
    property string kind
    property string trackId
    signal menuAt(var entries, real x, real y)
    preventStealing: true
    hoverEnabled: true
    enabled: !!bars && !!grid            // no pointer before its ruler and rows are linked (a roll being made or freed)
    readonly property real snapPx: 6     // snapping catches within 6 px (INTERACTION.md §1.11); a note's end handle is its last 6 px
    property string hover: ""
    cursorShape: mode === "handle" || hover !== "" ? Qt.SizeHorCursor : backend.tool === "draw" ? Qt.CrossCursor : Qt.ArrowCursor
    // How near (seconds) a click must be to catch an item: the snapping 6 px, and on the drum rows the whole diamond
    // (RollGrid.hitHalf) either side of the hit's time. Every press and double-click asks with this one tolerance.
    function tol() { return (kind === "drums" ? Math.max(snapPx, grid.hitHalf + 1) : snapPx) / bars.perSec }
    function endUnder(e) { return kind === "notes" ? backend.rollHandleAt(bars.tOf(e.x), grid.rowAt(e.y), snapPx / bars.perSec) : ({}) }
    acceptedButtons: Qt.LeftButton | Qt.RightButton
    property real x0: 0
    property real y0: 0
    property real x1: 0
    property real y1: 0
    property string hit: ""
    property string handle: ""          // the note end pressed: "length" (right) or "noteStart" (left)
    property string mode: ""            // "press" | "hpress" (a note's end) | "drag" | "handle" | "empty" | "box" | "steps" (Draw on a drum row)
    property real lastT: 0              // where the pointer last was over the roll (seconds): the bar a drum row's Fill acts on
    readonly property bool busy: mode === "drag" || mode === "box" || mode === "handle"
    function ctrl(e) { return (e.modifiers & Qt.ControlModifier) !== 0 }
    function shift(e) { return (e.modifiers & Qt.ShiftModifier) !== 0 }
    function alt(e) { return (e.modifiers & Qt.AltModifier) !== 0 }
    function far(e) { return Math.abs(e.x - x0) >= 4 || Math.abs(e.y - y0) >= 4 }

    onWheel: (w) => {   // Ctrl zooms, Shift / sideways scrolls in time (the Timeline's view); else up and down
        if (!backend.viewWheel(w.angleDelta.x, w.angleDelta.y, ctrl(w), shift(w), w.x / width, true))
            flick.contentY = Math.max(0, Math.min(flick.contentHeight - flick.height, flick.contentY - w.angleDelta.y / 2))
    }
    PinchGrow {}
    onPressed: (e) => {
        backend.focusArea("roll")
        x0 = x1 = e.x; y0 = y1 = e.y
        hit = backend.rollAt(bars.tOf(e.x), grid.rowAt(e.y), tol())
        if (e.button === Qt.RightButton) {
            mode = ""
            m.menuAt(hit !== "" ? backend.blockMenu(hit, bars.tOf(e.x)) : backend.rollMenu(bars.tOf(e.x), grid.rowAt(e.y), 1 / bars.perSec), e.x, e.y)
            return
        }
        if (backend.tool === "draw" && kind === "drums") {   // the step tool: a click adds / removes a hit, a drag paints / erases along the row
            mode = backend.stepPress(bars.tOf(e.x), grid.rowAt(e.y), 1 / bars.perSec, tol(), (shift(e) ? 1 : 0) | (alt(e) ? 2 : 0)) ? "steps" : ""
            return
        }
        var h = endUnder(e)
        if (h.id) { hit = h.id; handle = h.handle; mode = "hpress"; return }
        if (hit === "" && backend.tool === "draw") {          // Draw: a click on empty space adds a note / hit there
            hit = backend.drawAt(bars.tOf(e.x), grid.rowAt(e.y), 1 / bars.perSec)
            mode = hit !== "" && kind === "notes" ? "hpress" : ""   // dragging on sets the new note's length
            handle = "length"
            return
        }
        if (hit !== "" && !ctrl(e) && !shift(e) && !backend.picked[hit]) backend.pressSelect(hit)   // the outline now, the panel after the frame
        mode = hit !== "" ? "press" : "empty"
    }
    onPositionChanged: (e) => {
        x1 = e.x; y1 = e.y
        lastT = bars.tOf(e.x)
        if (!pressed) { hover = endUnder(e).handle || ""; return }
        if (mode === "steps") { backend.stepTo(bars.tOf(e.x), 1 / bars.perSec); return }
        if (mode === "hpress" && far(e)) mode = backend.beginHandle(hit, handle) ? "handle" : ""
        if (mode === "handle") { backend.handleTo((e.x - x0) / bars.perSec, 0, ctrl(e)); return }
        if (mode === "press" && far(e)) {
            if (!backend.picked[hit]) backend.clickSelect(hit, ctrl(e), false)
            mode = backend.beginDrag(hit) ? "drag" : ""
        } else if (mode === "empty" && far(e)) {
            mode = "box"
        }
        if (mode === "drag")
            backend.dragTo((e.x - x0) / bars.perSec, kind === "notes" ? grid.rowAt(e.y) - grid.rowAt(y0) : kind === "drums" ? Math.round((e.y - y0) / grid.rowH) : 0,
                           ctrl(e), shift(e), alt(e), bars.perSec)
        else if (mode === "box")
            backend.boxRoll(bars.tOf(x0), bars.tOf(x1), grid.rowAt(y0), grid.rowAt(y1), ctrl(e))
    }
    onReleased: (e) => {
        if (mode === "steps") { backend.stepEnd(); mode = ""; return }          // the stroke's one step ends here
        if (mode === "hpress") backend.endDrag()          // a note just drawn: its one step ends here
        if (mode === "press" || mode === "hpress") backend.clickSelect(hit, ctrl(e), shift(e))
        else if (mode === "empty") { if (!ctrl(e)) backend.pickMany([]) }     // only the ruler moves the playhead
        else if (mode === "drag" || mode === "handle") backend.endDrag()
        else if (mode === "box") backend.endBox()
        mode = ""
    }
    onCanceled: { if (mode === "drag" || mode === "handle" || mode === "hpress" || mode === "steps") backend.cancelDrag(); if (mode === "box") backend.endBox(); mode = "" }
    onDoubleClicked: (e) => {   // empty space: a note on that key, or a hit on that drum (Select tool; Draw adds on a click)
        if (backend.tool === "draw" || backend.rollAt(bars.tOf(e.x), grid.rowAt(e.y), tol()) !== "") return
        mode = ""                  // the release that follows must not clear the new note's selection
        if (kind === "notes") backend.addNote(bars.tOf(e.x), Math.round(grid.rowAt(e.y)), 1 / bars.perSec)
        else if (kind === "drums") backend.addHit(bars.tOf(e.x), grid.rowAt(e.y), 1 / bars.perSec)
    }

    Rectangle {   // the box being dragged
        visible: m.mode === "box"
        x: Math.min(m.x0, m.x1); y: Math.min(m.y0, m.y1); width: Math.abs(m.x1 - m.x0); height: Math.abs(m.y1 - m.y0)
        color: Theme.accentSoft; border.width: 1; border.color: Theme.accent
    }
}
