import QtQuick
import RostrumKit

// The kit's Ruler in seconds, with the project's shared markers as flags; press or drag sets the time (screen state)
// (an app adds what else a scrub does: 2D plays a short burst of the sound there, Main.qml).
// In a project folder the flags edit: drag = move, double-click = rename, × = delete (one marker operation each).
// frameTicks: a tick per frame (2D: a frame-by-frame layer selected).
Ruler {
    property alias time: r.value
    property bool frameTicks: false     // one tick per frame (2D: a frame-by-frame layer selected)
    id: r
    objectName: "timeRuler"
    unit: "seconds"
    markers: backend.markers
    editMarkers: backend.markerEdit.available
    onScrubbed: (t) => backend.setTime(t)       // an app adds its own (2D: a burst of the sound, Main.qml)
    onMarkerMoved: (id, at) => backend.markerEdit.move(id, at)
    onMarkerRenamed: (id, name) => backend.markerEdit.rename(id, name)
    onMarkerRemoved: (id) => backend.markerEdit.remove(id)

    Repeater {   // frameTicks: one small tick per frame (while frames are at least 4 px apart)
        readonly property real fps: backend.frameInfo.fps || 30
        readonly property bool on: r.frameTicks && r.perSec / fps >= 4
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
