import QtQuick
import RostrumKit

// One key on a timeline row (LayerTrack.qml): a diamond at its time; on a layer's bar it stands for every key of the
// layer at that frame (modelData.ids). Click picks it (the settings panel's Key block shows its ease; the panel keeps the layer, its keyed setting highlighted); Ctrl+click adds or removes
// it, Shift+click picks the run between (backend.keys, screen2d/key_select.py). Drag moves it, or every picked key
// together (key.set t, one change; within 6 px the grabbed key snaps: screen2d/time_snap.py; Ctrl: free; the "+6 f"
// label beside the key: DragLabel.qml). Alt+drag the first or last picked
// key stretches them all in time (key.scale); right-click gives the Ease list (backend.keyBar). `shift`: the x of what it lies in
// (a layer's bar), so it sits at its time whatever holds it.
Item {
    id: key
    required property var modelData
    property Item row               // the LayerTrack it belongs to (not "track": a delegate's "track: track" would bind to itself)
    property real shift: 0
    property real room: -1             // the bar's width: at the bar's very ends the click area stays inside it
    readonly property real at: row.xOf(modelData.t) - shift - width / 2      // where the diamond is centred, minus half
    readonly property var ids: modelData.ids || [modelData.id]
    readonly property bool on: backend.keys.count > 0 && backend.keys.has(ids)
                               || backend.stretch.shown && ids.some(i => backend.stretch.ids.indexOf(i) >= 0)   // a picked stretch's keys
    x: room < 0 ? at : Math.max(0, Math.min(room - width, at))
    width: 16; height: Math.max(18, parent.height); y: Math.round((parent.height - height) / 2)   // the track's height; in a slim bar, 18
    readonly property int n: modelData.n || 1          // more than one: keys too close to tell apart, shown as one dot
    KeyMark {   // the second diamond peeking out behind: this dot holds several keys
        visible: key.n > 1
        anchors.centerIn: parent; anchors.horizontalCenterOffset: key.at - key.x + 4
        size: key.row.isLayer ? 8 : 7
        color: key.on ? Theme.accent : Theme.fg3; opacity: 0.85
    }
    KeyMark {
        anchors.centerIn: parent; anchors.horizontalCenterOffset: key.at - key.x   // the diamond stays on its time
        size: key.row.isLayer ? 8 : 7
        color: key.on ? Theme.accent : keyArea.containsMouse ? Theme.fg : key.row.isLayer ? Theme.fg2 : Theme.fg3
    }
    MouseArea {
        id: keyArea; anchors.fill: parent; hoverEnabled: true; preventStealing: true
        acceptedButtons: Qt.LeftButton | Qt.RightButton
        cursorShape: Qt.SizeHorCursor
        HoverTip { hovered: keyArea.containsMouse; text: key.n > 1 ? key.n + " keys close together: click to pick them all, zoom in to tell them apart" : "Click to change its ease; drag a box on an empty part of the row to pick several" }
        property string held: ""        // "one" | "many" | ""
        function rowIds() { return key.row.rowData.keys.map(k => k.ids || [k.id]) }
        onPressed: (m) => {
            held = ""
            if (m.button === Qt.RightButton) {                  // the row's short menu (Cut, Copy … act on the picked keys)
                if (!backend.keys.has(key.ids)) backend.keys.click(key.ids, "", rowIds())
                key.row.openMenu(keyArea, m.x, m.y)
                return
            }
            if ((m.modifiers & Qt.AltModifier) && backend.keys.has(key.ids)          // Alt+drag an end: stretch them all
                    && backend.keys.beginStretch(key.modelData.id, key.row.tAt(keyArea, m.x))) {
                held = "many"
                return
            }
            if (m.modifiers & (Qt.ControlModifier | Qt.ShiftModifier)) {        // add / remove, or the run between
                backend.keys.click(key.ids, (m.modifiers & Qt.ControlModifier) ? "ctrl" : "shift", rowIds())
                return
            }
            if (!backend.keys.has(key.ids)) backend.keys.click(key.ids, "", rowIds())
            if (backend.keys.count > 1) held = backend.keys.beginDrag(key.modelData.id, key.row.tAt(keyArea, m.x)) ? "many" : ""
            else held = backend.beginKeyDrag(key.modelData.id) !== false ? "one" : ""
        }
        onPositionChanged: (m) => {
            if (!held) return
            const reach = (m.modifiers & Qt.ControlModifier) ? 0 : 6 / key.row.ruler.perSec      // Ctrl: no snapping
            if (held === "one") backend.keyDragTo(key.row.tAt(keyArea, m.x), reach)
            else backend.keys.dragTo(key.row.tAt(keyArea, m.x), reach)
        }
        function stop() { if (held === "one") backend.endDrag(); else if (held === "many") backend.keys.endDrag(); held = "" }
        onReleased: stop()
        onCanceled: stop()
    }
}
