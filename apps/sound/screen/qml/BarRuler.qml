import QtQuick
import RostrumKit

// Bars and beats along a width, from the song's tempo map (song.beats: every beat's time, so tempo changes move
// the ticks) and beats per bar: a number at each labelled bar (its
// start in seconds after it, dimmer), beat ticks, the playhead's head. Press or drag sets the time.
// With a track armed and punch on (the take panel), the punch range is shaded here too: a drag across the ruler
// sets it, its edges drag (takeSetup.setPunch: a quarter beat grid, Ctrl = free; screen state, not an edit).
// xOf(t) / tOf(x) are the one mapping the rows, markers and piano roll use too: backend.viewStart and
// backend.viewSpan (the zoom and scroll) are the one place that says which stretch of the song is on screen.
// The range band (the top `band` px, INTERACTION.md §1.6): drag on it for the time range (backend.setRange: snapped
// to the grid, Ctrl = free; screen state, shaded here and faintly over the rows by the host); double-click clears it.
// Below it, the time scale: click or drag moves the playhead (scrub). Right-click: the ruler's menu (menuAt).
// Wheel: Ctrl zooms around the pointer, Shift or a sideways swipe scrolls (the one rule, in backend.viewWheel).
Item {
    id: r
    signal menuAt(real t, real x, real y)
    readonly property int band: 7
    readonly property var range: backend.timeRange
    readonly property var song: backend.song
    readonly property real length: song.length
    readonly property real barSec: song.spb * song.beatsPerBar
    readonly property real start: backend.viewStart
    readonly property real perSec: width / Math.max(backend.viewSpan, 0.001)
    function visibleX(x) { return x >= -1 && x <= width + 1 }
    readonly property real barPx: barSec * perSec
    readonly property int every: [1, 2, 4, 8, 16, 32].find(n => n * barPx >= 64) || 64   // bars per label
    readonly property bool showSeconds: every * barPx >= 92
    function xOf(t) { return (t - start) * perSec }         // a time → where it is drawn
    function wOf(dur) { return dur * perSec }               // a length → how wide (never shifted by the scroll)
    function tOf(x) { return Math.max(0, Math.min(length, start + x / perSec)) }
    readonly property var punch: typeof takeSetup !== "undefined" ? takeSetup.punchRange : []
    readonly property bool punchOn: punch.length === 2
    function punchEdge(x) {                                  // 1: the in edge under x, 2: the out edge, 0: neither
        if (!punchOn) return 0
        return Math.abs(x - xOf(punch[0])) <= 5 ? 1 : Math.abs(x - xOf(punch[1])) <= 5 ? 2 : 0
    }
    implicitHeight: 22
    clip: true

    Rectangle {  // the punch range, with its two edges to drag
        visible: r.punchOn
        x: visible ? Math.round(r.xOf(r.punch[0])) : 0
        width: visible ? Math.max(1, Math.round(r.xOf(r.punch[1]) - r.xOf(r.punch[0]))) : 0
        height: r.height
        color: Qt.rgba(Theme.danger.r, Theme.danger.g, Theme.danger.b, 0.18)
        Rectangle { width: 3; height: parent.height; color: Theme.danger }
        Rectangle { x: parent.width - 3; width: 3; height: parent.height; color: Theme.danger }
    }
    Repeater {   // beat ticks (when they are far enough apart), bar ticks taller
        model: r.song.beats
        delegate: Rectangle {
            required property int index
            required property real modelData
            readonly property bool bar: index % r.song.beatsPerBar === 0
            readonly property real gap: index + 1 < r.song.beats.length ? r.song.beats[index + 1] - modelData : r.song.spb
            visible: (bar || gap * r.perSec >= 10) && r.visibleX(x)
            x: Math.round(r.xOf(modelData)); y: r.height - height
            width: 1; height: bar ? 8 : 4; color: bar ? Theme.lineHover : Theme.line
        }
    }
    Repeater {   // labels
        model: Math.floor((r.song.beats.length - 1) / (r.song.beatsPerBar * r.every)) + 1
        delegate: Row {
            required property int index
            readonly property real t: r.song.beats[index * r.every * r.song.beatsPerBar] || 0
            x: Math.round(r.xOf(t)) + 4; y: r.band - 1; spacing: 5
            visible: r.xOf(t) >= -4 && r.xOf(t) < r.width - 20      // a label that would be cut at the left is left out
            Text { text: index * r.every + 1; color: Theme.fg2; font.family: uiFont; font.pixelSize: Theme.label
                   font.features: { "tnum": 1 } }
            Text { visible: r.showSeconds; text: (Math.round(parent.t * 10) / 10) + " s"; color: Theme.fg4
                   font.family: uiFont; font.pixelSize: Theme.label - 1; font.features: { "tnum": 1 }
                   anchors.baseline: parent.children[0].baseline }
        }
    }
    MouseArea {
        anchors.fill: parent
        preventStealing: true
        hoverEnabled: true
        property int mode: 0                 // 0: the time, 1: a new punch range, 2: its in edge, 3: its out edge, 4: a time range
        property real x0: 0
        property real other: 0               // the edge that stays while one is dragged
        cursorShape: r.punchEdge(mouseX) || mouseY < r.band ? Qt.SizeHorCursor : Qt.PointingHandCursor
        acceptedButtons: Qt.LeftButton | Qt.RightButton
        onDoubleClicked: (m) => { if (m.y < r.band) backend.clearRange() }
        onPressed: (m) => {
            x0 = m.x
            if (m.button === Qt.RightButton) { mode = -1; r.menuAt(r.tOf(m.x), m.x, m.y); return }
            if (m.y < r.band) { mode = 4; return }
            var e = r.punchEdge(m.x)
            mode = e ? e + 1 : 0
            if (e) other = r.punch[e === 1 ? 1 : 0]
            else backend.setTime(r.tOf(m.x))
        }
        onPositionChanged: (m) => {
            if (!pressed) return
            var free = (m.modifiers & Qt.ControlModifier) !== 0       // Ctrl = no snapping (DESIGN.md §5)
            if (mode === 0 && r.punchOn && Math.abs(m.x - x0) > 6) mode = 1
            if (mode === 0) backend.setTime(r.tOf(m.x))                  // the scale: scrub
            else if (mode === 1) takeSetup.setPunch(r.tOf(x0), r.tOf(m.x), free)
            else if (mode === 4 && Math.abs(m.x - x0) >= 4) backend.setRange(r.tOf(x0), r.tOf(m.x), free)
            else if (mode === 2 || mode === 3) takeSetup.setPunch(r.tOf(m.x), other, free)
        }
        onReleased: mode = 0
        onWheel: (w) => backend.viewWheel(w.angleDelta.x, w.angleDelta.y, (w.modifiers & Qt.ControlModifier) !== 0,
                                          (w.modifiers & Qt.ShiftModifier) !== 0, w.x / r.width, false)
    }
    Rectangle {   // the range band: a faint strip, the time range strong in it
        width: r.width; height: r.band; color: Qt.rgba(1, 1, 1, 0.03)
        Rectangle {
            visible: r.range.length === 2
            x: visible ? Math.max(0, r.xOf(r.range[0])) : 0; height: parent.height; radius: 2
            width: visible ? Math.max(2, Math.min(r.width, r.xOf(r.range[1])) - x) : 0
            color: Qt.rgba(Theme.accent.r, Theme.accent.g, Theme.accent.b, backend.looping ? 0.85 : 0.5)
        }
    }
    Rectangle {  // the playhead: a line through the ruler, its head at the top
        visible: r.visibleX(x)
        x: Math.round(r.xOf(backend.time)); width: 1; height: r.height; color: Theme.accent
        Rectangle { x: -4; y: 0; width: 9; height: 8; radius: 2; color: Theme.accent }
    }
}
