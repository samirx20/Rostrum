import QtQuick
import RostrumKit

// The named markers above the ruler, each a small tag at its time. Click selects the marker; drag moves it
// (marker.set at, one gesture = one undo step; snapped to a quarter beat, Shift = free). The project's shared
// markers show with a dashed edge; dragging one moves only its tag while the mouse is down, and the release is one
// marker.move in the project's marker list (backend.moveSharedMarker), so it moves for every app.
// The clicks are taken here in one place, so a drag keeps going while the tags are redrawn.
Item {
    id: band
    property var ruler
    clip: true
    property string sharedId: ""    // the project marker being dragged (its tag follows the mouse until release)
    property real sharedDx: 0
    function tagWidth(name) { return metrics.advanceWidth(name) + 14 }
    function markerAt(x) {
        var best = null
        for (var i = 0; i < backend.markers.length; i++) {
            var m = backend.markers[i], mx = ruler.xOf(m.t)
            if (!m.named && x >= mx - 4 && x <= mx + tagWidth(m.name)) best = m
        }
        return best
    }
    FontMetrics { id: metrics; font.family: uiFont; font.pixelSize: Theme.label }

    Repeater {
        model: backend.markers
        delegate: Rectangle {
            required property var modelData
            readonly property bool on: modelData.id === backend.selected
            x: Math.round(band.ruler.xOf(modelData.t) + (modelData.id === band.sharedId ? band.sharedDx : 0)); y: 1
            visible: !modelData.named && x + width > 0 && x < band.width
            width: tag.implicitWidth + 12; height: band.height - 2
            radius: 3; color: on ? Theme.accent : Theme.raised
            Rectangle { width: 2; height: parent.height; color: parent.on ? Theme.fg : Theme.fg3; radius: 1
                        visible: !modelData.shared }
            Column { visible: modelData.shared; spacing: 2; Repeater { model: Math.ceil(band.height / 4)
                     Rectangle { width: 2; height: 2; color: Theme.accent } } }
            Text { id: tag; x: 7; anchors.verticalCenter: parent.verticalCenter; text: modelData.name
                   color: parent.on ? Theme.fg : Theme.fg2; font.family: uiFont; font.pixelSize: Theme.label }
        }
    }
    MouseArea {
        anchors.fill: parent
        preventStealing: true
        property real x0: 0
        property bool dragging: false
        cursorShape: band.markerAt(mouseX) !== null ? Qt.SizeHorCursor : Qt.ArrowCursor
        hoverEnabled: true
        onPressed: (m) => {
            var hit = band.markerAt(m.x)
            x0 = m.x
            if (hit !== null && hit.shared) { band.sharedId = hit.id; band.sharedDx = 0; dragging = true; return }
            dragging = hit !== null && backend.beginDrag(hit.id)
            if (!dragging) m.accepted = false
        }
        onPositionChanged: (m) => {
            if (!(dragging && pressed)) return
            if (band.sharedId !== "") band.sharedDx = m.x - x0
            else backend.dragBy((m.x - x0) / band.ruler.perSec, 0, (m.modifiers & Qt.ShiftModifier) !== 0)
        }
        onWheel: (w) => backend.viewWheel(w.angleDelta.x, w.angleDelta.y, (w.modifiers & Qt.ControlModifier) !== 0,
                                          (w.modifiers & Qt.ShiftModifier) !== 0, w.x / band.width, false)
        onReleased: (m) => {
            if (band.sharedId !== "")
                backend.moveSharedMarker(band.sharedId, band.sharedDx / band.ruler.perSec, (m.modifiers & Qt.ShiftModifier) !== 0)
            else if (dragging) backend.endDrag()
            band.sharedId = ""; band.sharedDx = 0; dragging = false
        }
        onCanceled: { if (dragging && band.sharedId === "") backend.cancelDrag(); band.sharedId = ""; band.sharedDx = 0; dragging = false }
    }
}
