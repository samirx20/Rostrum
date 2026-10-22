import QtQuick
import QtQuick.Dialogs
import RostrumKit

// "My sounds" in the Sounds panel: the person's own sound folders (library_panel.py, `soundLibrary`), searched by the
// panel's words (`query`) and narrowed by kind and shape. With no folder yet it offers only "Add a folder of my
// sounds"; the choices and results appear once there is something to search. Each result plays on its own through the engine (click it, or ▶; ■ Stop in the Library ends it) and
// goes on the selected track at the playhead (double-click or Place: one operation, one undo step). With one clip
// selected each result also has Swap (double-click swaps): clip.swap keeps the clip's time, length, level and fades.
Item {
    id: lib
    property string query: ""
    signal used()
    onQueryChanged: soundLibrary.setText(query)
    function addFolder() { picker.open() }

    FolderDialog { id: picker; title: "Choose a folder of your sounds"
                   onAccepted: soundLibrary.addFolder(selectedFolder.toString()) }

    Column {   // no folder yet: the one thing you can do
        visible: !soundLibrary.hasFolders && soundLibrary.busy === ""
        width: parent.width; spacing: Theme.gap; topPadding: Theme.pad
        Text { width: parent.width; wrapMode: Text.WordWrap
               text: "Use sound effects you own: a Sonniss bundle, BOOM, your recordings. Nothing is copied."
               color: Theme.fg3; font.family: uiFont; font.pixelSize: Theme.body }
        Button { kind: "primary"; text: "Add a folder…"; onClicked: picker.open() }
        Text { visible: soundLibrary.status !== ""; width: parent.width; wrapMode: Text.WordWrap; text: soundLibrary.status
               color: Theme.danger; font.family: uiFont; font.pixelSize: Theme.body }
    }
    Text {   // reading a folder (the first time only)
        visible: soundLibrary.busy !== ""
        width: parent.width; wrapMode: Text.WordWrap; topPadding: Theme.pad
        text: "Reading " + soundLibrary.busy + "…\nThe first time takes a while; after that it opens at once."
        color: Theme.fg3; font.family: uiFont; font.pixelSize: Theme.body
    }
    Column {
        id: body
        visible: soundLibrary.hasFolders && soundLibrary.busy === ""
        anchors.fill: parent; spacing: Theme.gap
        ChoiceField { width: parent.width; options: soundLibrary.kindChoices; current: soundLibrary.kind
                      onPicked: (v) => soundLibrary.setFilter("kind", v) }
        Segmented { options: soundLibrary.lengthChoices; current: soundLibrary.length
                    onPicked: (v) => soundLibrary.setFilter("length", v) }
        Segmented { options: soundLibrary.brightnessChoices; current: soundLibrary.brightness
                    onPicked: (v) => soundLibrary.setFilter("brightness", v) }
        Text { width: parent.width; wrapMode: Text.WordWrap; text: soundLibrary.status
               color: soundLibrary.status.startsWith("Error") ? Theme.danger : Theme.fg3
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
                TapHandler { onTapped: soundLibrary.audition(row.index); onDoubleTapped: { soundLibrary.swapTarget ? soundLibrary.swap(row.index) : soundLibrary.place(row.index); lib.used() } }
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
                    anchors.right: parent.right; anchors.rightMargin: Theme.grid; anchors.verticalCenter: parent.verticalCenter
                    spacing: 2
                    IconButton { glyph: "▶"; kind: "ghost"; tip: "Hear it"; onClicked: soundLibrary.audition(row.index) }
                    Button { text: "Place"; onClicked: { soundLibrary.place(row.index); lib.used() } }
                    Button { visible: soundLibrary.swapTarget !== ""; kind: "primary"; text: "Swap"
                             onClicked: { soundLibrary.swap(row.index); lib.used() } }
                }
            }
        }
    }
}
