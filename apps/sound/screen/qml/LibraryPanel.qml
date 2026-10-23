import QtQuick
import QtQuick.Dialogs
import RostrumKit

// "My sounds" in the Sounds panel: the person's own sound folders (library_panel.py, `soundLibrary`), searched by the
// panel's words (`query`) and narrowed by kind and shape. With no folder yet it offers only "Add a folder of my
// sounds"; the choices and results appear once there is something to search. Each result plays on its own through the engine (click it, or ▶; ■ Stop in the Library ends it) and
// goes on the selected track at the playhead (double-click or Place: one operation, one undo step). With one clip
// selected each result also has Swap (double-click swaps): clip.swap keeps the clip's time, length, level and fades.
// ↑ / ↓ (in the search box) step through the results in the clip's place with a loop round it; Enter keeps (one undo step),
// Esc puts the original back (swap_trial.py). The step bar appears only while stepping.
Item {
    id: lib
    property string query: ""
    signal used()
    onQueryChanged: soundLibrary.setText(query)
    readonly property bool filterOpen: filterPop.opened
    function addFolder() { picker.open() }
    function openFilter(item) { filterPop.openAt(item) }

    Popover {   // length, tone and kind of sound: one place, not three rows
        id: filterPop
        Column { spacing: Theme.gap
            ChoiceField { width: 220; options: soundLibrary.kindChoices; current: soundLibrary.kind
                          onPicked: (v) => soundLibrary.setFilter("kind", v) }
            Segmented { options: soundLibrary.lengthChoices; current: soundLibrary.length
                        onPicked: (v) => soundLibrary.setFilter("length", v) }
            Segmented { options: soundLibrary.brightnessChoices; current: soundLibrary.brightness
                        onPicked: (v) => soundLibrary.setFilter("brightness", v) } }
    }

    FolderDialog { id: picker; title: "Choose a folder of your sounds"
                   onAccepted: soundLibrary.addFolder(selectedFolder.toString()) }

    Column {   // no folder yet: the one thing you can do
        visible: !soundLibrary.hasFolders && soundLibrary.busy === ""
        width: parent.width; spacing: Theme.gap; topPadding: Theme.pad
        Text { width: parent.width; wrapMode: Text.WordWrap
               text: "Use recordings you own: your own takes, a Sonniss bundle, BOOM. Nothing is copied."
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
        Text { width: parent.width; wrapMode: Text.WordWrap; text: soundLibrary.status
               color: soundLibrary.status.startsWith("Error") ? Theme.danger : Theme.fg3
               font.family: uiFont; font.pixelSize: Theme.label }
        Text { visible: soundLibrary.swapTarget !== "" && !soundLibrary.swapping; width: parent.width; wrapMode: Text.WordWrap
               text: "↑ ↓ try each sound in place of the clip"; color: Theme.fg3; font.family: uiFont; font.pixelSize: Theme.label }
        Item {
            id: stepBar
            visible: soundLibrary.swapping
            width: parent.width; height: visible ? Theme.field : 0
            Text { anchors { left: parent.left; right: keepBtn.left; rightMargin: Theme.gap; verticalCenter: parent.verticalCenter }
                   text: "Trying in place"; elide: Text.ElideRight
                   color: Theme.fg3; font.family: uiFont; font.pixelSize: Theme.label }
            Row { id: keepBtn; anchors { right: parent.right; verticalCenter: parent.verticalCenter } spacing: 2
                  Button { text: "Original"; kind: "ghost"; onClicked: soundLibrary.swapBack()
                           HoverTip { text: "Put the original back (Esc)"; hovered: backHover.hovered }
                           HoverHandler { id: backHover } }
                  Button { text: "Keep"; kind: "primary"; onClicked: { soundLibrary.swapKeep(); lib.used() }
                           HoverTip { text: "Keep this one (Enter)"; hovered: keepHover.hovered }
                           HoverHandler { id: keepHover } } }
        }
        Item {
          width: parent.width; height: body.height - y
          EdgeFade { z: 1; flick: list; anchors.fill: list }
          ListView {
            id: list
            anchors.fill: parent; clip: true; spacing: 2
            currentIndex: soundLibrary.swapRow
            onCurrentIndexChanged: if (soundLibrary.swapping) positionViewAtIndex(currentIndex, ListView.Contain)
            boundsBehavior: Flickable.StopAtBounds
            model: soundLibrary.results
            delegate: Rectangle {
                id: row
                required property var modelData
                required property int index
                width: list.width; height: Theme.rowDense * 2
                radius: Theme.radiusCtl
                color: soundLibrary.swapRow === row.index ? Theme.accentSoft : hover.hovered ? Theme.hover : Theme.raised
                HoverHandler { id: hover }
                TapHandler { onTapped: soundLibrary.audition(row.index); onDoubleTapped: { soundLibrary.swapTarget ? soundLibrary.swap(row.index) : soundLibrary.place(row.index); lib.used() } }
                Column {
                    anchors.left: parent.left; anchors.leftMargin: Theme.gap; anchors.right: buttons.left
                    anchors.rightMargin: Theme.gap; anchors.verticalCenter: parent.verticalCenter; spacing: 2
                    NameLabel { width: parent.width; text: row.modelData.name; elide: Text.ElideMiddle }
                    Text { id: whatText; width: parent.width; elide: Text.ElideRight; color: Theme.fg3
                           text: row.modelData.what + (row.modelData.inFile ? " · " + row.modelData.inFile : "")
                           font.family: uiFont; font.pixelSize: Theme.label
                           HoverTip { text: whatText.truncated ? whatText.text : ""; hovered: hover.hovered } }
                }
                Row {
                    id: buttons
                    anchors.right: parent.right; anchors.rightMargin: Theme.grid; anchors.verticalCenter: parent.verticalCenter
                    spacing: 2
                    IconButton { glyph: "▶"; kind: "ghost"; tip: "Hear it"; onClicked: soundLibrary.audition(row.index) }
                    Button { text: "Place"; onClicked: { soundLibrary.place(row.index); lib.used() } }
                    Button { visible: soundLibrary.swapTarget !== "" && soundLibrary.swapRow !== row.index; kind: "primary"; text: "Swap"
                             onClicked: { soundLibrary.swap(row.index); lib.used() } }
                }
            }
        }
          }
    }
}
