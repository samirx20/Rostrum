import QtQuick
import RostrumKit

// Add marker: a shared project marker at the playhead (on its frame), in the timeline's play cell. Only in a project
// folder (markers belong to the project); the new flag can be dragged, renamed (double-click) or deleted (×) on the ruler.
// With `askOn` (a TimeRuler) the name is asked first, under the playhead (as M does): Enter adds it, Esc adds nothing.
IconButton {
    property Item askOn: null           // a TimeRuler: the name is asked there first
    visible: backend.markerEdit.available
    glyph: "⚑"; kind: "ghost"; implicitWidth: 24; implicitHeight: 24
    tip: "Add marker"; help: "A named moment at the playhead that other apps can follow"
    objectName: "addMarker"
    onClicked: askOn ? askOn.newMarker()
                     : backend.markerEdit.add(Math.round(backend.time * backend.frameInfo.fps) / backend.frameInfo.fps)
}
