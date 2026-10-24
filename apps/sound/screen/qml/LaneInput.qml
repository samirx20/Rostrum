import QtQuick
import RostrumKit

// Every click and drag on the arrangement's lanes, in one place (select first, then act: INTERACTION.md §1.3, §1.10).
// On an item: click selects it alone, Ctrl+click adds / removes, Shift+click takes the run between on its track;
// double-click selects it and opens the Editor. A press that moves 4 px or more drags every selected item (Ctrl: no
// snapping, Shift: only in time, Alt: a copy; clips also go to the track under the pointer; one undo step).
// A selected clip's handles (handles.py): edges trim, top corners fade, bottom-right stretches, the level line sets
// its volume; the pointer shape says which. On empty lane space: a click clears the selection and makes that track
// the Editor's (the playhead stays: only the ruler moves it); a drag draws a box that selects what it touches across tracks (Ctrl
// adds). Right-click: an item's actions (selected alone first unless already selected), or the lane's own menu.
// An open automation lane keeps its own clicks (backend.laneBegin …). `tl` is the Timeline, `bars` its ruler.
MouseArea {
    id: m
    property var tl
    property var bars
    property var flick
    signal menuAt(var entries, real x, real y)
    preventStealing: true
    hoverEnabled: true
    acceptedButtons: Qt.LeftButton | Qt.RightButton
    property real x0: 0
    property real y0: 0
    property real x1: 0
    property real y1: 0
    property real laneTop: 0
    property real rowH: 1
    property string hit: ""
    property string handle: ""
    property string hover: ""
    property int row0: -1
    property string mode: ""            // "press" (on an item) | "hpress" (on a handle) | "drag" | "handle" | "empty" | "box" | "point"
    readonly property bool busy: mode === "drag" || mode === "box" || mode === "handle"
    readonly property real snapPx: 6     // snapping catches within 6 px (INTERACTION.md §1.11)
    cursorShape: ({ start: Qt.SizeHorCursor, end: Qt.SizeHorCursor, fadeIn: Qt.SizeBDiagCursor,
                    fadeOut: Qt.SizeFDiagCursor, stretch: Qt.SizeFDiagCursor, level: Qt.SizeVerCursor })[mode === "handle" ? handle : hover] || Qt.ArrowCursor
    function yFrac(y) { return Math.max(0, Math.min(1, (y - laneTop - 8) / (tl.laneH - 16))) }
    function ctrl(e) { return (e.modifiers & Qt.ControlModifier) !== 0 }
    function shift(e) { return (e.modifiers & Qt.ShiftModifier) !== 0 }
    function alt(e) { return (e.modifiers & Qt.AltModifier) !== 0 }
    function far(e) { return Math.abs(e.x - x0) >= 4 || Math.abs(e.y - y0) >= 4 }
    function rowIndex(y) { var s = tl.slot(Math.max(0, Math.min(height - 1, y))); return s.i }
    function under(e) {   // {r, s, t, lane}: the row, its slot, the time and the height in the row (0 top .. 1 bottom)
        var s = tl.slot(e.y)
        if (s.i < 0) return null
        var r = tl.rows[s.i]
        return { r: r, s: s, t: bars.tOf(e.x), lane: Math.max(0, Math.min(1, (e.y - s.top - 3) / Math.max(1, tl.hOf(r) - 8))) }
    }
    function handleUnder(e) {
        var u = under(e)
        return u && !u.r.mix && !(u.s.lane && tl.autoOf(u.r)) ? backend.handleAt(u.r.id, u.t, u.lane, snapPx / bars.perSec) : ({})
    }

    onWheel: (w) => {
        if (!backend.viewWheel(w.angleDelta.x, w.angleDelta.y, ctrl(w), shift(w), w.x / width, flick.contentHeight > flick.height + 1))
            flick.contentY = Math.max(0, Math.min(flick.contentHeight - flick.height, flick.contentY - w.angleDelta.y / 2))
    }
    PinchGrow {}
    onPressed: (e) => {
        backend.focusArea("arrange")
        x0 = x1 = e.x; y0 = y1 = e.y
        var u = under(e)
        row0 = u ? u.s.i : -1
        if (!u) { mode = "empty"; return }
        var a = tl.autoOf(u.r)
        if (u.s.lane && a && e.button === Qt.LeftButton) {
            laneTop = u.s.laneTop; mode = "point"
            backend.laneBegin(u.r.id, a.target, a.lane, u.t, yFrac(e.y), 7 / bars.perSec, 7 / (tl.laneH - 16), shift(e))
            return
        }
        hit = u.r.mix ? "" : backend.blockAt(u.r.id, u.t, u.lane, snapPx / bars.perSec)
        if (e.button === Qt.RightButton) {
            mode = ""
            m.menuAt(hit !== "" ? backend.blockMenu(hit, u.t) : backend.atMenu(u.r.mix ? "" : u.r.id, u.t), e.x, e.y)
            return
        }
        var h = handleUnder(e)
        if (h.id) { hit = h.id; handle = h.handle; rowH = Math.max(1, tl.hOf(u.r) - 8); mode = "hpress"; return }
        if (hit !== "" && !ctrl(e) && !shift(e) && !backend.picked[hit]) backend.pressSelect(hit)
        mode = hit !== "" ? "press" : "empty"
    }
    onPositionChanged: (e) => {
        x1 = e.x; y1 = e.y
        if (!pressed) { var h = handleUnder(e); hover = h.handle || ""; return }
        if (mode === "press" && far(e)) {
            if (!backend.picked[hit]) backend.clickSelect(hit, ctrl(e), false)
            mode = backend.beginDrag(hit) ? "drag" : ""
        } else if (mode === "hpress" && far(e)) {
            mode = backend.beginHandle(hit, handle) ? "handle" : ""
        } else if (mode === "empty" && far(e)) {
            mode = "box"
        }
        if (mode === "drag") {
            var r = rowIndex(e.y)
            backend.dragTrack(r >= 0 && !shift(e) && !tl.rows[r].mix ? tl.rows[r].id : "")
            backend.dragTo((e.x - x0) / bars.perSec, 0, ctrl(e), shift(e), alt(e), bars.perSec)
        }
        else if (mode === "handle") backend.handleTo((e.x - x0) / bars.perSec, (e.y - y0) / rowH, ctrl(e))
        else if (mode === "point") backend.laneDrag(bars.tOf(e.x), yFrac(e.y), shift(e))
        else if (mode === "box") {
            var a = rowIndex(y0), b = rowIndex(y1), ids = []
            for (var i = Math.min(a, b); i <= Math.max(a, b); i++) if (i >= 0) ids.push(tl.rows[i].id)
            backend.boxSelect(ids, bars.tOf(x0), bars.tOf(x1), ctrl(e))
        }
    }
    onReleased: (e) => {
        if (mode === "press" || mode === "hpress") backend.clickSelect(hit, ctrl(e), shift(e))
        else if (mode === "empty") {
            backend.clearPoint()
            if (!ctrl(e)) backend.pickMany([])
            if (row0 >= 0 && !tl.rows[row0].mix) backend.focusTrack(tl.rows[row0].id)     // only the ruler moves the playhead
        }
        else if (mode === "drag" || mode === "point" || mode === "handle") backend.endDrag()
        else if (mode === "box") backend.endBox()
        mode = ""
    }
    onDoubleClicked: (e) => {   // goes in: the item selected, the Editor open on it
        var u = under(e)
        var id = u && !u.r.mix ? backend.blockAt(u.r.id, u.t, u.lane, snapPx / bars.perSec) : ""
        if (id === "" && u && editorSide.isVoiceTrack(u.r.id)) { editorSide.startTyping(u.r.id, bars.tOf(e.x)); return }
        if (id !== "") { backend.select(id); workspace.setDock("editor") }
    }
    onCanceled: { if (mode === "drag" || mode === "point" || mode === "handle") backend.cancelDrag(); if (mode === "box") backend.endBox(); mode = "" }

    Rectangle {   // the box being dragged
        visible: m.mode === "box"
        x: Math.min(m.x0, m.x1); y: Math.min(m.y0, m.y1); width: Math.abs(m.x1 - m.x0); height: Math.abs(m.y1 - m.y0)
        color: Theme.accentSoft; border.width: 1; border.color: Theme.accent
    }
}
