import QtQuick
import RostrumKit

// "Render mix and stems": the same versioned render the MCP render_mix makes (a new renders/<item>/vNNN/ folder with the
// mix, a stem per track and per bus named after the track, and the manifest), in the background. What to save as
// (format, sample rate, trim the silent end) comes from the same choices render_mix offers. The result area has a fixed
// height, so a finished render never moves the loudness curve above it.
Column {
    id: x
    readonly property var job: mixer.export
    spacing: Theme.grid
    ChoiceField {
        width: parent.width
        options: x.job.formats; current: x.job.format
        onPicked: (v) => x.job.setFormat(v)
    }
    ChoiceField {
        width: parent.width
        options: x.job.rates; current: x.job.rate
        onPicked: (v) => x.job.setRate(v)
    }
    Row {
        spacing: Theme.gap
        Toggle { checked: x.job.trim; onToggled: (v) => x.job.setTrim(v); anchors.verticalCenter: parent.verticalCenter }
        Text { text: "Trim silence at the end"; color: Theme.fg2; font.family: uiFont; font.pixelSize: Theme.body
               anchors.verticalCenter: parent.verticalCenter }
    }
    Button {
        width: parent.width
        text: x.job.busy ? "Rendering…" : "Render mix and stems"
        kind: "primary"; opacity: x.job.busy ? 0.6 : 1
        onClicked: x.job.start()
    }
    Item {   // the result: always this tall (what it says, then where it went and the button), so nothing moves
        width: parent.width; height: 56
        Text {
            id: status
            width: parent.width; height: 32; wrapMode: Text.WordWrap; elide: Text.ElideRight; maximumLineCount: 2
            text: x.job.status
            color: text.indexOf("Error") === 0 ? Theme.danger : Theme.fg2
            font.family: uiFont; font.pixelSize: Theme.label
        }
        Button {
            id: show
            anchors { left: parent.left; bottom: parent.bottom }
            visible: x.job.folder !== ""; text: "Show folder"; onClicked: x.job.reveal()
        }
        Text {
            anchors { left: show.right; leftMargin: Theme.gap; right: parent.right; verticalCenter: show.verticalCenter }
            visible: show.visible; elide: Text.ElideMiddle
            text: x.job.folder; color: Theme.fg3; font.family: uiFont; font.pixelSize: Theme.label
        }
    }
}
