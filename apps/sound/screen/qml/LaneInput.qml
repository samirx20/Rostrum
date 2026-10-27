import QtQuick
import RostrumKit
import RostrumCursors 1.0
import "MixFormat.js" as F
import "Picks.js" as Picks
import "Pointers.js" as Pointers
import "Tempo.js" as Tempo

// Every click and drag on the arrangement's lanes, in one place (select first, then act: INTERACTION.md §1.3, §1.10).
// On an item: click selects it alone, Ctrl+click adds / removes, Shift+click takes the run between on its track;
// double-click selects it and opens the Editor. A press that moves 4 px or more drags every selected item (Ctrl: no
// snapping, Shift: only in time, Alt: a copy; clips also go to the track under the pointer; one undo step).
// A selected clip's handles (handles.py): edges trim (Alt on the right edge: stretch), top corners fade, bottom-right
// stretches, the level line sets its volume. The pointer says what a press does there: the kit's CanvasCursor
// (CURSORS.md, names in Pointers.js; CANVAS.md §4): pick on a body (Alt held: the copy badge, mouse still), resize
// on an edge (Alt on the right edge: the centre badge, a stretch), resize ±45° on the fade corners, up-down on the
// level line, the closed hand while a move runs; on an open automation lane make (a click adds a point) and
// pick+point over a point. The kind stays the press's until the release. While dragging, the kit's chip by the
// pointer says the amount ("+1 bar 2 beats", "Fade 120 ms", "−3.0 dB", "Stretch 125 %", a point's "−6.0 dB at
// bar 2.3"), and Esc puts everything back with no undo step (dragEsc). On empty lane space: a click clears the selection and makes that track
// the Editor's (the playhead stays: only the ruler moves it); a drag draws a box that selects what it touches across tracks (Ctrl
// adds; Esc: the selection as before). Right-click: an item's actions (selected alone first unless already selected), or the lane's own menu.
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
    property string hover: ""           // the zone under the pointer: a handle's name, "body" (an item), "" (empty)
    property string handleTrack: ""     // the pressed item's row and its block at the press (the chip's "from")
    property var handleFrom: null
    // the drag's amount: a binding on what the lanes draw now (they redraw after the move that changed them)
    readonly property string chip: mode === "drag" ? moveChip() : mode === "handle" ? chipNow() : mode === "point" && holding ? pointChip() : ""
    property string chipHint: ""
    property string pointTrack: ""      // an automation point drag's row
    property var boxWas: []             // the selection when a box started (Esc gives it back)
    property bool holding: false        // this drag holds Esc (dragEsc)
    property int row0: -1
    // "press" (on an item) | "hpress" (on a handle) | "drag" | "handle" | "empty" | "box" | "point" | "gone" (Esc'd, until the release)
    property string mode: ""
    readonly property bool busy: mode === "drag" || mode === "box" || mode === "handle"
    readonly property real snapPx: 6     // snapping catches within 6 px (INTERACTION.md §1.11)
    readonly property var zones: ({ start: "trim", end: "trim", fadeIn: "fade", fadeOut: "fadeOut", stretch: "stretch", level: "level",
                                    body: "pick", point: "point", line: "draw" })
    // the pointer's name (Pointers.js): the press's while it lasts (locked), else the zone under the pointer
    readonly property string pointer: mode === "drag" ? "moving" : mode === "press" ? "pick"
                                    : mode === "handle" || mode === "hpress" ? zones[handle] || "pick"
                                    : mode === "point" ? "point" : mode === "" ? zones[hover] || "pick" : "pick"
    CanvasCursor {
        objectName: "laneCursor"
        anchors.fill: parent
        kind: Pointers.kind(m.pointer); badge: Pointers.badge(m.pointer); angle: Pointers.turn(m.pointer)
        altBadge: m.pointer === "pick" || m.pointer === "moving" ? "copy"                    // Alt: drag a copy
                  : m.mode === "" && m.hover === "end" ? "centre" : ""                       // Alt on the right edge: stretch
    }
    function hold() { if (!holding) { holding = true; dragEsc.holdEsc() } }
    function letGo() { if (holding) { holding = false; dragEsc.letEsc() } }
    Connections {   // Esc while this drag runs: everything as before, no undo step; the release then does nothing
        target: dragEsc
        function onCancelled() {
            if (!m.holding) return
            m.holding = false
            if (m.mode === "drag" || m.mode === "point" || m.mode === "handle") backend.cancelDrag()
            else if (m.mode === "box") { backend.endBox(); backend.pickMany(m.boxWas) }
            m.mode = "gone"; m.chipHint = ""
        }
    }
    function hintOf(e) {   // what the held keys do to a move now (the chip's second line)
        var h = []
        if (shift(e)) h.push("only in time")
        if (alt(e)) h.push("copy")
        if (ctrl(e)) h.push("no snapping")
        return h.join(" · ")
    }
    function beatsBetween(was, now) {   // seconds → the move in beats, as the song's beat lines count them
        var song = bars.song
        return Tempo.along(song.beats, now, song.spb) - Tempo.along(song.beats, was, song.spb)
    }
    function placed(id, first) {   // {b, row}: a block as the lanes draw it now, its row at the press first, then any row (a clip moved across)
        var b = tl.blockOf(first, id), row = first
        for (var i = 0; !b && i < tl.rows.length; i++) if (!tl.rows[i].mix) { row = tl.rows[i].id; b = tl.blockOf(row, id) }
        return { b: b, row: row }
    }
    function blockNow(id, first) { return placed(id, first).b }
    // the dragged clip's box on the Timeline, which the chip keeps clear of (none while nothing is dragged)
    readonly property rect chipAvoid: {
        if (mode !== "drag" && mode !== "handle") return Qt.rect(0, 0, 0, 0)
        var q = placed(hit, handleTrack), b = q.b, sp = b ? tl.rowSpan(q.row) : null
        if (!sp) return Qt.rect(0, 0, 0, 0)
        var x = m.mapToItem(tl, bars.xOf(b.t), 0).x
        return Qt.rect(x, sp.top, b.dur * bars.perSec, sp.bottom - sp.top)
    }
    function moveChip() {   // a body move's amount: the pressed item's place now against the press ("+1 bar 2 beats")
        var b = blockNow(hit, handleTrack), f = handleFrom
        return b && f ? Pointers.beats(backend, beatsBetween(f.t, b.t), bars.song.barBeats) : ""
    }
    function pointChip() {   // the dragged point's value and place: "−6.0 dB at bar 2.3"
        var r = tl.rows.find(x => x.id === pointTrack), a = r ? tl.autoOf(r) : null, p = backend.point
        var pt = a && p.track === pointTrack && p.index >= 0 ? a.points[p.index] : null
        if (!pt) return ""
        var v = a.gain ? F.faderText(pt.v) : (a.lo < 0 && pt.v > 0 ? "+" : "") + Number(pt.v).toFixed(2)
        return v + " at " + Tempo.barName(bars.song, pt.t)
    }
    function yFrac(y) { return Math.max(0, Math.min(1, (y - laneTop - 8) / (tl.laneH - 16))) }
    function ctrl(e) { return (e.modifiers & Qt.ControlModifier) !== 0 }
    function shift(e) { return (e.modifiers & Qt.ShiftModifier) !== 0 }
    function alt(e) { return (e.modifiers & Qt.AltModifier) !== 0 }
    function far(e) { return Math.abs(e.x - x0) >= 4 || Math.abs(e.y - y0) >= 4 }
    function rowIndex(y) { var s = tl.slot(Math.max(0, Math.min(height - 1, y))); return s.i }
    function boxRow(y) {   // a box's edge: the row at y; in a gap (+ Track) or below every row, the row above it (none above: the first)
        for (var yy = Math.min(height - 1, y); yy >= 0; yy -= 2) { var i = tl.slot(yy).i; if (i >= 0) return i }
        return 0
    }
    function under(e) {   // {r, s, t, lane}: the row, its slot, the time and the height in the row (0 top .. 1 bottom)
        var s = tl.slot(e.y)
        if (s.i < 0) return null
        var r = tl.rows[s.i]
        return { r: r, s: s, t: bars.tOf(e.x), lane: Math.max(0, Math.min(1, (e.y - s.top - 3) / Math.max(1, tl.hOf(r) - 8))) }
    }
    function zoneAt(e) {   // what a press here would take: a handle, an item's body, an automation point or line, or nothing
        var h = handleUnder(e)
        if (h.handle) return h.handle
        var u = under(e)
        var a = u && u.s.lane ? tl.autoOf(u.r) : null
        if (a) {
            var top = u.s.laneTop + 8, ph = tl.laneH - 16
            return Pointers.pointNear(a.points, bars.xOf, v => top + (1 - (v - a.lo) / (a.hi - a.lo)) * ph, e.x, e.y, 7) >= 0 ? "point" : "line"
        }
        return u && !u.r.mix && !(u.s.lane && tl.autoOf(u.r)) && backend.blockAt(u.r.id, u.t, u.lane, snapPx / bars.perSec) !== "" ? "body" : ""
    }
    function chipNow() {   // the handle drag's amount, from the block as its lane draws it now against the press
        var b = tl.blockOf(handleTrack, hit), f = handleFrom, song = bars.song
        if (!b || !f) return ""
        if (handle === "start" || handle === "end") {
            var was = handle === "start" ? f.t : f.t + f.dur, now = handle === "start" ? b.t : b.t + b.dur
            return Pointers.beats(backend, beatsBetween(was, now), song.barBeats)
        }
        if (handle === "fadeIn" || handle === "fadeOut") {
            var ms = Math.round((b[handle] || 0) * 1000)
            return "Fade " + (ms < 1000 ? ms + " ms" : (ms / 1000).toFixed(2) + " s")
        }
        if (handle === "level") {
            var db = 20 * Math.log((b.volume || 1e-4)) / Math.LN10
            return (db < -0.05 ? "−" : db > 0.05 ? "+" : "") + Math.abs(db).toFixed(1) + " dB"
        }
        return "Stretch " + Math.round(b.dur / Math.max(1e-6, f.dur) * 100) + " %"
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
    onExited: { hover = ""; Pointers.hoverLane(bars, "", 0) }
    onPressed: (e) => {
        backend.focusArea("arrange")
        Pointers.hoverLane(bars, "", 0)                         // a press ends the lane's tip
        x0 = x1 = e.x; y0 = y1 = e.y
        var u = under(e)
        row0 = u ? u.s.i : -1
        if (!u) { mode = "empty"; return }
        var a = tl.autoOf(u.r)
        if (u.s.lane && a && e.button === Qt.RightButton) {     // on a point: its menu (Delete point)
            laneTop = u.s.laneTop; mode = ""
            var pm = backend.pointMenu(u.r.id, a.target, a.lane, u.t, yFrac(e.y), 7 / bars.perSec, 7 / (tl.laneH - 16))
            if (pm.length) { m.menuAt(pm, e.x, e.y); return }
        }
        if (u.s.lane && a && e.button === Qt.LeftButton) {
            laneTop = u.s.laneTop; mode = "point"; pointTrack = u.r.id
            backend.laneBegin(u.r.id, a.target, a.lane, u.t, yFrac(e.y), 7 / bars.perSec, 7 / (tl.laneH - 16), shift(e), 1 / bars.perSec)
            return
        }
        hit = u.r.mix ? "" : backend.blockAt(u.r.id, u.t, u.lane, snapPx / bars.perSec)
        if (e.button === Qt.RightButton) {
            mode = ""
            m.menuAt(hit !== "" ? backend.blockMenu(hit, u.t) : backend.atMenu(u.r.mix ? "" : u.r.id, u.t, 1 / bars.perSec), e.x, e.y)
            return
        }
        var h = handleUnder(e)
        if (h.id) {
            hit = h.id; handle = h.handle === "end" && alt(e) ? "stretch" : h.handle     // Alt on the right edge: stretch
            rowH = Math.max(1, tl.hOf(u.r) - 8); mode = "hpress"; handleTrack = u.r.id
            var b = tl.blockOf(u.r.id, hit)
            handleFrom = b ? { t: b.t, dur: b.dur, volume: b.volume || 1 } : null
            return
        }
        if (hit !== "" && !ctrl(e) && !shift(e) && !Picks.all(backend, backend.pickStamp)[hit]) backend.pressSelect(hit)
        mode = hit !== "" ? "press" : "empty"
        var p = hit !== "" ? tl.blockOf(u.r.id, hit) : null
        handleTrack = u.r.id; handleFrom = p ? { t: p.t, dur: p.dur, volume: p.volume || 1 } : null
    }
    onPositionChanged: (e) => {
        x1 = e.x; y1 = e.y
        if (!pressed) {
            hover = zoneAt(e)
            var o = under(e)                                    // the lane under the pointer shows its cut label's tip
            Pointers.hoverLane(bars, o && !o.s.lane && !o.r.mix ? o.r.id : "", e.x)
            return
        }
        if (mode === "press" && far(e)) {
            if (!Picks.all(backend, backend.pickStamp)[hit]) backend.clickSelect(hit, ctrl(e), false)
            mode = backend.beginDrag(hit) ? "drag" : ""
        } else if (mode === "hpress" && far(e)) {
            mode = backend.beginHandle(hit, handle) ? "handle" : ""
        } else if (mode === "empty" && far(e)) {
            boxWas = Object.keys(Picks.all(backend, backend.pickStamp))
            mode = "box"
        }
        if (mode === "drag" || mode === "handle" || mode === "box" || (mode === "point" && far(e))) hold()   // Esc is the drag's now
        if (mode === "drag") {
            var r = rowIndex(e.y)
            backend.dragTrack(r >= 0 && !shift(e) && !tl.rows[r].mix ? tl.rows[r].id : "")
            backend.dragTo((e.x - x0) / bars.perSec, 0, ctrl(e), shift(e), alt(e), bars.perSec)
            chipHint = hintOf(e)
        }
        else if (mode === "handle") { backend.handleTo((e.x - x0) / bars.perSec, (e.y - y0) / rowH, ctrl(e)); chipHint = ctrl(e) ? "no snapping" : "" }
        else if (mode === "point") { backend.laneDrag(bars.tOf(e.x), yFrac(e.y), shift(e)) }
        else if (mode === "box") {
            var a = boxRow(y0), b = boxRow(y1), ids = []                 // every row the box crosses
            for (var i = Math.min(a, b); i <= Math.max(a, b) && i < tl.rows.length; i++) ids.push(tl.rows[i].id)
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
        letGo(); mode = ""; chipHint = ""
    }
    onDoubleClicked: (e) => {   // goes in: the item selected, the Editor open on it
        var u = under(e)
        var id = u && !u.r.mix ? backend.blockAt(u.r.id, u.t, u.lane, snapPx / bars.perSec) : ""
        if (id === "" && u && editorSide.isVoiceTrack(u.r.id)) { editorSide.startTyping(u.r.id, bars.tOf(e.x)); return }
        if (id !== "") { backend.select(id); workspace.setDock("editor") }
    }
    onCanceled: { if (mode === "drag" || mode === "point" || mode === "handle") backend.cancelDrag(); if (mode === "box") backend.endBox(); letGo(); mode = ""; chipHint = "" }

    DragLabel {   // the drag's amount by the pointer (on the Timeline: the rows sit above this area and would hide it)
        parent: m.tl; z: 1000
        text: m.chip; hint: m.chipHint; avoid: m.chipAvoid
        at: { var p = m.mapToItem(m.tl, m.x1, m.y1); return Qt.point(p.x, p.y) }
    }
    Rectangle {   // the box being dragged
        visible: m.mode === "box"
        x: Math.min(m.x0, m.x1); y: Math.min(m.y0, m.y1); width: Math.abs(m.x1 - m.x0); height: Math.abs(m.y1 - m.y0)
        color: Theme.accentSoft; border.width: 1; border.color: Theme.accent
    }
}
