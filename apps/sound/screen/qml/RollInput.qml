import QtQuick
import RostrumKit
import RostrumCursors 1.0
import "Picks.js" as Picks
import "Tempo.js" as Tempo
import "BeatWords.js" as BeatWords
import "Pointers.js" as Pointers

// Every click and drag on the Editor's piano roll / drum rows, in one place (the same rules as LaneInput):
// click selects alone, Ctrl+click adds / removes, Shift+click the run between; a press that moves 4 px or more
// drags every selected item in time and (notes) in pitch (Ctrl: no snapping, Shift: only in time, Alt: a copy;
// one undo step). Empty space: a click clears the selection (the playhead stays; only the ruler moves it), a drag draws a box (Ctrl adds),
// a double-click adds a note (or, on the drum rows, a hit). The Draw tool (B; V is Select): a click on empty space adds
// a note Note ▾ long (drag on: longer) or a hit; on the drum rows Draw is the step tool: a click on an empty step adds a hit,
// a click on a hit removes it, a drag along a row paints (or, from a hit, erases) every grid step it passes (Shift+click an accent,
// Alt+click soft; one undo step per stroke: backend.stepPress / stepTo / stepEnd). A new note or hit goes in the grid cell under the pointer (timing.snap). The two tools' buttons are on the dock's top line (EditorHeader). A note's right end (its last 6 px, inside the note: a click
// just past it is empty space, so Draw adds the next note there) sets its length (every selected note by the same amount, one undo
// step; a chip beside the pointer says the length, "1/8"); its left end (its first 6 px, at most a third of it) moves its start, the end staying put.
// Right-click: the item's actions (the kit's short menu, then Quantise, Humanise, Transpose ▸), or on empty space what
// belongs there (Add note here, Paste here, Select all on this track, Select every C4: backend.rollMenu).
// The pointer says what a press does there (CANVAS.md §4; the kit's CanvasCursor, CURSORS.md): `pointer` names the zone,
// `cur` shows it. A note's body `pick` (Alt down: the copy badge, mouse still), a closed hand while it moves (a copy
// badge while Alt copies), its ends `resize` sideways (the length), empty space with Draw `make`, and what a Draw click
// would remove `pick` with the red remove badge, lit red (a hit; a note with Alt: Draw+Alt click erases it, Draw+Alt
// drag still copies). With Draw, a faint note or hit sits where a click would put it (backend.rollHover: the click's
// own snap, key lock and length), its key lit on the keyboard (PLAN S1). Locked during a drag (the mode says it).
// A drag shows the kit's value chip by the pointer: a move "+1 bar 2 beats · +3 semitones" (what the dragged note
// moved, snap included), a length "1/8". Esc during a drag (after the 4 px) puts everything back, no undo step
// (dragEsc; the drum stroke and a note's end too). A box has no chip; Esc gives back the selection as it was before the box.
// A drum hit is caught only on the diamond you see (tol), never on the empty step beside it.
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
    property var over: ({})             // what is under the pointer, or the ghost a Draw click would make (backend.rollHover)
    property bool altHeld: false        // Alt, as the pointer last moved
    property bool copying: false        // a drag with Alt: a copy
    property bool erasing: false        // the drum stroke began on a hit: it erases
    readonly property bool drawTool: backend.tool === "draw"
    onDrawToolChanged: over = ({})
    readonly property bool onEnd: over.part === "length" || over.part === "noteStart"
    // a Draw click here removes what is under the pointer: a hit (the step tool), a note's body with Alt
    readonly property bool removes: drawTool && !!over.id && (kind === "drums" || (over.part === "body" && altHeld))
    readonly property string pointer: mode === "drag" ? (copying ? "copy" : "moving")
                                    : mode === "handle" || mode === "hpress" ? "trim"
                                    : mode === "steps" ? (erasing ? "erase" : "draw")
                                    : mode === "erase" ? "erase"
                                    : mode !== "" ? ""
                                    : removes ? "erase" : onEnd ? "trim" : over.part === "body" ? "pick"
                                    : drawTool ? "draw" : ""
    CanvasCursor {   // the zone's pointer: [kind, badge, angle] per name (CURSORS.md, "Moving Sound's stand-in over")
        id: cur
        objectName: "rollCursor"; anchors.fill: parent
        readonly property var look: ({ pick: ["pick", ""], moving: ["hand-grab", ""], copy: ["hand-grab", "copy"],
                                       trim: ["resize", ""], draw: ["make", ""], erase: ["pick", "remove"] })[m.pointer] || ["pick", ""]
        kind: look[0]; angle: 0
        // Alt on a body: the copy badge, mouse still, from Sound's own Alt watch (backend.altWatch, the same as the red
        // light), not the kit's altBadge: in Sound's window the kit's key watch missed Alt's release (reported to the kit)
        badge: m.pointer === "pick" && m.mode === "" && m.over.part === "body" && m.altHeld ? "copy" : look[1]
    }
    // How near (seconds) a click must be to catch an item: the snapping 6 px; on the drum rows the diamond as drawn
    // (RollGrid.hitHalf, 1 px round it): as wide either side of the hit's time as the diamond is at the pointer's height,
    // -1 off it. Every press, hover and double-click asks with this one tolerance.
    function tol(y) {
        if (kind !== "drums") return snapPx / bars.perSec
        var half = grid.hitHalf + 1 - Math.abs(y - (Math.floor(y / grid.rowH) + 0.5) * grid.rowH)
        return half > 0 ? half / bars.perSec : -1
    }
    function endUnder(e) { return kind === "notes" ? backend.rollHandleAt(bars.tOf(e.x), grid.rowAt(e.y), snapPx / bars.perSec) : ({}) }
    function hoverAt(x, y, e) {         // one answer a move; the ghost's key lit on the keyboard
        altHeld = !!e && alt(e)
        over = backend.rollHover(bars.tOf(x), grid.rowAt(y), tol(y), 1 / bars.perSec, drawTool)
        var g = over.ghost
        grid.hoverKey = g && g.keys ? g.keys[0] : -1
    }
    function leave() { over = ({}); grid.hoverKey = -1 }
    Connections {   // Alt pressed or let go with the pointer still: the pointer and the red light follow at once
        target: backend.altWatch
        function onChanged(held) { if (m.containsMouse && !m.pressed) m.altHeld = held }
    }
    onExited: leave()
    acceptedButtons: Qt.LeftButton | Qt.RightButton
    property real x0: 0
    property real y0: 0
    property real x1: 0
    property real y1: 0
    property string hit: ""
    property string handle: ""          // the note end pressed: "length" (right) or "noteStart" (left)
    property bool drawn: false          // the press drew the note(s) under it (Draw): the release keeps what it selected
    property string mode: ""            // "press" | "hpress" (a note's end) | "drag" | "handle" | "empty" | "box" | "steps" (Draw on a drum row) | "erase" (Draw+Alt on a note)
    property real lastT: 0              // where the pointer last was over the roll (seconds): the bar a drum row's Fill acts on
    readonly property bool busy: mode === "drag" || mode === "box" || mode === "handle"
    function ctrl(e) { return (e.modifiers & Qt.ControlModifier) !== 0 }
    function shift(e) { return (e.modifiers & Qt.ShiftModifier) !== 0 }
    function alt(e) { return (e.modifiers & Qt.AltModifier) !== 0 }
    function far(e) { return Math.abs(e.x - x0) >= 4 || Math.abs(e.y - y0) >= 4 }

    onWheel: (w) => {   // Ctrl zooms, Shift / sideways scrolls in time (the Timeline's view); else up and down
        leave()                          // the view moves under a still pointer: no ghost left behind
        if (!backend.viewWheel(w.angleDelta.x, w.angleDelta.y, ctrl(w), shift(w), w.x / width, true))
            flick.contentY = Math.max(0, Math.min(flick.contentHeight - flick.height, flick.contentY - w.angleDelta.y / 2))
    }
    PinchGrow {}
    // Esc while a drag runs: everything back as it was, no undo step; the release that follows does nothing
    function holds(md) { return md === "drag" || md === "handle" || md === "steps" || md === "box" }
    onModeChanged: { if (holds(mode)) dragEsc.holdEsc(); else dragEsc.letEsc() }
    Connections {
        target: dragEsc
        function onCancelled() { if (m.mode === "box") backend.cancelBox(); else if (m.holds(m.mode)) backend.cancelDrag(); else return; m.mode = "" }
    }
    // The move chip: where the dragged note (hit) was at the press, and how far it is now, in bars and beats (and keys)
    property var moveFrom: null
    function blockOf(id) { var b = grid ? grid.blocks : []; for (var i = 0; i < b.length; i++) if (b[i].id === id) return b[i]; return null }
    function moveWords() {
        var now = blockOf(hit), f = moveFrom, song = bars.song
        if (!now || !f) return ""
        var db = Tempo.along(song.beats, now.t, song.spb) - Tempo.along(song.beats, f.t, song.spb)
        var dk = now.keys && f.keys ? now.keys[0] - f.keys[0] : 0
        return Pointers.beats(backend, db, song.barBeats) + (dk ? " · " + BeatWords.semitones(dk) : "")
    }
    onPressed: (e) => {
        backend.focusArea("roll")
        x0 = x1 = e.x; y0 = y1 = e.y
        copying = false
        hit = backend.rollAt(bars.tOf(e.x), grid.rowAt(e.y), tol(e.y))
        if (e.button === Qt.RightButton) {
            mode = ""
            m.menuAt(hit !== "" ? backend.blockMenu(hit, bars.tOf(e.x)) : backend.rollMenu(bars.tOf(e.x), grid.rowAt(e.y), 1 / bars.perSec), e.x, e.y)
            return
        }
        if (backend.tool === "draw" && kind === "drums") {   // the step tool: a click adds / removes a hit, a drag paints / erases along the row
            erasing = hit !== ""
            mode = backend.stepPress(bars.tOf(e.x), grid.rowAt(e.y), 1 / bars.perSec, tol(e.y), (shift(e) ? 1 : 0) | (alt(e) ? 2 : 0)) ? "steps" : ""
            return
        }
        var h = endUnder(e)
        drawn = false
        if (h.id) { hit = h.id; handle = h.handle; mode = "hpress"; return }
        if (hit !== "" && backend.tool === "draw" && kind === "notes" && alt(e)) { mode = "erase"; return }   // a click erases, a drag copies
        if (hit === "" && backend.tool === "draw") {          // Draw: a click on empty space adds a note / hit there
            hit = backend.drawAt(bars.tOf(e.x), grid.rowAt(e.y), 1 / bars.perSec)
            mode = hit !== "" && kind === "notes" ? "hpress" : ""   // dragging on sets the new note's length
            drawn = true
            handle = "length"
            return
        }
        if (hit !== "" && !ctrl(e) && !shift(e) && !Picks.all(backend, backend.pickStamp)[hit]) backend.pressSelect(hit)   // the outline now, the panel after the frame
        mode = hit !== "" ? "press" : "empty"
    }
    onPositionChanged: (e) => {
        x1 = e.x; y1 = e.y
        lastT = bars.tOf(e.x)
        if (!pressed) { hoverAt(e.x, e.y, e); return }
        if (mode === "steps") { backend.stepTo(bars.tOf(e.x), 1 / bars.perSec); return }
        if (mode === "erase" && far(e)) mode = "press"                 // Draw+Alt dragged on: a copy, as with Select
        if (mode === "hpress" && far(e)) mode = backend.beginHandle(hit, handle) ? "handle" : ""
        if (mode === "handle") { backend.handleTo((e.x - x0) / bars.perSec, 0, ctrl(e)); return }
        if (mode === "press" && far(e)) {
            if (!Picks.all(backend, backend.pickStamp)[hit]) backend.clickSelect(hit, ctrl(e), false)
            var b0 = blockOf(hit)
            moveFrom = b0 ? { t: b0.t, keys: b0.keys ? [b0.keys[0]] : null } : null
            mode = backend.beginDrag(hit) ? "drag" : ""
        } else if (mode === "empty" && far(e)) {
            mode = "box"
        }
        if (mode === "drag") {
            copying = alt(e)
            backend.dragTo((e.x - x0) / bars.perSec, kind === "notes" ? grid.rowAt(e.y) - grid.rowAt(y0) : kind === "drums" ? Math.round((e.y - y0) / grid.rowH) : 0,
                           ctrl(e), shift(e), alt(e), bars.perSec)
        } else if (mode === "box")
            backend.boxRoll(bars.tOf(x0), bars.tOf(x1), grid.rowAt(y0), grid.rowAt(y1), ctrl(e))
    }
    onReleased: (e) => {
        if (mode === "steps") backend.stepEnd()          // the stroke's one step ends here
        else if (mode === "erase") backend.eraseNote(hit)
        else {
            if (mode === "hpress") backend.endDrag()          // a note just drawn: its one step ends here
            if (mode === "press" || (mode === "hpress" && !drawn)) backend.clickSelect(hit, ctrl(e), shift(e))   // drawn: it picked what it made (a stamped chord: all of it)
            else if (mode === "empty") { if (!ctrl(e)) backend.pickMany([]) }     // only the ruler moves the playhead
            else if (mode === "drag" || mode === "handle") backend.endDrag()
            else if (mode === "box") backend.endBox()
        }
        mode = ""
        if (e.button === Qt.LeftButton) hoverAt(e.x, e.y, e)     // what is under the pointer now (the note just drawn there)
    }
    onCanceled: { if (mode === "drag" || mode === "handle" || mode === "hpress" || mode === "steps") backend.cancelDrag(); if (mode === "box") backend.endBox(); mode = "" }
    onDoubleClicked: (e) => {   // empty space: a note on that key, or a hit on that drum (Select tool; Draw adds on a click)
        if (backend.tool === "draw" || backend.rollAt(bars.tOf(e.x), grid.rowAt(e.y), tol(e.y)) !== "") return
        mode = ""                  // the release that follows must not clear the new note's selection
        if (kind === "notes") backend.addNote(bars.tOf(e.x), Math.round(grid.rowAt(e.y)), 1 / bars.perSec)
        else if (kind === "drums") backend.addHit(bars.tOf(e.x), grid.rowAt(e.y), 1 / bars.perSec)
    }

    // What a Draw click would make (faint) or remove (lit red): one small item each, moved with the pointer.
    readonly property var ghost: !pressed && drawTool && over.ghost ? over.ghost : null
    readonly property bool lit: removes && mode === ""
    Repeater {   // a note, or each key of the chord Note ▾ › Draw stamps (by count: a move re-places the same items)
        model: m.ghost && m.ghost.keys ? m.ghost.keys.length : 0
        Rectangle {
            required property int index
            readonly property int key: m.ghost ? m.ghost.keys[index] : 0
            visible: !!m.ghost && m.grid.shows(key)
            x: m.ghost ? m.bars.xOf(m.ghost.t) : 0; y: m.grid.rowOf(key) * m.grid.rowH + 1
            width: m.ghost ? Math.max(4, m.bars.xOf(m.ghost.end) - x - 1) : 0; height: m.grid.rowH - 2; radius: 3
            color: m.grid.roll.hue; opacity: 0.55       // faint, still seen on the dark rows (real-window check)
        }
    }
    Diamond {   // a hit
        shown: !!m.ghost && m.ghost.row !== undefined
        at: shown ? Qt.point(m.bars.xOf(m.ghost.t), (m.ghost.row + 0.5) * m.grid.rowH) : Qt.point(0, 0)
        color: m.grid ? m.grid.roll.hue : "transparent"; opacity: 0.55; side: m.grid ? m.grid.hitHalf * Math.SQRT2 : 0
    }
    Repeater {   // a note a click would remove (each of its keys)
        model: m.lit && m.over.keys ? m.over.keys : []
        Rectangle { required property var modelData
                    x: m.bars.xOf(m.over.t); y: m.grid.rowOf(modelData) * m.grid.rowH + 1
                    width: Math.max(4, m.bars.wOf(m.over.dur) - 1); height: m.grid.rowH - 2; radius: 3
                    color: Theme.danger; opacity: 0.75 }
    }
    Diamond {   // a hit a click would remove
        shown: m.lit && m.over.row !== undefined && m.over.row >= 0
        at: shown ? Qt.point(m.bars.xOf(m.over.t), (m.over.row + 0.5) * m.grid.rowH) : Qt.point(0, 0)
        color: Theme.danger; side: m.grid ? m.grid.hitHalf * Math.SQRT2 : 0
    }
    component Diamond: Rectangle {   // the roll's hit diamond (Marks.js: its corners hitHalf from its centre)
        property bool shown: false
        property point at
        visible: shown
        property real side: 0                                // (an inline component can't read `m`: set where used)
        x: at.x - side / 2; y: at.y - side / 2; width: side; height: side; rotation: 45; antialiasing: true
    }
    DragLabel {   // a note's length while its end is dragged ("1/8"); a move's amount ("+1 bar 2 beats · +3 semitones")
        objectName: "rollChip"
        text: m.mode === "handle" && m.grid ? backend.lengthWords(m.hit, m.grid.blocks)
            : m.mode === "drag" && m.grid ? (m.grid.blocks, m.moveWords()) : ""
        hint: m.mode === "drag" ? (m.copying ? "copy" : "") : ""
        at: Qt.point(m.x1, m.y1)
    }

    Rectangle {   // the box being dragged
        visible: m.mode === "box"
        x: Math.min(m.x0, m.x1); y: Math.min(m.y0, m.y1); width: Math.abs(m.x1 - m.x0); height: Math.abs(m.y1 - m.y0)
        color: Theme.accentSoft; border.width: 1; border.color: Theme.accent
    }
}
