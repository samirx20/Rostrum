import QtQuick
import "."

// The one ruler for time (INTERACTION.md 1.6 › Ruler): seconds (unit "seconds", 0..duration) or frames (unit
// "frames", first..last, last is the final frame so the width ends one past it). Top to bottom, each band only when
// it has a use (rule of individuality):
//   range band (rangeBand, 8 px): drag = one rangeSet(a, b) on release (seconds), double-click = rangeCleared();
//   marker band (markers, or editMarkers): MarkerFlag.qml per marker, shared solid with a chain, own hollow;
//   time scale: ticks and labels (the first inside the left edge; a label that would be cut is left out), with an
//     optional upper line the app fills (`upper`: [{at seconds, text}], e.g. Sound's bars over seconds).
// Press or drag on the scale emits scrubbed(value), in the ruler's unit: the app's playhead op does the seeking.
// newMarker() (the app's M key) opens a name field at the playhead with a Shared switch when canShare; Enter emits
// markerAdded(name, shared, at seconds) and the app's marker operation adds it. The kit never edits on its own.
// Right-click on a flag (editMarkers, and `markerSource`: the screen's MarkerWatch, rostrum_gui/markers.py): its menu,
// built from the marker operations. Rename, Move to playhead, Colour and Delete are done there as one change each;
// "Shared / Only here" is the app's (markerShareToggled(id, nowShared)), shown only when canShare.
// `view` (a rostrum_gui.timeview.TimeViewObject, seconds): zoom and scroll, and the wheel over the ruler (Ctrl zooms
// at the pointer, Shift scrolls); without it the ruler shows the whole length. xOf(v) / tOf(x) (alias fOf) are the
// one mapping the rows use too.
Item {
    id: r
    property string unit: "seconds"
    property real duration: 1          // seconds
    property real fps: 30
    property int first: 0              // frames
    property int last: 47
    property real value: 0             // the playhead: seconds or a frame
    property var markers: []           // [{id, name, at, colour, shared}], at in seconds (either unit)
    property bool editMarkers: false   // drag a flag = markerMoved, double-click = rename, × = delete
    property var view: null            // TimeViewObject: which stretch is on screen (none: all of it)
    property bool rangeBand: false     // the app has a time range (loop, export, notes)
    property var range: null           // {start, end} in seconds, or null
    property bool seconds: true        // the seconds scale (ticks and labels); an app whose `upper` line is its main scale can hide it
    property var upper: []             // the scale's upper line: [{at, text}] in seconds; empty: one line
    property bool canShare: false      // the document is in a project: new markers may be shared
    property var markerSource: null    // a MarkerWatch: gives the right-click menu and runs its choices
    signal scrubbed(real t)
    signal markerMoved(string id, real at)        // seconds, on whole frames
    signal markerRenamed(string id, string name)
    signal markerRemoved(string id)
    signal markerAdded(string name, bool shared, real at)
    signal markerShareToggled(string id, bool shared)    // the menu's "Shared / Only here": the app flips it
    signal rangeSet(real a, real b)               // seconds, a < b, on whole frames
    signal rangeCleared()

    readonly property bool frames: unit === "frames"
    readonly property real total: frames ? Math.max(1, last + 1 - first) : Math.max(duration, 0.001)   // whole length
    readonly property real origin: (frames ? first : 0) + (view ? view.start * (frames ? fps : 1) : 0)
    readonly property real span: view ? Math.max(view.span * (frames ? fps : 1), 0.001) : total
    readonly property real perUnit: width / span
    readonly property real perSec: perUnit
    // label every `major` (at least ~90 px / ~70 px apart), small ticks every `minor`
    readonly property real major: frames ? ([1, 2, 5, 10, 20, 50, 100, 200, 500, 1000, 5000].find(n => n * perUnit >= 70) || 10000)
                                         : ([0.1, 0.25, 0.5, 1, 2, 5, 10, 30, 60, 300].find(s => s * perUnit >= 90) || 600)
    readonly property real minor: frames ? (major >= 10 ? major / (major % 4 === 0 ? 4 : 5) : 1)
                                         : major / (major === 1 || major === 2 ? 4 : 5)
    readonly property int tick0: Math.ceil(origin / minor - 1e-6)
    function xOf(v) { return (v - origin) * perUnit }
    function tOf(x) { const v = origin + x / perUnit; return frames ? v : Math.max(0, Math.min(duration, v)) }
    function fOf(x) { return tOf(x) }
    function xOfSec(s) { return xOf(frames ? s * fps : s) }           // a time in seconds (markers), either unit
    function nextX(at) {   // where the next marker after `at` stands (a flag's name stops before it)
        let x = width + 1
        for (const m of markers) if (m.at > at) x = Math.min(x, xOfSec(m.at))
        return x
    }
    function secOf(x) { const v = tOf(x); return Math.max(0, Math.round((frames ? v : v * fps)) / fps) }
    function label(v) {
        if (frames) return v
        return v >= 60 ? Math.floor(v / 60) + ":" + ("0" + Math.round(v % 60)).slice(-2) : (Math.round(v * 100) / 100) + "s"
    }
    function openMarkerMenu(flag, marker, x, y) {
        if (!markerSource) return
        const sec = frames ? value / fps : value
        mm.flag = flag; mm.marker = marker; mm.sec = sec
        mm.entries = markerSource.menu(marker.id, sec, marker.shared !== false)
        if (mm.entries.length) mm.openAt(x, y)
    }
    function newMarker() { namer.x = Math.max(0, Math.min(xOf(value) - 8, width - namer.width))
                           namer.ask("Marker " + (markers.length + 1)) }

    // the bands, top down; the scale takes the rest (an app's fixed height under the natural one squeezes the
    // labels up beside the flags, as before)
    readonly property int bandH: rangeBand ? 8 : 0
    readonly property int flagTop: bandH
    readonly property bool flagRow: markers.length > 0 || editMarkers
    readonly property int labelTop: bandH + (flagRow && height >= bandH + 30 + (upper.length ? 12 : 0) ? 18 : 5)
    implicitHeight: bandH + (flagRow ? 18 : 0) + (upper.length ? (seconds ? 34 : 20) : 22)

    Repeater {   // the time scale
        model: !r.seconds ? 0 : Math.max(0, Math.floor((r.origin + r.span) / r.minor + 1e-6) - r.tick0 + 1)
        delegate: Rectangle {
            required property int index
            readonly property real v: (r.tick0 + index) * r.minor
            readonly property bool big: Math.abs(v / r.major - Math.round(v / r.major)) < 1e-6
            x: Math.round(r.xOf(v)); y: r.height - height
            width: 1; height: big ? 7 : 3; color: big ? Theme.lineHover : Theme.line
            Text { visible: parent.big && parent.x >= 0 && parent.x + 4 + implicitWidth <= r.width
                   x: 4; y: -r.height + r.labelTop + (r.upper.length ? 13 : 0) + parent.height
                   text: r.label(parent.v); color: Theme.fg3; font.family: uiFont; font.pixelSize: Theme.label
                   font.features: { "tnum": 1 } }
        }
    }
    Repeater {   // the upper line (bars): the app's marks, brighter, with a tall tick
        model: r.upper
        delegate: Rectangle {
            required property var modelData
            x: Math.round(r.xOfSec(modelData.at)); y: r.labelTop; width: 1; height: r.height - y; color: Theme.line
            visible: x >= 0 && x + 4 + up.implicitWidth <= r.width
            Text { id: up; x: 4; y: -1; text: modelData.text; color: Theme.fg2; font.family: uiFont
                   font.pixelSize: Theme.label; font.features: { "tnum": 1 } }
        }
    }
    Rectangle {  // the range band, and the range on it
        visible: r.rangeBand; width: parent.width; height: r.bandH; color: Theme.sunken
        readonly property var shown: area.ranging ? [Math.min(area.a, area.b), Math.max(area.a, area.b)]
                                     : r.range ? [r.range.start, r.range.end] : null
        Rectangle { visible: !!parent.shown; color: Theme.accentSoft; border.color: Theme.accent; height: parent.height
                    x: parent.shown ? Math.max(0, r.xOfSec(parent.shown[0])) : 0
                    width: parent.shown ? Math.max(1, Math.min(r.width, r.xOfSec(parent.shown[1])) - x) : 0 }
        HoverHandler { id: bandHover }
        HoverTip { text: "Time range"; help: "Drag here to set it; double-click to clear it."; hovered: bandHover.hovered
                   pressed: area.pressed }
    }
    MouseArea {  // the band makes a range, the scale scrubs; under the flags, so a flag takes its own presses
        id: area
        anchors.fill: parent
        preventStealing: true
        hoverEnabled: true
        cursorShape: r.rangeBand && mouseY < r.bandH ? Qt.IBeamCursor : Qt.PointingHandCursor
        property bool ranging: false
        property real a: 0
        property real b: 0
        onPressed: (m) => {
            ranging = r.rangeBand && m.y < r.bandH
            if (ranging) { a = r.secOf(m.x); b = a } else r.scrubbed(r.tOf(m.x))
        }
        onPositionChanged: (m) => { if (!pressed) return; if (ranging) b = r.secOf(m.x); else r.scrubbed(r.tOf(m.x)) }
        onReleased: { if (ranging && Math.abs(r.xOfSec(b) - r.xOfSec(a)) >= 2) r.rangeSet(Math.min(a, b), Math.max(a, b))
                      ranging = false }
        onDoubleClicked: (m) => { if (r.rangeBand && m.y < r.bandH && r.range) r.rangeCleared() }
        onWheel: (w) => { w.accepted = !!r.view && r.view.wheel(w.angleDelta.x, w.angleDelta.y,
                                                                (w.modifiers & Qt.ControlModifier) !== 0,
                                                                (w.modifiers & Qt.ShiftModifier) !== 0, w.x / r.width, false) }
    }
    Repeater { model: r.markers; delegate: MarkerFlag { ruler: r } }
    Rectangle {  // the playhead: a line through the ruler, its head at the top
        x: Math.round(r.xOf(r.value)); width: 1; height: r.height; color: Theme.accent
        visible: x >= 0 && x <= r.width
        Rectangle { x: -4; y: 0; width: 9; height: 8; radius: 2; color: Theme.accent }
    }
    ActionMenu {
        id: mm
        property Item flag: null
        property var marker: null
        property real sec: 0
        onPicked: (v) => {
            const shared = marker.shared !== false
            const d = r.markerSource.choose(marker.id, v, sec, shared)
            if (d === "rename" && flag) flag.startRename()
            else if (d === "share") r.markerShareToggled(marker.id, !shared)
        }
    }
    MarkerNamer { id: namer; y: r.height + 2; canShare: r.canShare
                  onAccepted: (name, shared) => r.markerAdded(name, shared, r.frames ? r.value / r.fps : r.value) }
}
