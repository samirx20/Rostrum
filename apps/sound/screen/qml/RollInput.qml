import QtQuick
import RostrumKit

// Every click and drag on the Editor's piano roll / drum rows, in one place (the same rules as LaneInput):
// click selects alone, Ctrl+click adds / removes, Shift+click the run between; a press that moves 4 px or more
// drags every selected item in time and (notes) in pitch (Ctrl: no snapping, Shift: only in time, Alt: a copy;
// one undo step). Empty space: a click clears the selection (the playhead stays; only the ruler moves it), a drag draws a box (Ctrl adds),
// a double-click adds a note (or, on the drum rows, a hit). The Draw tool (B; V is Select): a click on empty space adds
// a note Note ▾ long (drag on: longer) or a hit. The two tools' buttons are on the dock's top line (EditorHeader). A note's right end sets its length (every selected note by the same amount, one undo
// step; the pointer shows ↔ over it). Right-click: the selection's actions, or the menu for that time.
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
    readonly property real snapPx: 6     // snapping catches within 6 px (INTERACTION.md §1.11)
    property string hover: ""
    cursorShape: mode === "handle" || hover !== "" ? Qt.SizeHorCursor : backend.tool === "draw" ? Qt.CrossCursor : Qt.ArrowCursor
    function endUnder(e) { return kind === "notes" ? backend.rollHandleAt(bars.tOf(e.x), grid.rowAt(e.y), snapPx / bars.perSec) : ({}) }
    acceptedButtons: Qt.LeftButton | Qt.RightButton
    property real x0: 0
    property real y0: 0
    property real x1: 0
    property real y1: 0
    property string hit: ""
    property string mode: ""            // "press" | "hpress" (a note's end) | "drag" | "handle" | "empty" | "box"
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
        hit = backend.rollAt(bars.tOf(e.x), grid.rowAt(e.y), snapPx / bars.perSec)
        if (e.button === Qt.RightButton) {
            mode = ""
            m.menuAt(hit !== "" ? backend.itemMenu(hit) : backend.atMenu(trackId, bars.tOf(e.x)), e.x, e.y)
            return
        }
        var h = endUnder(e)
        if (h.id) { hit = h.id; mode = "hpress"; return }
        if (hit === "" && backend.tool === "draw") {          // Draw: a click on empty space adds a note / hit there
            hit = backend.drawAt(bars.tOf(e.x), grid.rowAt(e.y))
            mode = hit !== "" && kind === "notes" ? "hpress" : ""   // dragging on sets the new note's length
            return
        }
        if (hit !== "" && !ctrl(e) && !shift(e) && !backend.picked[hit]) backend.pressSelect(hit)   // the outline now, the panel after the frame
        mode = hit !== "" ? "press" : "empty"
    }
    onPositionChanged: (e) => {
        x1 = e.x; y1 = e.y
        if (!pressed) { hover = endUnder(e).handle || ""; return }
        if (mode === "hpress" && far(e)) mode = backend.beginHandle(hit, "length") ? "handle" : ""
        if (mode === "handle") { backend.handleTo((e.x - x0) / bars.perSec, 0, ctrl(e)); return }
        if (mode === "press" && far(e)) {
            if (!backend.picked[hit]) backend.clickSelect(hit, ctrl(e), false)
            mode = backend.beginDrag(hit) ? "drag" : ""
        } else if (mode === "empty" && far(e)) {
            mode = "box"
        }
        if (mode === "drag")
            backend.dragTo((e.x - x0) / bars.perSec, kind === "notes" ? -Math.round((e.y - y0) / grid.rowH) : 0,
                           ctrl(e), shift(e), alt(e), bars.perSec)
        else if (mode === "box")
            backend.boxRoll(bars.tOf(x0), bars.tOf(x1), grid.rowAt(y0), grid.rowAt(y1), ctrl(e))
    }
    onReleased: (e) => {
        if (mode === "hpress") backend.endDrag()          // a note just drawn: its one step ends here
        if (mode === "press" || mode === "hpress") backend.clickSelect(hit, ctrl(e), shift(e))
        else if (mode === "empty") { if (!ctrl(e)) backend.pickMany([]) }     // only the ruler moves the playhead
        else if (mode === "drag" || mode === "handle") backend.endDrag()
        else if (mode === "box") backend.endBox()
        mode = ""
    }
    onCanceled: { if (mode === "drag" || mode === "handle" || mode === "hpress") backend.cancelDrag(); if (mode === "box") backend.endBox(); mode = "" }
    onDoubleClicked: (e) => {   // empty space: a note on that key, or a hit on that drum (Select tool; Draw adds on a click)
        if (backend.tool === "draw" || backend.rollAt(bars.tOf(e.x), grid.rowAt(e.y), 0) !== "") return
        mode = ""                  // the release that follows must not clear the new note's selection
        if (kind === "notes") backend.addNote(bars.tOf(e.x), Math.round(grid.rowAt(e.y)))
        else if (kind === "drums") backend.addHit(bars.tOf(e.x), grid.rowAt(e.y))
    }

    Rectangle {   // the box being dragged
        visible: m.mode === "box"
        x: Math.min(m.x0, m.x1); y: Math.min(m.y0, m.y1); width: Math.abs(m.x1 - m.x0); height: Math.abs(m.y1 - m.y0)
        color: Theme.accentSoft; border.width: 1; border.color: Theme.accent
    }
}
