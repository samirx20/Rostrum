import QtQuick
import QtQuick.Dialogs
import RostrumKit

// The Library panel: your own sound folders, searched by kind and shape. With no folder yet it offers only
// "Add a sound folder"; search, shape choices and results appear once there is something to search. Each result
// plays on its own (Play) and goes on the selected track at the playhead (Place: one operation, one undo).
Panel {
    id: lib
    title: "Library"
    headerRight: Button { visible: soundLibrary.hasFolders && soundLibrary.busy === ""; kind: "ghost"
                          text: "Add folder"; onClicked: picker.open() }

    FolderDialog { id: picker; title: "Choose a folder of sound effects"
                   onAccepted: soundLibrary.addFolder(selectedFolder.toString()) }

    // No folder yet: the one thing you can do.
    Column {
        visible: !soundLibrary.hasFolders && soundLibrary.busy === ""
        anchors.centerIn: parent; spacing: Theme.gap; width: Math.min(parent.width, 320)
        Text { width: parent.width; horizontalAlignment: Text.AlignHCenter; wrapMode: Text.WordWrap
               text: "Use sound effects you own: a Sonniss bundle, BOOM, your recordings. Nothing is copied."
               color: Theme.fg3; font.family: uiFont; font.pixelSize: Theme.body }
        Button { anchors.horizontalCenter: parent.horizontalCenter; kind: "primary"; text: "Add a sound folder"
                 onClicked: picker.open() }
        Text { visible: soundLibrary.status !== ""; width: parent.width; horizontalAlignment: Text.AlignHCenter
               wrapMode: Text.WordWrap; text: soundLibrary.status; color: Theme.danger
               font.family: uiFont; font.pixelSize: Theme.body }
    }

    // Reading a folder (the first time only).
    Text {
        visible: soundLibrary.busy !== ""
        anchors.centerIn: parent; width: Math.min(parent.width, 360); wrapMode: Text.WordWrap
        horizontalAlignment: Text.AlignHCenter
        text: "Reading " + soundLibrary.busy + "…\nThe first time takes a while; after that it opens at once."
        color: Theme.fg3; font.family: uiFont; font.pixelSize: Theme.body
    }

    // Search and results.
    Column {
        id: body
        visible: soundLibrary.hasFolders && soundLibrary.busy === ""
        anchors.fill: parent; spacing: Theme.gap
        Row {
            width: parent.width; spacing: Theme.gap
            TextField { width: parent.width - kindPick.width - Theme.gap; placeholder: "Search words (metal, cloth…)"
                        value: soundLibrary.text; onEdited: (t) => soundLibrary.setText(t) }
            ChoiceField { id: kindPick; width: 120; options: soundLibrary.kindChoices; current: soundLibrary.kind
                          onPicked: (v) => soundLibrary.setFilter("kind", v) }
        }
        Flow {
            width: parent.width; spacing: Theme.gap
            Segmented { options: soundLibrary.lengthChoices; current: soundLibrary.length
                        onPicked: (v) => soundLibrary.setFilter("length", v) }
            Segmented { options: soundLibrary.brightnessChoices; current: soundLibrary.brightness
                        onPicked: (v) => soundLibrary.setFilter("brightness", v) }
        }
        Text { text: soundLibrary.status; color: soundLibrary.status.startsWith("Error") ? Theme.danger : Theme.fg3
               font.family: uiFont; font.pixelSize: Theme.label }
        ListView {
            id: list
            width: parent.width; height: body.height - y; clip: true; spacing: 2
            boundsBehavior: Flickable.StopAtBounds
            model: soundLibrary.results
            delegate: Rectangle {
                id: row
                required property var modelData
                required property int index
                width: list.width; height: Theme.rowDense * 2
                radius: Theme.radiusCtl
                color: hover.hovered ? Theme.hover : Theme.raised
                HoverHandler { id: hover }
                Column {
                    anchors.left: parent.left; anchors.leftMargin: Theme.gap; anchors.right: buttons.left
                    anchors.rightMargin: Theme.gap; anchors.verticalCenter: parent.verticalCenter; spacing: 2
                    Text { width: parent.width; text: row.modelData.name; elide: Text.ElideMiddle; color: Theme.fg
                           font.family: uiFont; font.pixelSize: Theme.body }
                    Text { width: parent.width; elide: Text.ElideRight; color: Theme.fg3
                           text: row.modelData.what + (row.modelData.inFile ? " · " + row.modelData.inFile : "")
                           font.family: uiFont; font.pixelSize: Theme.label }
                }
                Row {
                    id: buttons
                    anchors.right: parent.right; anchors.rightMargin: Theme.gap; anchors.verticalCenter: parent.verticalCenter
                    spacing: Theme.grid
                    Button { kind: "ghost"; text: "Play"; onClicked: soundLibrary.audition(row.index) }
                    Button { text: "Place"; onClicked: soundLibrary.place(row.index) }
                }
            }
        }
    }
}
