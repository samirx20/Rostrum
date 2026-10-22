import QtQuick
import RostrumKit

// The timeline, bottom, full width, always there; it is also the layers list (apps/2d/DESIGN.md › The layer rows).
// Header: play, the time, how playing frames are drawn, Add marker, Keys | Curves and, for a selected drawing, its
// frame buttons. Under it the ruler (it scrubs; the project's marker flags sit on it) and one row per layer: its name
// on the left (LayerName.qml), its bar, keys and frames on the right (LayerTrack.qml). Curves shows the selected
// layer's value curves in the same place. The thin strip above the top edge drags to make the timeline taller.
// Compact (DESIGN.md › two heights): only the selected layer's row; its name opens a list of every layer, so another
// is one click away. The button at the header's right end switches; Main.qml remembers it per tool.
Rectangle {
    id: tl
    property int labelWidth: 240
    signal resized(real height)                 // the top edge dragged to this height (Main.qml clamps it)
    property bool compact: false
    signal compactAsked(bool on)
    readonly property real compactHeight: rowsTop + Theme.rowDense + 2 * Theme.gap
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

    Row {  // the header
        id: header
        x: Theme.gap; y: Theme.gap; height: Theme.header; spacing: Theme.pad   // y: room for the edge's grab above it
        PlayButton { anchors.verticalCenter: parent.verticalCenter; implicitHeight: 24; implicitWidth: 24
                     playing: backend.playing; onClicked: backend.togglePlay() }
        TimeReadout { anchors.verticalCenter: parent.verticalCenter; width: 112 }
        PlayOptions { anchors.verticalCenter: parent.verticalCenter }
        AddMarker { anchors.verticalCenter: parent.verticalCenter }
        Segmented {   // Keys: the rows' diamonds; Curves: the value curves inside this same area
            anchors.verticalCenter: parent.verticalCenter; implicitHeight: 26
            options: [{ value: "keys", label: "Keys" }, { value: "curves", label: "Curves" }]
            current: backend.curves.on ? "curves" : "keys"
            onPicked: (v) => backend.curves.setOn(v === "curves")
        }
        FrameTools { anchors.verticalCenter: parent.verticalCenter; visible: painter.drawingId !== "" && !keyBar.visible }   // a frame-by-frame layer, no keys picked
        KeyBar { id: keyBar; anchors.verticalCenter: parent.verticalCenter }   // only while keys are picked
    }
    IconButton {  // every row, or only the selected layer's
        id: compactSwitch
        anchors { right: parent.right; rightMargin: Theme.gap; verticalCenter: header.verticalCenter }
        implicitWidth: 26; implicitHeight: 26; kind: "ghost"
        glyph: tl.compact ? "⌃" : "⌄"
        tip: tl.compact ? "Show every layer" : "Show only the selected layer"
        onClicked: tl.compactAsked(!tl.compact)
    }
    Text {   // how to reach the Ease choice (it shows once a key is selected)
        visible: !tl.compact && !backend.curves.on && !backend.keyBar.shown && backend.layers.some(r => r.keys.length > 0)
                 && x > header.x + header.width + Theme.pad
        anchors { right: compactSwitch.left; rightMargin: Theme.pad; verticalCenter: header.verticalCenter }
        text: "Click a diamond to change its ease, drag a box to pick several"
        color: Theme.fg3; font.family: uiFont; font.pixelSize: Theme.body
    }

    Text {
        x: Theme.pad; anchors.verticalCenter: ruler.bottom; anchors.verticalCenterOffset: -11
        text: "Layers"; color: Theme.fg2; font.family: uiFont; font.pixelSize: Theme.label
        font.weight: Font.DemiBold; font.letterSpacing: Theme.capsSpacing; font.capitalization: Font.AllUppercase
    }
    TimeRuler {
        id: ruler
        x: tl.labelWidth + Theme.gap + 8; y: header.y + header.height   // 8: room for a key at 0
        width: parent.width - x - Theme.pad - 8; height: backend.markers.length > 0 ? 34 : 22   // 34: a row for marker flags
        duration: backend.frameInfo.duration; fps: backend.frameInfo.fps; time: backend.time
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
    Text {
        visible: backend.layers.length === 0
        x: Theme.pad; y: tl.rowsTop + Theme.gap; width: tl.labelWidth - Theme.pad
        text: "Add a shape, text or picture with + Add"
        wrapMode: Text.WordWrap; color: Theme.fg3; font.family: uiFont; font.pixelSize: Theme.body
    }
    Repeater {   // the project's shared markers, a faint line across every row (their flags are on the ruler)
        model: backend.markers
        delegate: Rectangle {
            required property var modelData
            x: ruler.x + Math.round(ruler.xOf(modelData.at)); y: ruler.y + ruler.height
            width: 1; height: tl.height - y - Theme.gap; color: Theme.warn; opacity: 0.35
        }
    }
    Menu {   // a key's right-click: the same Ease list as the key bar (backend.keyBar)
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
}
