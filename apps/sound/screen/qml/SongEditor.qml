import QtQuick
import QtQuick.Controls as QQC
import RostrumKit

// The song's music map, edited: opened by clicking the tempo / key in the top bar. Tempo (the song's own, a change at
// the playhead, the selected change's tempo), key (tonic and mode chooser; a key change at the playhead) and sections
// (one at the playhead, the selected one's name). Only what is valid now shows: a delete is there only with that
// thing selected, a key change only once the song has a key. Every control is one document operation (one undo step);
// dragging the flags and section edges on the ruler does the same on the Timeline.
QQC.Popup {
    id: pop
    readonly property var st: { backend.time; backend.selected; backend.song; return backend.songEdit() }
    readonly property string key: st.tonic + " " + st.mode
    width: 292; padding: Theme.pad
    background: Rectangle { color: Theme.raised; radius: Theme.radiusCtl; border.color: Theme.popupEdge }
    component Head: Text { color: Theme.fg3; font.family: uiFont; font.pixelSize: Theme.label; font.weight: Font.DemiBold }
    component Line: Row {
        property string caption: ""
        spacing: Theme.gap; height: Theme.field
        Text { width: 76; text: parent.caption; anchors.verticalCenter: parent.verticalCenter; color: Theme.fg2
               font.family: uiFont; font.pixelSize: Theme.body }
    }

    contentItem: Column {
        spacing: Theme.gap
        Head { text: "Tempo" }
        Line { caption: "Song"
               NumberField { width: 100; value: pop.st.startBpm; from: 20; to: 400; step: 1; unit: "bpm"
                             onEdited: (v) => backend.songDo("start_bpm", String(v)) } }
        Line { visible: pop.st.selected === "tempo"; caption: "This change"
               NumberField { width: 100; value: pop.st.selBpm; from: 20; to: 400; step: 1; unit: "bpm"
                             onEdited: (v) => backend.setValue("bpm", v) } }
        Row { spacing: Theme.gap
              Button { visible: backend.time > 0.01; text: "Tempo change here"; onClicked: backend.songDo("add_tempo", "") }
              Button { visible: pop.st.selected === "tempo"; text: "Delete"; kind: "ghost"; onClicked: backend.removeSelected() } }
        Head { text: "Key" }
        Line { caption: "Key"
               ChoiceField { width: 74; options: ["C", "C#", "Db", "D", "Eb", "E", "F", "F#", "G", "Ab", "A", "Bb", "B"]
                             current: pop.st.tonic; onPicked: (v) => backend.songDo("set_key", v + " " + pop.st.mode) }
               ChoiceField { width: 104; options: ["major", "minor", "dorian", "phrygian", "lydian", "mixolydian", "locrian"]
                             current: pop.st.mode; onPicked: (v) => backend.songDo("set_key", pop.st.tonic + " " + v) } }
        Row { spacing: Theme.gap
              Button { visible: pop.st.hasKey && !pop.st.keyAtPlayhead; text: "Key change here"
                       onClicked: backend.songDo("add_key", pop.key) }
              Button { visible: pop.st.selected === "key"; text: "Delete"; kind: "ghost"; onClicked: backend.removeSelected() } }
        Head { text: "Sections" }
        Line { visible: pop.st.selected === "section"; caption: "Name"
               TextField { width: 150; value: pop.st.selName; onEdited: (v) => backend.setValue("name", v) } }
        Row { spacing: Theme.gap
              Button { text: "Section here"; onClicked: backend.songDo("add_section", "") }
              Button { visible: pop.st.selected === "section"; text: "Delete"; kind: "ghost"; onClicked: backend.removeSelected() } }
        Text { width: parent.width; wrapMode: Text.Wrap; color: Theme.fg4; font.family: uiFont; font.pixelSize: Theme.label
               text: "Drag a flag or a section's edge on the ruler to move it." }
    }
}
