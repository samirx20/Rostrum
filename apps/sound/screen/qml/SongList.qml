import QtQuick
import RostrumKit

// The song's timeline as lists, in the settings panel while nothing is selected (SongSettings.qml): Tempo, Time
// signature, Key, Sections, Markers (a project marker shared with the other apps: the click only moves the
// playhead), then the heading of the song's own rows. Bar 1's tempo and time signature are the song's own fields, edited in place (songPanel);
// every change after them is a row ("Bar 5 · drop", its value at the right, on the settings grid's field column):
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
    component Entry: Rectangle {      // one change: click = the playhead there + selected
        required property var modelData
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
    component Start: Item {           // Bar 1: the song's own value, edited in place
        default property alias field: slot.data
        width: sl.width; height: Theme.row
        Place { x: Theme.grid; text: "Bar 1" }
        Item { id: slot; x: sl.fieldX; width: sl.fieldW; height: parent.height }
    }
    component Add: Button { kind: "ghost"; flushLeft: true; width: sl.width; height: Theme.rowDense }

    Head { text: "Tempo" }
    Start {
        NumberField {
            anchors.fill: parent; anchors.topMargin: 2; anchors.bottomMargin: 2
            value: Math.round(sl.st.startBpm); from: 20; to: 400; step: 1; unit: "bpm"
            onEdited: (v) => songPanel.setValue("tempo", v)
            onScrubStarted: songPanel.beginScrub("tempo")
            onScrubbed: (v) => songPanel.scrub("tempo", v)
            onScrubEnded: songPanel.endScrub()
        }
    }
    Repeater { model: sl.lists.tempo; delegate: Entry { } }
    Add { visible: sl.st.canTempo; text: "+ Tempo change"; onClicked: backend.songDo("add_tempo", "") }

    Head { text: "Time signature" }
    Start {
        ChoiceField {
            anchors.fill: parent; anchors.topMargin: 2; anchors.bottomMargin: 2
            current: backend.song.beatsPerBar + "/" + backend.song.beatUnit
            options: songPanel.meters.map(m => ({ value: m, label: m }))
            onPicked: (v) => songPanel.setMeter(v)
        }
    }
    Repeater {      // a change's value is its picker: 3/4 -> 6/8 in one step, the way the header sets it
        model: sl.lists.meter
        delegate: Entry {
            id: me
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

    Head { text: "Key" }
    Start {       // no key yet: the first one is chosen here (never assumed)
        visible: sl.lists.key.length === 0
        ChoiceField {
            anchors.fill: parent; anchors.topMargin: 2; anchors.bottomMargin: 2
            current: ""; options: [{ value: "", label: songPanel.noKey }].concat(songPanel.tonics)
            onPicked: (v) => { if (v !== "") songPanel.setKey(v, "major") }
        }
    }
    Repeater { model: sl.lists.key; delegate: Entry { } }
    Add { visible: sl.st.hasKey && !sl.st.keyAtPlayhead; text: "+ Key change"
          onClicked: backend.songDo("add_key", sl.st.tonic + " " + sl.st.mode) }

    Head { text: "Sections" }
    Repeater { model: sl.lists.sections; delegate: Entry { } }
    Add { text: "+ Section"; onClicked: backend.songDo("add_section", "") }

    Head { text: "Markers" }
    Repeater { model: sl.lists.markers; delegate: Entry { } }
    Add { visible: sl.st.canMarker; text: "+ Marker"; onClicked: backend.markerHere() }

    Head { text: "Song" }      // the song's own settings follow (SongSettings.qml: length, More)
}
