import QtQuick
import RostrumKit

// The settings panel while nothing is selected: the song, titled "Song" (its name is the top bar's tab). Only the
// song's CHANGES are listed (SongList.qml: tempo, time signature and key changes, sections, markers; "+" adds one at
// the playhead); the first tempo, time signature and key are edited in the top bar only. Then the song's own
// settings: its length, a picker or typed ("23 bars", "1:02.5"; song_length.py) (the rest behind More). The Song rows are the kit's InspectorRow on `songPanel`
// (song_panel.py: the `doc.set` fields); each change is one undo step.
Panel {
    id: p
    Text { id: kind; text: "Song"                    // its name is the top bar's tab
           color: Theme.fg; font.family: uiFont
           font.pixelSize: Theme.heading; font.weight: Font.DemiBold }
    Flickable {
        anchors { left: parent.left; right: parent.right; top: kind.bottom; bottom: parent.bottom; topMargin: Theme.gap }
        contentHeight: list.height; clip: true; boundsBehavior: Flickable.StopAtBounds
        Column {
            id: list
            width: parent.width
            ActionsSection { width: parent.width; hub: backend.actions }   // a time range's actions (Make a section …)
            Item {   // not the main mix yet: the one action for it (absent once it is, the title says so)
                visible: songPanel.mainMix === "other"
                width: parent.width; height: visible ? Theme.row + Theme.grid : 0
                Button { anchors.verticalCenter: parent.verticalCenter; text: "Make this the main mix"
                         onClicked: songPanel.makeMain() }
            }
            SongList { width: parent.width }      // ends on the "Song" heading for the rows below
            Item {   // the song's length: one picker (Until the last sound, a number of bars) or typed (Type a length…)
                id: lengthRow
                property bool typing: false         // the picker's place holds a text box until Enter / Esc / leaving it
                property bool held: false           // the box has had the caret since it opened
                width: parent.width; height: Theme.row + Theme.gap
                Text { id: lengthLabel; anchors.verticalCenter: lengthField.verticalCenter; text: "Length"; color: Theme.fg2
                       font.family: uiFont; font.pixelSize: Theme.body }
                ChoiceField { id: lengthField; objectName: "songLength"; visible: !lengthRow.typing
                              anchors { left: parent.left; leftMargin: Theme.labelColumnFor(parent.width); bottom: parent.bottom }
                              width: Theme.fieldFor(parent.width); options: songPanel.lengthChoices
                              current: songPanel.lengthChoice; onPicked: (v) => songPanel.setLength(v)
                              more: "Type a length…"
                              onMoreChosen: { lengthRow.typing = true; lengthType.input.text = ""; caretIn.restart() } }
                Timer { id: caretIn; interval: Theme.fast + 60   // once the list has closed (closing hands the keys back to the picker)
                        onTriggered: lengthType.input.forceActiveFocus() }
                TextField { id: lengthType; objectName: "songLengthTyped"; visible: lengthRow.typing
                            anchors { left: lengthField.left; bottom: parent.bottom }
                            width: lengthField.width
                            placeholder: "23 bars, bar 24, 1:02.5"
                            onEdited: (t) => { if (songPanel.setLength(t)) lengthRow.typing = false }
                            onEscaped: lengthRow.typing = false }
                Connections { target: lengthType.input   // leaving the box (once it had the caret) gives the picker back
                              function onActiveFocusChanged() { if (lengthType.input.activeFocus) lengthRow.held = true
                                                                else if (lengthRow.held) { lengthRow.held = false; lengthRow.typing = false } } }
            }
            Repeater { model: songPanel.rows; delegate: InspectorRow { bridge: songPanel } }
        }
    }
}
