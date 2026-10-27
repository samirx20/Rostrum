import QtQuick
import RostrumKit

// The kit's Ruler in seconds, with the project's shared markers as flags; press or drag sets the time (screen state)
// (an app adds what else a scrub does: 2D plays a short burst of the sound there, Main.qml).
// In a project folder the flags edit: drag = move, double-click = rename, × = delete (one marker operation each).
// frameTicks: a tick per frame (2D: a frame-by-frame layer selected).
// newMarker() (Add marker, an app's M key) asks the name under the playhead; Enter adds it on the playhead's frame
// (one marker operation). `addsMarkers: false` for an app that adds them itself from markerAdded.
Ruler {
    property alias time: r.value
    property bool frameTicks: false     // one tick per frame (2D: a frame-by-frame layer selected)
    property bool addsMarkers: true     // the name box's Enter adds the marker (markerAdded): one marker operation
    property var cuts: []               // times the frame cuts at (2D): a short orange tick through the ruler, on the Frame row's cut keys
    id: r
    objectName: "timeRuler"
    unit: "seconds"
    markers: backend.markers
    editMarkers: backend.markerEdit.available
    markerSource: backend.markerEdit              // right-click a flag: its menu (Rename, Move to playhead, Colour, Delete)
    onScrubbed: (t) => backend.setTime(t)       // an app adds its own (2D: a burst of the sound, Main.qml)
    onMarkerMoved: (id, at) => backend.markerEdit.move(id, at)
    onMarkerRenamed: (id, name) => backend.markerEdit.rename(id, name)
    onMarkerRemoved: (id) => backend.markerEdit.remove(id)
    nextMarkerName: backend.markerEdit.available ? backend.markerEdit.freeName : "Marker 1"
    onMarkerAdded: (name, shared, at) => {
        const fps = backend.frameInfo.fps || 30
        if (addsMarkers) backend.markerEdit.addNamed(name, Math.round(at * fps) / fps)
    }

    Repeater {   // the frame's cuts: a vertical tick at each, the whole ruler's height
        model: r.cuts
        delegate: Rectangle {
            required property var modelData
            x: Math.round(r.xOf(modelData)) - 1; y: 2; width: 2; height: r.height - 4; radius: 1
            color: Theme.warn
        }
    }
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
