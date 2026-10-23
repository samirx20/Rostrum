import QtQuick
import RostrumKit

// In the inspector of a clip with a clean-up, under its rows (the Cleanup group is last) (DESIGN.md §3.10): "Make cleaned take" while its take is not made yet,
// Cancel while a clean-up runs (it stops the job and keeps nothing; the clip plays its original), and once the take is
// made the line that says what the clean-up did ("Background noise −18 dB · voice level unchanged"), measured once.
// Each part shows only when it can be used. The job is the same as the render_cleanup tool; the status line follows it.
Rectangle {
    id: bar
    readonly property var job: mixer.cleaning
    visible: job.shown
    implicitHeight: visible ? col.height + Theme.gap : 0
    color: "transparent"
    Keys.onEscapePressed: (e) => { if (job.cancellable) job.cancel(); else e.accepted = false }
    Column {
        id: col
        anchors { left: parent.left; right: parent.right; top: parent.top; topMargin: Theme.gap }
        spacing: Theme.gap
        Text {
            visible: bar.job.clip !== ""
            width: parent.width; wrapMode: Text.WordWrap
            text: "This clip has cleanup set, but its cleaned take is not made yet."
            color: Theme.fg2; font.family: uiFont; font.pixelSize: Theme.label
        }
        Text {
            visible: bar.job.info.line !== undefined && bar.job.info.line !== ""
            width: parent.width; wrapMode: Text.WordWrap
            text: bar.job.info.line || ""
            color: Theme.fg2; font.family: uiFont; font.pixelSize: Theme.label
        }
        Text {
            visible: bar.job.info.warn !== undefined && bar.job.info.warn !== ""
            width: parent.width; wrapMode: Text.WordWrap
            text: bar.job.info.warn || ""
            color: Theme.warn; font.family: uiFont; font.pixelSize: Theme.label
        }
        ModelDownload { width: parent.width; fetch: bar.job.download }
        Button {
            visible: bar.job.clip !== "" && !bar.job.busy && (bar.job.download.state === "idle" || bar.job.download.state === "done")
            width: parent.width; kind: "primary"
            text: "Make cleaned take"
            onClicked: bar.job.make()
        }
        Button {
            visible: bar.job.cancellable
            width: parent.width; kind: "ghost"
            text: "Cancel"
            onClicked: bar.job.cancel()
        }
        Text {
            visible: text !== ""; width: parent.width; wrapMode: Text.WordWrap
            text: bar.job.status; color: text.indexOf("Error") === 0 ? Theme.danger : Theme.fg3
            font.family: uiFont; font.pixelSize: Theme.label
        }
    }
}
