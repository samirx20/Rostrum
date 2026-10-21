import QtQuick
import RostrumKit

// "Render mix and stems": the same versioned render the MCP render_mix makes (a new renders/<item>/vNNN/ folder with the
// mix, a stem per track and per bus, and the manifest), in the background. Shows progress, then where it went.
Column {
    id: x
    readonly property var job: mixer.export
    spacing: Theme.grid
    Button {
        width: parent.width
        text: x.job.busy ? "Rendering…" : "Render mix and stems"
        kind: "primary"; opacity: x.job.busy ? 0.6 : 1
        onClicked: x.job.start()
    }
    Text {
        visible: text !== ""; width: parent.width; wrapMode: Text.WordWrap
        text: x.job.status
        color: text.indexOf("Error") === 0 ? Theme.danger : Theme.fg2
        font.family: uiFont; font.pixelSize: Theme.label
    }
    Text {   // where it went
        visible: x.job.folder !== ""; width: parent.width; wrapMode: Text.WrapAnywhere
        text: x.job.folder; color: Theme.fg3; font.family: uiFont; font.pixelSize: Theme.label
    }
    Button { visible: x.job.folder !== ""; text: "Show folder"; kind: "ghost"; onClicked: x.job.reveal() }
}
