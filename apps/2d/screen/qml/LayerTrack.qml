import QtQuick
import RostrumKit

// A timeline row's time side (LayerRows.qml), under the ruler (x = ruler.x - 8). A layer row draws its bar from when
// it appears to when it goes (composition seconds): the selected layer's in the accent tint. Drag the bar's middle to
// move the layer in time, an end (its outer 6 px) to trim it: backend.beginBarDrag / barDragTo / endDrag (one gesture
// = one change; near a marker or the playhead it snaps, and an end dropped on a marker is tied to it: a small flag).
// Keys sit on it as diamonds (all the layer's keys); a drawing's frames lie on it (FrameMarks). Setting, effect and
// mask rows show their keys only. Click a diamond: the key is selected (the inspector shows its ease); drag it: key.set
// t (it lands on a marker within 6 px). A click anywhere else on the row selects its layer; the ruler scrubs.
Rectangle {
    id: track
    property var rowData
    property Item ruler
    readonly property bool isLayer: rowData.row === "layer"
    readonly property bool lit: rowData.owner === backend.selected || backend.multi.ids.indexOf(rowData.owner) >= 0   // every selected layer's bar
    function xOf(t) { return 8 + Math.round(ruler.xOf(t)) }
    function onBar(k) { return k.t >= (rowData.start || 0) - 1e-6 && k.t <= (rowData.end || 0) + 1e-6 }   // a key in the layer's time
    function tAt(item, x) { return ruler.tOf(item.mapToItem(track, x, 0).x - 8) }
    radius: Theme.radiusCtl
    color: isLayer ? Theme.sunken : Qt.darker(Theme.panel, 1.15)

    MouseArea { anchors.fill: parent; onPressed: backend.select(track.rowData.owner) }   // the row's empty part

    Rectangle {  // the bar
        id: bar
        visible: track.rowData.bar === true
        opacity: track.rowData.hidden ? 0.35 : 1       // a hidden layer dims
        x: track.xOf(track.rowData.start || 0); width: Math.max(4, track.xOf(track.rowData.end || 0) - x)
        y: 3; height: parent.height - 6; radius: 4
        color: track.lit ? Qt.rgba(Theme.accent.r, Theme.accent.g, Theme.accent.b, 0.34) : Theme.raised
        border.width: 1; border.color: track.lit ? Theme.accent : Theme.border
        MouseArea {
            id: barArea
            anchors.fill: parent; hoverEnabled: true; preventStealing: true
            readonly property real grip: Math.min(6, width / 3)
            function part(x) { return x < grip ? "start" : x > width - grip ? "end" : "move" }
            cursorShape: pressed ? (held === "move" ? Qt.ClosedHandCursor : Qt.SizeHorCursor)
                       : part(mouseX) === "move" ? Qt.OpenHandCursor : Qt.SizeHorCursor
            property string held: ""
            onPressed: (m) => {          // a selected bar's middle moves every selected bar (drags.py); else it is selected alone
                const p = part(m.x)
                if (!(p === "move" && backend.multi.has(track.rowData.id))) backend.select(track.rowData.id)
                held = backend.beginBarDrag(track.rowData.id, p, track.tAt(barArea, m.x)) === false ? "" : p
            }
            onPositionChanged: (m) => { if (held) backend.barDragTo(track.tAt(barArea, m.x), 6 / track.ruler.perSec) }
            onReleased: { if (held) backend.endDrag(); held = "" }
            onCanceled: { if (held) backend.endDrag(); held = "" }
        }
        Repeater {   // a layer's keys lie in its bar: pressed on a key, the key moves; anywhere else, the bar
            model: bar.visible ? track.rowData.keys.filter(k => track.onBar(k)) : []
            delegate: KeyDot { row: track; shift: bar.x; room: bar.width }
        }
    }
    FrameMarks { anchors.fill: parent; frames: track.rowData.frames; timeRuler: track.ruler }   // a drawing's frames, on its bar
    Repeater {   // a tied end: a small flag with the marker's name on hover
        model: [{ at: "start", name: track.rowData.startMarker || "" }, { at: "end", name: track.rowData.endMarker || "" }]
        delegate: Rectangle {
            required property var modelData
            visible: bar.visible && modelData.name !== ""
            x: modelData.at === "start" ? bar.x : bar.x + bar.width - width; y: 1
            width: 7; height: 7; radius: 1; color: Theme.warn
            HoverHandler { id: flagHover }
            HoverTip { hovered: flagHover.hovered; text: (modelData.at === "start" ? "Starts at marker " : "Ends at marker ") + modelData.name }
        }
    }
    Repeater {   // the keys of a row with no bar (a setting, an effect, a mask)
        model: bar.visible ? track.rowData.keys.filter(k => !track.onBar(k)) : track.rowData.keys
        delegate: KeyDot { row: track }
    }
}
