import QtQuick
import RostrumKit

// One key on a timeline row (LayerTrack.qml): a diamond at its time; on a layer's bar it stands for every key of the
// layer at that frame (modelData.ids). Click picks it (the settings panel shows its ease); Ctrl+click adds or removes
// it, Shift+click picks the run between (backend.keys, screen2d/key_select.py). Drag moves it, or every picked key
// together (key.set t, one change; a single key lands on a marker within 6 px). `shift`: the x of what it lies in
// (a layer's bar), so it sits at its time whatever holds it.
Item {
    id: key
    required property var modelData
    property Item row               // the LayerTrack it belongs to (not "track": a delegate's "track: track" would bind to itself)
    property real shift: 0
    property real room: -1             // the bar's width: at the bar's very ends the click area stays inside it
    readonly property real at: row.xOf(modelData.t) - shift - width / 2      // where the diamond is centred, minus half
    readonly property var ids: modelData.ids || [modelData.id]
    readonly property bool on: modelData.id === backend.selected || backend.keys.count > 0 && backend.keys.has(ids)
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
        property string held: ""        // "one" | "many" | ""
        function rowIds() { return key.row.rowData.keys.map(k => k.ids || [k.id]) }
        onPressed: (m) => {
            held = ""
            if (m.modifiers & (Qt.ControlModifier | Qt.ShiftModifier)) {        // add / remove, or the run between
                backend.keys.click(key.ids, (m.modifiers & Qt.ControlModifier) ? "ctrl" : "shift", rowIds())
                return
            }
            if (!backend.keys.has(key.ids)) backend.keys.click(key.ids, "", rowIds())
            if (backend.keys.count > 1) held = backend.keys.beginDrag(key.modelData.id, key.row.tAt(keyArea, m.x)) ? "many" : ""
            else held = backend.beginKeyDrag(key.modelData.id) !== false ? "one" : ""
        }
        onPositionChanged: (m) => {
            if (held === "one") backend.keyDragTo(key.row.tAt(keyArea, m.x), 6 / key.row.ruler.perSec)
            else if (held === "many") backend.keys.dragTo(key.row.tAt(keyArea, m.x))
        }
        function stop() { if (held === "one") backend.endDrag(); else if (held === "many") backend.keys.endDrag(); held = "" }
        onReleased: stop()
        onCanceled: stop()
    }
}
