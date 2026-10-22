import QtQuick
import RostrumKit

// Asks before a clean-up model is downloaded (size, licence), then shows its progress with Cancel, then done or the
// error in words. `fetch` is mixer.cleaning.download (model_fetch.py). Absent while nothing is going on.
Column {
    id: panel
    property var fetch
    visible: fetch.state !== "idle"
    spacing: Theme.gap
    Text {
        width: parent.width; wrapMode: Text.WordWrap
        visible: panel.fetch.state === "asking"
        text: panel.fetch.question; color: Theme.fg; font.family: uiFont; font.pixelSize: Theme.body
    }
    Row {
        visible: panel.fetch.state === "asking"; spacing: Theme.gap
        Button { text: "Download"; kind: "primary"; onClicked: panel.fetch.start() }
        Button { text: "Not now"; onClicked: panel.fetch.cancel() }
    }
    Text {
        width: parent.width; wrapMode: Text.WordWrap
        visible: panel.fetch.state === "downloading"
        text: "Downloading " + panel.fetch.note + "…"; color: Theme.fg2; font.family: uiFont; font.pixelSize: Theme.label
    }
    Rectangle {
        visible: panel.fetch.state === "downloading"
        width: parent.width; height: 6; radius: 3; color: Theme.sunken
        Rectangle { width: parent.width * panel.fetch.progress; height: parent.height; radius: 3; color: Theme.accent }
    }
    Button { visible: panel.fetch.state === "downloading"; text: "Cancel"; onClicked: panel.fetch.cancel() }
    Text {
        width: parent.width; wrapMode: Text.WordWrap
        visible: panel.fetch.state === "done"
        text: "Downloaded and checked."; color: Theme.ok; font.family: uiFont; font.pixelSize: Theme.label
    }
    Text {
        width: parent.width; wrapMode: Text.WordWrap
        visible: panel.fetch.state === "failed"
        text: panel.fetch.error; color: Theme.danger; font.family: uiFont; font.pixelSize: Theme.label
    }
    Row {
        visible: panel.fetch.state === "failed"; spacing: Theme.gap
        Button { text: "Try again"; onClicked: panel.fetch.start() }
        Button { text: "Close"; onClicked: panel.fetch.cancel() }
    }
}
