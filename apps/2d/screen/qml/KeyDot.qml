import QtQuick
import RostrumKit

// One key on a timeline row (LayerTrack.qml): a diamond at its time. Click selects it (the settings panel shows its
// ease); drag moves it (key.set t, one change; it lands on a marker within 6 px). `shift`: the x of what it lies in
// (a layer's bar), so it sits at its time whatever holds it.
Item {
    id: key
    required property var modelData
    property Item row               // the LayerTrack it belongs to (not "track": a delegate's "track: track" would bind to itself)
    property real shift: 0
    property real room: -1             // the bar's width: at the bar's very ends the click area stays inside it
    readonly property real at: row.xOf(modelData.t) - shift - width / 2      // where the diamond is centred, minus half
    readonly property bool on: modelData.id === backend.selected
    x: room < 0 ? at : Math.max(0, Math.min(room - width, at))
    width: 16; height: parent.height        // the track's height, or the bar's when it lies in a bar
    KeyMark {
        anchors.centerIn: parent; anchors.horizontalCenterOffset: key.at - key.x   // the diamond stays on its time
        size: key.row.isLayer ? 8 : 7
        color: key.on ? Theme.accent : keyArea.containsMouse ? Theme.fg : key.row.isLayer ? Theme.fg2 : Theme.fg3
    }
    MouseArea {
        id: keyArea; anchors.fill: parent; hoverEnabled: true; preventStealing: true
        cursorShape: Qt.SizeHorCursor
        property bool held: false
        onPressed: held = backend.beginKeyDrag(key.modelData.id) !== false
        onPositionChanged: (m) => { if (held) backend.keyDragTo(key.row.tAt(keyArea, m.x), 6 / key.row.ruler.perSec) }
        onReleased: { if (held) backend.endDrag(); held = false }
        onCanceled: { if (held) backend.endDrag(); held = false }
    }
}
