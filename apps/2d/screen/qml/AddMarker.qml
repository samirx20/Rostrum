import QtQuick
import RostrumKit

// "Add marker": a shared project marker at the playhead (on its frame). Only in a project folder (markers belong to
// the project); the new flag can be dragged, renamed (double-click) or deleted (×) on the ruler.
Button {
    visible: backend.markerEdit.available
    text: "Add marker"; kind: "ghost"; implicitHeight: 24
    onClicked: backend.markerEdit.add(Math.round(backend.time * backend.frameInfo.fps) / backend.frameInfo.fps)
}
