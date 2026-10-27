import QtQuick
import RostrumKit
import RostrumCursors 1.0
import "Pointers.js" as Pointers
import "Tempo.js" as Tempo

// The song's ruler: the kit's Ruler (range band, seconds scale only when the right-click menu turned it on, playhead, scrub, the wheel's zoom and scroll through
// backend.timeView) with Sound's bars on its upper line, plus what is Sound's own: the punch range (with a take
// armed and punch on: a drag across the scale sets it, its edges drag; takeSetup.setPunch, a quarter beat grid,
// Ctrl = free; screen state, not an edit; the kit's CanvasCursor resize (left-right) over its edges and while it is
// drawn, the kit's chip "bar 3 → bar 5", Esc gives the range as it was) and the right-click menu (menuAt). Elsewhere
// the pointer is the kit Ruler's own. The range band's drag is one
// backend.setRange (each edge on a bar or beat line a few px away, else the nearest grid line: timing.snap); double-click clears it. xOf(t) / tOf(x) are the one mapping the rows,
// markers and piano roll use too, the kit's, following backend.timeView.
// A click or scrub on the scale (and the press that starts a punch scrub) puts the playhead through the one snap, in
// Python (backend.setTimeSnapped: markers, section edges, then the grid; the seconds line with a picture: its frames;
// Ctrl = free). `snapping` is true while that press lasts (the views show the snap line then); its release clears it.
Item {
    id: r
    objectName: "barRuler"
    signal menuAt(real t, real x, real y)
    readonly property bool snapping: kit.scrubbing || punchArea.mode === 0
    onSnappingChanged: if (!snapping) backend.endTimeSnap()
    function snapTo(x, y, free) { backend.setTimeSnapped(r.tOf(x), free, kit.onSecondsAt(y), kit.perSec) }
    readonly property int band: kit.bandH
    readonly property var range: backend.timeRange
    readonly property var song: backend.song       // the one read per change: the grids and bands over this ruler share it
    readonly property var placing: backend.blocksTempo   // the tempo map the blocks over this ruler are placed by (Blocks.timed)
    readonly property real length: song.length
    readonly property real barSec: song.spb * song.barBeats
    readonly property real start: backend.viewStart
    readonly property real perSec: kit.perSec
    function visibleX(x) { return x >= -1 && x <= width + 1 }
    readonly property real barPx: barSec * perSec
    readonly property int every: [1, 2, 4, 8, 16, 32].find(n => n * barPx >= 64) || 64   // bars per label
    function xOf(t) { return kit.xOf(t) }                    // a time → where it is drawn
    function wOf(dur) { return dur * perSec }                // a length → how wide (never shifted by the scroll)
    function tOf(x) { return kit.tOf(x) }
    readonly property var punch: typeof takeSetup !== "undefined" ? takeSetup.punchRange : []
    readonly property bool punchOn: punch.length === 2
    function punchEdge(x) {                                  // 1: the in edge under x, 2: the out edge, 0: neither
        if (!punchOn) return 0
        return Math.abs(x - xOf(punch[0])) <= 5 ? 1 : Math.abs(x - xOf(punch[1])) <= 5 ? 2 : 0
    }
    readonly property var barMarks: {   // "5" (plain bar numbers) at every `every`-th bar
        var out = [], bars = song.bars                 // each bar's start, time signature changes included
        for (var i = 0; i < bars.length; i += every) out.push({ at: bars[i], text: String(i + 1) })
        return out
    }
    implicitHeight: kit.implicitHeight
    clip: true
    // Grid Auto keeps its steps wide enough on the narrowest ruler on screen (grid_slots.setRulerWidth); told again
    // when the window takes another song's bridge (New, Open)
    readonly property var host: backend
    readonly property real shownWidth: visible ? width : 0
    function reportWidth() { if (host) host.setRulerWidth(String(r), shownWidth) }
    onShownWidthChanged: reportWidth()
    onHostChanged: reportWidth()
    Component.onCompleted: reportWidth()
    Component.onDestruction: if (host) host.setRulerWidth(String(r), 0)

    Rectangle {  // the punch range, with its two edges to drag
        visible: r.punchOn
        x: visible ? Math.round(r.xOf(r.punch[0])) : 0
        width: visible ? Math.max(1, Math.round(r.xOf(r.punch[1]) - r.xOf(r.punch[0]))) : 0
        height: r.height
        color: Qt.rgba(Theme.danger.r, Theme.danger.g, Theme.danger.b, 0.18)
        Rectangle { width: 3; height: parent.height; color: Theme.danger }
        Rectangle { x: parent.width - 3; width: 3; height: parent.height; color: Theme.danger }
    }
    PlayTime { id: playTime }
    Ruler {
        id: kit
        anchors.fill: parent
        duration: r.length; fps: 1000                        // (whole milliseconds: the grid does the snapping)
        value: playTime.value; view: backend.timeView; upper: r.barMarks; seconds: workspace.seconds
        rangeBand: true; rangeActive: backend.looping; range: r.range.length === 2 ? { start: r.range[0], end: r.range[1] } : null
        onScrubbed: (t, free) => backend.setTimeSnapped(t, free, kit.onSeconds, kit.perSec)
        onRangeSet: (a, b) => backend.setRange(a, b, workspace.seconds, kit.perSec)   // drawn on the seconds scale: exact seconds, no grid
        onRangeCleared: backend.clearRange()
    }
    MouseArea {   // above the kit's: the right-click menu, and the punch range while a take is armed with punch on
        id: punchArea
        anchors.fill: parent
        preventStealing: true
        property int mode: -1                // 0: the time, 1: a new punch range, 2: its in edge, 3: its out edge
        property real x0: 0
        property real other: 0               // the edge that stays while one is dragged
        property var was: []                 // the punch range at the press (Esc gives it back)
        property bool holding: false         // a punch drag holds Esc (dragEsc)
        acceptedButtons: Qt.LeftButton | Qt.RightButton
        HoverHandler { id: punchHover }      // (passive: the kit Ruler under it still hears the hover)
        CanvasCursor {   // over a punch edge, and while the range is drawn or an edge dragged; else the kit Ruler's pointer
            objectName: "punchCursor"
            anchors.fill: parent
            visible: punchArea.mode >= 1 || (punchArea.mode < 0 && punchHover.hovered && punchHover.point.position.y >= r.band
                                             && r.punchEdge(punchHover.point.position.x) !== 0)
            kind: Pointers.kind("trim"); angle: Pointers.turn("trim")
        }
        function letGo() { if (holding) { holding = false; dragEsc.letEsc() } }
        Connections {   // Esc while the punch range is dragged: the range as it was; the release then does nothing
            target: dragEsc
            function onCancelled() {
                if (!punchArea.holding) return
                punchArea.holding = false
                if (punchArea.was.length === 2) takeSetup.setPunch(punchArea.was[0], punchArea.was[1], true)
                punchArea.mode = -1
            }
        }
        onPressed: (m) => {
            x0 = m.x
            if (m.button === Qt.RightButton) { mode = -1; r.menuAt(r.tOf(m.x), m.x, m.y); return }
            if (!r.punchOn || m.y < r.band) { m.accepted = false; return }       // the kit's (scrub, range band)
            var e = r.punchEdge(m.x)
            mode = e ? e + 1 : 0
            was = r.punch.slice()
            if (e) other = r.punch[e === 1 ? 1 : 0]
            else r.snapTo(m.x, m.y, (m.modifiers & Qt.ControlModifier) !== 0)
        }
        onPositionChanged: (m) => {
            if (!pressed || mode < 0) return
            var free = (m.modifiers & Qt.ControlModifier) !== 0       // Ctrl = no snapping (DESIGN.md §5)
            if (mode === 0 && Math.abs(m.x - x0) > 6) mode = 1
            if (mode >= 1 && !holding && Math.abs(m.x - x0) >= 4) { holding = true; dragEsc.holdEsc() }
            if (mode === 0) r.snapTo(m.x, m.y, free)                     // the scale: scrub
            else if (mode === 1) takeSetup.setPunch(r.tOf(x0), r.tOf(m.x), free)
            else takeSetup.setPunch(r.tOf(m.x), other, free)
        }
        onReleased: { mode = -1; letGo() }
        onCanceled: { mode = -1; letGo() }
        onWheel: (w) => { w.accepted = false }
    }
    DragLabel {   // the punch range being set
        parent: r.parent; z: 1000
        at: Qt.point(r.x + punchArea.mouseX, r.y + r.height / 2)
        text: punchArea.holding && r.punchOn ? Tempo.barName(r.song, r.punch[0]) + " → " + Tempo.barName(r.song, r.punch[1]) : ""
    }
}
