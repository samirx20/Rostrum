import QtQuick
import RostrumKit

// The settings panel while nothing is selected: the song (DESIGN.md decision 4, W1) — its name, tempo, beats per
// bar, length and key (the rest of the song's own settings behind More), then the changes at the playhead (tempo, key,
// section). It is the one home of these (the header's tempo selects the song). The rows are the kit's InspectorRow on `songPanel` (song_panel.py: the `doc.set` fields), so
// they look and behave like every other setting; each change is one undo step.
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
            Item {   // the key at the start of the song: tonic and mode (a key change later is made on the ruler)
                width: parent.width; height: Theme.row
                Text { width: Theme.labelColumn; anchors.verticalCenter: parent.verticalCenter; text: "Key"; color: Theme.fg2
                       font.family: uiFont; font.pixelSize: Theme.body }
                Row {
                    x: Theme.labelColumn; anchors.verticalCenter: parent.verticalCenter; spacing: Theme.grid
                    readonly property real w: (list.width - Theme.labelColumn - Theme.grid) / 2
                    ChoiceField { width: songPanel.key.set ? parent.w : 2 * parent.w + Theme.grid
                                  options: (songPanel.key.set ? [] : [{ value: "", label: songPanel.noKey }]).concat(
                                      ["C", "C#", "Db", "D", "Eb", "E", "F", "F#", "G", "Ab", "A", "Bb", "B"])
                                  current: songPanel.key.tonic; onPicked: (v) => { if (v !== "") songPanel.setKey(v, songPanel.key.mode) } }
                    ChoiceField { visible: songPanel.key.set; width: parent.w; options: ["major", "minor", "dorian", "phrygian", "lydian", "mixolydian", "locrian"]
                                                     .map(m => ({ value: m, label: m.charAt(0).toUpperCase() + m.slice(1) }))
                                  current: songPanel.key.mode; onPicked: (v) => songPanel.setKey(songPanel.key.tonic, v) }
                }
            }
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
                Button { visible: backend.time > 0.01; text: "Tempo change"; onClicked: backend.songDo("add_tempo", "") }
                Button { visible: parent.st.hasKey && !parent.st.keyAtPlayhead; text: "Key change"
                         onClicked: backend.songDo("add_key", parent.st.tonic + " " + parent.st.mode) }
                Button { text: "Section"; onClicked: backend.songDo("add_section", "") }
            }
        }
    }
}
