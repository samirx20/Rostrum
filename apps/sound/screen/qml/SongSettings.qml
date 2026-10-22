import QtQuick
import RostrumKit

// The settings panel while nothing is selected: the song (DESIGN.md decision 4, W1) — its name, length (the rest of
// the song's own settings behind More), then what can be added at the playhead (a tempo change, a key change, a
// section). Tempo, beats per bar and key live in the arrangement header (SongReadout.qml), never here too. The rows
// are the kit's InspectorRow on `songPanel` (song_panel.py: the `doc.set` fields); each change is one undo step.
Panel {
    id: p
    NameLabel { id: name; text: backend.docName; font.pixelSize: Theme.heading
                font.weight: Font.DemiBold; anchors.left: parent.left; anchors.right: parent.right }
    Text { id: kind; text: songPanel.mainMix === "main" ? "Song · Main mix" : "Song"
           color: songPanel.mainMix === "main" ? Theme.accent : Theme.fg3; font.family: uiFont; font.pixelSize: Theme.body
           anchors.top: name.bottom; anchors.topMargin: 2 }
    Flickable {
        anchors { left: parent.left; right: parent.right; top: kind.bottom; bottom: parent.bottom; topMargin: Theme.gap }
        contentHeight: list.height; clip: true; boundsBehavior: Flickable.StopAtBounds
        Column {
            id: list
            width: parent.width
            Item {   // not the main mix yet: the one action for it (absent once it is, the title says so)
                visible: songPanel.mainMix === "other"
                width: parent.width; height: visible ? Theme.row + Theme.grid : 0
                Button { anchors.verticalCenter: parent.verticalCenter; text: "Make this the main mix"
                         onClicked: songPanel.makeMain() }
            }
            Repeater { model: songPanel.rows; delegate: InspectorRow { bridge: songPanel } }
            Row {   // a change in the song's own map, at the playhead: only what is valid there
                readonly property var st: { backend.time; backend.song; return backend.songEdit() }
                topPadding: Theme.gap; spacing: Theme.gap
                Button { visible: backend.time > 0.01; text: "+ Tempo change"; onClicked: backend.songDo("add_tempo", "") }
                Button { visible: parent.st.hasKey && !parent.st.keyAtPlayhead; text: "+ Key change"
                         onClicked: backend.songDo("add_key", parent.st.tonic + " " + parent.st.mode) }
                Button { text: "+ Section"; onClicked: backend.songDo("add_section", "") }
            }
        }
    }
}
