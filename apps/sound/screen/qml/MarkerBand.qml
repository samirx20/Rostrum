import QtQuick
import RostrumKit

// The named markers above the ruler, each a small tag at its time. Click selects the marker; drag moves it
// (marker.set at, one gesture = one undo step; snapped to a quarter beat, Shift = free).
// The clicks are taken here in one place, so a drag keeps going while the tags are redrawn.
Item {
    id: band
    property var ruler
    clip: true
    function tagWidth(name) { return metrics.advanceWidth(name) + 14 }
    function markerAt(x) {
        var best = ""
        for (var i = 0; i < backend.markers.length; i++) {
            var m = backend.markers[i], mx = ruler.xOf(m.t)
            if (!m.named && x >= mx - 4 && x <= mx + tagWidth(m.name)) best = m.id
        }
        return best
    }
    FontMetrics { id: metrics; font.family: uiFont; font.pixelSize: Theme.label }

    Repeater {
        model: backend.markers
        delegate: Rectangle {
            required property var modelData
            readonly property bool on: modelData.id === backend.selected
            x: Math.round(band.ruler.xOf(modelData.t)); y: 1
            visible: !modelData.named && x + width > 0 && x < band.width
            width: tag.implicitWidth + 12; height: band.height - 2
            radius: 3; color: on ? Theme.accent : Theme.raised
            Rectangle { width: 2; height: parent.height; color: parent.on ? Theme.fg : Theme.fg3; radius: 1 }
            Text { id: tag; x: 7; anchors.verticalCenter: parent.verticalCenter; text: modelData.name
                   color: parent.on ? Theme.fg : Theme.fg2; font.family: uiFont; font.pixelSize: Theme.label }
        }
    }
    MouseArea {
        anchors.fill: parent
        preventStealing: true
        property real x0: 0
        property bool dragging: false
        cursorShape: band.markerAt(mouseX) !== "" ? Qt.SizeHorCursor : Qt.ArrowCursor
        hoverEnabled: true
        onPressed: (m) => {
            var id = band.markerAt(m.x)
            dragging = id !== "" && backend.beginDrag(id)
            x0 = m.x
            if (!dragging) m.accepted = false
        }
        onPositionChanged: (m) => { if (dragging && pressed)
            backend.dragBy((m.x - x0) / band.ruler.perSec, 0, (m.modifiers & Qt.ShiftModifier) !== 0) }
        onWheel: (w) => backend.viewWheel(w.angleDelta.x, w.angleDelta.y, (w.modifiers & Qt.ControlModifier) !== 0,
                                          (w.modifiers & Qt.ShiftModifier) !== 0, w.x / band.width, false)
        onReleased: { if (dragging) backend.endDrag(); dragging = false }
        onCanceled: { if (dragging) backend.cancelDrag(); dragging = false }
    }
}
