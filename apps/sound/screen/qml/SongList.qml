import QtQuick
import RostrumKit

// The song's timeline as lists, in the settings panel while nothing is selected (SongSettings.qml): Tempo, Time
// signature, Key, Sections, Markers (a project marker shared with the other apps: the click only moves the
// playhead). The first tempo, time signature and key are edited in the top bar only, never twice: this panel lists only
// the changes after them. Each change is a row ("Bar 5 · drop", its value at the right, on the settings grid's field column):
// click it and the playhead jumps there and it is selected (its settings take the panel; Delete removes it). Under
// each list, its "+" adds one at the playhead, starting at what plays there, and selects it — present only where it
// is valid (song_list.can: not at the start, not where one already is). The rows come from song_list.py.
Column {
    id: sl
    readonly property var lists: { backend.song; return backend.songList() }
    readonly property var st: { backend.time; backend.song; return backend.songEdit() }
    readonly property int fieldX: Theme.labelColumnFor(width)
    readonly property int fieldW: Theme.fieldFor(width)

    component Head: Text {      // a group's heading, as the kit's InspectorRow draws one
        width: sl.width; height: Theme.groupGap + Theme.rowDense; verticalAlignment: Text.AlignBottom
        bottomPadding: Theme.grid + 2; color: Theme.fg3; font.family: uiFont; font.pixelSize: Theme.label
        font.weight: Font.DemiBold
    }
    component Place: Text {
        anchors.verticalCenter: parent.verticalCenter; width: sl.fieldX - Theme.gap; elide: Text.ElideRight
        color: Theme.fg; font.family: uiFont; font.pixelSize: Theme.body; font.features: { "tnum": 1 }
    }
    // Each list's Repeater counts its entries and an entry reads its own (`of`): a new list of as many (a tempo drag
    // re-times every section and marker on each step) keeps every entry, only its texts change
    component Entry: Rectangle {      // one change: click = the playhead there + selected
        required property int index
        property var of: []              // its list
        readonly property var modelData: of[index] || ({})
        property bool picker: false      // its value is a field (a time signature), not words
        width: sl.width; height: Theme.rowDense; radius: Theme.radiusCtl
        color: modelData.id === backend.selected ? Theme.accentSoft : hover.containsMouse ? Theme.hover : "transparent"
        Place { x: Theme.grid; text: parent.modelData.place }
        Text { visible: !parent.picker; x: sl.fieldX; width: sl.fieldW; anchors.verticalCenter: parent.verticalCenter
               horizontalAlignment: Text.AlignRight; text: parent.modelData.value; elide: Text.ElideRight
               color: Theme.fg2; font.family: uiFont; font.pixelSize: Theme.body; font.features: { "tnum": 1 } }
        MouseArea { id: hover; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                    onClicked: { backend.setTime(parent.modelData.t); if (parent.modelData.pick) backend.select(parent.modelData.id) } }
    }
    component Add: Button { kind: "ghost"; flushLeft: true; width: sl.width; height: Theme.rowDense }

    Head { text: "Tempo"; visible: sl.lists.tempo.length > 0 || sl.st.canTempo }
    Repeater { model: sl.lists.tempo.length; delegate: Entry { of: sl.lists.tempo } }
    Add { visible: sl.st.canTempo; text: "+ Tempo change"; onClicked: backend.songDo("add_tempo", "") }

    Head { text: "Time signature"; visible: sl.lists.meter.length > 0 || sl.st.canMeter }
    Repeater {      // a change's value is its picker: 3/4 -> 6/8 in one step, the way the header sets it
        model: sl.lists.meter.length
        delegate: Entry {
            id: me
            of: sl.lists.meter
            picker: true
            ChoiceField {
                x: sl.fieldX; width: sl.fieldW; height: parent.height - 4; anchors.verticalCenter: parent.verticalCenter
                current: me.modelData.value
                options: songPanel.meters.map(m => ({ value: m, label: m }))
                onPicked: (v) => { backend.select(me.modelData.id); songPanel.setMeter(v, me.modelData.id) }
            }
        }
    }
    Add { visible: sl.st.canMeter; text: "+ Time signature change"; onClicked: backend.songDo("add_meter", "") }

    Head { text: "Key"; visible: sl.lists.key.length > 0 || (sl.st.hasKey && !sl.st.keyAtPlayhead) }
    Repeater { model: sl.lists.key.length; delegate: Entry { of: sl.lists.key } }
    Add { visible: sl.st.hasKey && !sl.st.keyAtPlayhead; text: "+ Key change"
          onClicked: backend.songDo("add_key", sl.st.tonic + " " + sl.st.mode) }

    Head { text: "Sections" }
    Repeater { model: sl.lists.sections.length; delegate: Entry { of: sl.lists.sections } }
    Add { text: "+ Section"; onClicked: backend.songDo("add_section", "") }

    Head { text: "Markers" }
    Repeater { model: sl.lists.markers.length; delegate: Entry { of: sl.lists.markers } }
    Add { visible: sl.st.canMarker; text: "+ Marker"; onClicked: backend.markerHere() }

}
