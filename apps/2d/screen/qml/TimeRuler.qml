import QtQuick
import RostrumKit

// The kit's Ruler in seconds, with the project's shared markers as flags; press or drag sets the time (screen state).
// In a project folder the flags edit: drag = move, double-click = rename, × = delete (one marker operation each).
Ruler {
    property alias time: r.value
    id: r
    unit: "seconds"
    markers: backend.markers
    editMarkers: backend.markerEdit.available
    onScrubbed: (t) => backend.setTime(t)
    onMarkerMoved: (id, at) => backend.markerEdit.move(id, at)
    onMarkerRenamed: (id, name) => backend.markerEdit.rename(id, name)
    onMarkerRemoved: (id) => backend.markerEdit.remove(id)
}
