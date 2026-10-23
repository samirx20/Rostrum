import QtQuick
import RostrumKit

// The timeline, bottom, full width, always there; it is also the layers list (apps/2d/DESIGN.md › The layer rows).
// One header row: play and the time over the names, the ruler over the rows (it scrubs; the project's marker flags sit
// on it), Keys | Curves and the height switch at its right end. Under it one row per layer: its name
// on the left (LayerName.qml), its bar, keys and frames on the right (LayerTrack.qml). Curves shows the selected
// layer's value curves in the same place. The thin strip above the top edge drags to make the timeline taller.
// Compact (DESIGN.md › two heights): only the selected layer's row; its name opens a list of every layer, so another
// is one click away. The button at the ruler row's right end switches; Main.qml remembers it per tool.
Rectangle {
    id: tl
    property int labelWidth: 240
    signal resized(real height)                 // the top edge dragged to this height (Main.qml clamps it)
    property bool compact: false
    property bool canCompact: true              // false beside a tall frame (one height there): the switch is absent
    signal compactAsked(bool on)
    readonly property real compactHeight: rowsTop + Theme.rowDense + 2 * Theme.gap
                                          + (backend.soundtrack.present ? Theme.row + 2 : 0)   // the Sound row stays
    readonly property real wantedHeight: rowsTop + rows.contentHeight + 2 * Theme.gap   // header, ruler and every row: Main.qml's default height, up to its cap
    function openMenu(id, px, py) { rows.openMenu(id, px, py) }
    color: Theme.panel; radius: Theme.radiusPanel

    MouseArea {  // the top edge: in the gap above the timeline, so it never takes a click meant for the canvas
        id: edge
        anchors { left: parent.left; right: parent.right; verticalCenter: parent.top }
        height: 2 * Theme.gap          // 16 px: easy to grab; half in the gap above, half on the timeline's own edge
        hoverEnabled: true; preventStealing: true
        cursorShape: Qt.SizeVerCursor
        property real y0: 0
        property real h0: 0
        onPressed: (m) => { y0 = mapToGlobal(m.x, m.y).y; h0 = tl.height }
        onPositionChanged: (m) => { if (pressed) tl.resized(h0 - (mapToGlobal(m.x, m.y).y - y0)) }
        Rectangle { anchors.centerIn: parent; width: 48; height: 3; radius: 1.5
                    color: edge.pressed ? Theme.accent : Theme.fg4; visible: edge.containsMouse || edge.pressed }
    }

    // The header row (SPEC §9.5): over the layer names, play, the time, Add marker (in a project folder) and Keys | Curves;
    // over the rows, the ruler, with the height switch at its right end. One row instead of two: the height is the rows'.
    readonly property real headY: Theme.gap                                   // room for the edge's grab above it
    readonly property real headH: Math.max(30, ruler.height)
    Row {
        id: playCell
        x: Theme.gap; y: tl.headY; height: tl.headH; spacing: Theme.gap
        PlayButton { objectName: "timelinePlay"; anchors.verticalCenter: parent.verticalCenter; implicitHeight: 24; implicitWidth: 24
                     playing: backend.playing; onClicked: backend.togglePlay() }
        TimeReadout { anchors.verticalCenter: parent.verticalCenter }
        AddMarker { anchors.verticalCenter: parent.verticalCenter }
    }
    Segmented {   // Keys: the rows' diamonds; Curves: the value curves inside this same area
        id: keysCurves
        objectName: "keysCurves"
        anchors { right: ruler.left; rightMargin: Theme.pad + 8; verticalCenter: ruler.verticalCenter }   // the names column's right edge
        implicitHeight: 26
        options: [{ value: "keys", label: "Keys" }, { value: "curves", label: "Curves" }]
        current: backend.curves.on ? "curves" : "keys"
        onPicked: (v) => backend.curves.setOn(v === "curves")
    }
    TimeRuler {
        id: ruler
        x: tl.labelWidth + Theme.gap + 8; y: tl.headY   // 8: room for a key at 0
        width: (compactSwitch.visible ? compactSwitch.x - Theme.grid : parent.width - Theme.pad) - 8 - x; height: backend.markers.length > 0 ? 34 : 30   // 34: a row for marker flags
        duration: backend.frameInfo.duration; fps: backend.frameInfo.fps; time: backend.time
    }
    IconButton {  // every row, or only the selected layer's
        id: compactSwitch
        objectName: "timelineHeight"
        visible: tl.canCompact
        anchors { right: parent.right; rightMargin: Theme.gap; verticalCenter: ruler.verticalCenter }
        implicitWidth: 26; implicitHeight: 26; kind: "ghost"
        glyph: tl.compact ? "⌃" : "⌄"
        tip: tl.compact ? "Show every layer" : "Show only the selected layer"
        onClicked: tl.compactAsked(!tl.compact)
    }
    readonly property real rowsTop: ruler.y + ruler.height + Theme.grid
    CurveEditor {
        visible: backend.curves.on
        ruler: ruler; labelWidth: tl.labelWidth
        anchors { left: parent.left; right: parent.right; bottom: parent.bottom; top: parent.top
                  topMargin: tl.rowsTop; rightMargin: Theme.gap; bottomMargin: Theme.gap }   // x as the ruler's
    }
    LayerRows {
        id: rows
        visible: !backend.curves.on
        ruler: ruler; labelWidth: tl.labelWidth; compact: tl.compact
        anchors { left: parent.left; right: parent.right; bottom: parent.bottom; top: parent.top
                  topMargin: tl.rowsTop; rightMargin: Theme.gap; bottomMargin: Theme.gap }   // x as the ruler's
    }
    EdgeFade { flick: rows; visible: rows.visible; x: rows.x; y: rows.y; width: rows.width; height: rows.height; color: Theme.panel }   // a half-shown row fades, never a sliver
    VScrollBar { flick: rows; visible: rows.visible && needed }
    MouseArea {  // compact: the one row's name is a list of every layer
        visible: tl.compact && !backend.curves.on && backend.layers.length > 0
        x: 0; y: tl.rowsTop; width: tl.labelWidth; height: Theme.rowDense; z: 2
        cursorShape: Qt.PointingHandCursor
        onClicked: { picker.entries = backend.layers.filter(r => r.row === "layer")
                         .map(r => ({ value: r.id, label: " ".repeat(r.depth) + r.label })); picker.open() }
        Chevron { anchors { right: parent.right; rightMargin: Theme.gap; verticalCenter: parent.verticalCenter } }
        Menu { id: picker; y: parent.height; width: tl.labelWidth; onPicked: (id) => backend.select(id) }
    }
    EmptyHint {     // the kit's empty state (INTERACTION.md 1.16): gone with the first layer
        visible: backend.layers.length === 0
        x: Theme.pad; y: tl.rowsTop + Theme.gap * 2; width: tl.width - 2 * Theme.pad
        text: "Your layers appear here as bars. Drag a bar to change when it shows."
    }
    BeatLines { ruler: ruler; bottomY: tl.height - Theme.gap }   // Show beats (the Sound row's menu): beat and bar lines
    Repeater {   // the project's shared markers, a faint line across every row (their flags are on the ruler)
        model: backend.markers
        delegate: Rectangle {
            required property var modelData
            x: ruler.x + Math.round(ruler.xOf(modelData.at)); y: ruler.y + ruler.height
            width: 1; height: tl.height - y - Theme.gap; color: Theme.warn; opacity: 0.35
        }
    }
    Menu {   // a key's right-click: the same Ease list as the key panel (backend.keyBar)
        id: easeMenu
        width: 140
        entries: backend.keyBar.eases
        onPicked: (v) => backend.keyBar.setEase(v)
    }
    Connections {
        target: backend.keyBar
        function onMenuAsked(gx, gy) {
            const p = tl.mapFromItem(null, gx, gy)
            easeMenu.x = Math.min(p.x, tl.width - easeMenu.width); easeMenu.y = Math.max(0, p.y - easeMenu.height)
            easeMenu.open()
        }
    }
    Rectangle {  // the playhead line, across every row
        x: ruler.x + Math.round(ruler.xOf(backend.time)); y: ruler.y + ruler.height
        width: 1; height: tl.height - y - Theme.gap; color: Theme.accent; opacity: 0.8
    }
    DragLabel {  // "+6 f · drop" beside the dragged edge or key, on its layer's row (time_snap.py); no row shown: under the ruler
        readonly property real mid: rows.visible && backend.timeSnap.text !== "" ? rows.rowMid(backend.timeSnap.row) : -1
        at: Qt.point(ruler.x + ruler.xOf(backend.timeSnap.t), mid >= 0 ? rows.y + mid : ruler.y + ruler.height + 12)
    }
    SnapLine {   // what a time drag caught (a marker, key, bar end, beat, the playhead), only while snapped (time_snap.py)
        visible: backend.timeSnap.caught
        x: ruler.x + Math.round(ruler.xOf(backend.timeSnap.caughtT)); y: ruler.y + ruler.height
        width: 1; height: tl.height - y - Theme.gap
    }
}
