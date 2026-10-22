import QtQuick
import RostrumKit

// The kit's Ruler in seconds, with the project's shared markers as flags; press or drag sets the time (screen state)
// and plays a short burst of the project's sound there (backend.soundtrack.scrub).
// In a project folder the flags edit: drag = move, double-click = rename, × = delete (one marker operation each).
// ▾ at its left end: the ruler's view menu, shown only when it has something to offer (Show beats: when the
// project's sound has a tempo; BeatLines.qml draws them).
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

    function openViewMenu() { viewMenu.open() }        // (steps: the ▾ click)
    IconButton {
        id: more
        visible: viewMenu.entries.length > 0
        x: -width - 10; anchors.bottom: parent.bottom; implicitWidth: 22; implicitHeight: 22; kind: "ghost"
        glyph: "▾"; tip: "What the ruler shows"
        onClicked: viewMenu.open()
    }
    Menu {
        id: viewMenu
        parent: more; y: more.height + 2
        width: 160
        entries: backend.soundtrack.hasBeats
                 ? [{ value: "beats", label: backend.soundtrack.showBeats ? "Hide beats" : "Show beats" }] : []
        onPicked: (v) => { if (v === "beats") backend.soundtrack.setShowBeats(!backend.soundtrack.showBeats) }
    }
}
