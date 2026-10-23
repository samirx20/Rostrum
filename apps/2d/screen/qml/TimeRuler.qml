import QtQuick
import RostrumKit

// The kit's Ruler in seconds, with the project's shared markers as flags; press or drag sets the time (screen state)
// and plays a short burst of the project's sound there (backend.soundtrack.scrub).
// In a project folder the flags edit: drag = move, double-click = rename, × = delete (one marker operation each).
// With a frame-by-frame layer selected, a tick per frame. (Show beats is on the Sound row's menu, SoundRow.qml.)
Ruler {
    property alias time: r.value
    id: r
    objectName: "timeRuler"
    unit: "seconds"
    markers: backend.markers
    editMarkers: backend.markerEdit.available
    onScrubbed: (t) => { backend.setTime(t); backend.soundtrack.scrub(t) }
    onMarkerMoved: (id, at) => backend.markerEdit.move(id, at)
    onMarkerRenamed: (id, name) => backend.markerEdit.rename(id, name)
    onMarkerRemoved: (id) => backend.markerEdit.remove(id)

    Repeater {   // a frame-by-frame layer selected: one small tick per frame (while frames are at least 4 px apart)
        readonly property real fps: backend.frameInfo.fps || 30
        readonly property bool on: painter.drawingId !== "" && r.perSec / fps >= 4
        readonly property int f0: Math.ceil(r.origin * fps - 1e-6)
        id: frameTicks
        model: on ? Math.max(0, Math.floor((r.origin + r.span) * fps + 1e-6) - f0 + 1) : 0
        delegate: Rectangle {
            required property int index
            objectName: "frameTick"
            x: Math.round(r.xOf((frameTicks.f0 + index) / frameTicks.fps)); y: r.height - height
            width: 1; height: 2; color: Theme.line
        }
    }
}
