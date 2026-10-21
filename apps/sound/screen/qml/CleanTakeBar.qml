import QtQuick
import RostrumKit

// Under the inspector of a clip: "Make cleaned take", only while the clip has a cleanup step set and its take is not
// made yet. It runs the same job as the render_cleanup tool, in the background; the status line follows it.
Rectangle {
    id: bar
    readonly property var job: mixer.cleaning
    visible: job.clip !== ""
    implicitHeight: visible ? col.height + 2 * Theme.pad : 0
    color: Theme.panel; radius: Theme.radiusPanel
    Column {
        id: col
        anchors { left: parent.left; right: parent.right; top: parent.top; margins: Theme.pad }
        spacing: Theme.gap
        Text {
            width: parent.width; wrapMode: Text.WordWrap
            text: "This clip has cleanup set, but its cleaned take is not made yet."
            color: Theme.fg2; font.family: uiFont; font.pixelSize: Theme.label
        }
        Button {
            width: parent.width; kind: "primary"; opacity: bar.job.busy ? 0.6 : 1
            text: bar.job.busy ? "Making…" : "Make cleaned take"
            onClicked: bar.job.make()
        }
        Text {
            visible: text !== ""; width: parent.width; wrapMode: Text.WordWrap
            text: bar.job.status; color: text.indexOf("Error") === 0 ? Theme.danger : Theme.fg3
            font.family: uiFont; font.pixelSize: Theme.label
        }
    }
}
