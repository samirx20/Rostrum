import QtQuick
import RostrumKit

// A timeline row's time side (LayerRows.qml), under the ruler (x = ruler.x - 8). A layer row draws a slim bar from its
// first key to its last (vertically centred, no text; no keys, no bar); a selected layer's row is tinted, its bar in
// the accent (Sam, H49: no box around the whole row). Drag the bar to move the layer in time: backend.beginBarDrag /
// barDragTo / endDrag (one gesture = one change; near a marker or the playhead it snaps). When it shows (Starts at /
// Ends at) is set in the panel; an end tied to a marker is a small flag at that time.
// Keys sit on it as diamonds (all the layer's keys); a drawing's frames lie on it (FrameMarks). Setting, effect and
// mask rows show their keys only. Click a diamond: the key is selected (the inspector shows its ease); drag it: key.set
// t (it lands on a marker within 6 px). Between two keys of one setting a stretch can be clicked (StretchBand.qml). A click anywhere else on the row selects its layer, a drag there draws a box
// that picks every key it touches (on several rows); between two keys a tiny shape shows the ease. The ruler scrubs.
// Past the last key, Repeat and Back and forth show faint copies of the keys; a spring cut short by its next key, a
// faint tail to where it would have settled (screen2d/key_ghosts.py, from the evaluator's own functions).
Rectangle {
    id: track
    property var rowData
    property Item ruler
    readonly property bool isLayer: rowData.row === "layer"
    readonly property bool lit: rowData.owner === backend.selected || backend.multi.ids.indexOf(rowData.owner) >= 0   // every selected layer's bar
    function xOf(t) { return 8 + Math.round(ruler.xOf(t)) }
    function onBar(k) { return k.t >= (rowData.start || 0) - 1e-6 && k.t <= (rowData.end || 0) + 1e-6 }   // a key in the layer's time
    function tAt(item, x) { return ruler.tOf(item.mapToItem(track, x, 0).x - 8) }
    readonly property var barKeys: isLayer && rowData.bar === true ? rowData.keys.filter(k => onBar(k)) : []
    radius: Theme.radiusCtl
    color: lit && isLayer ? Qt.tint(Theme.sunken, Qt.rgba(Theme.accent.r, Theme.accent.g, Theme.accent.b, 0.07))
         : isLayer ? Theme.sunken : Qt.darker(Theme.panel, 1.15)

    property Item rows                  // the LayerRows it lies in: a box dragged here picks keys on every row it touches
    // Right-click anywhere on the row (its empty part, its bar, a stretch, a key): the one short menu (actions.SHORT_MENU)
    function openMenu(item, x, y) { const p = item.mapToItem(rows, x, y); rows.openMenu(rowData.owner, p.x, p.y) }
    MouseArea {   // the row's empty part: a click selects its layer, a drag draws a box that picks keys
        anchors.fill: parent
        acceptedButtons: Qt.LeftButton | Qt.RightButton
        property point from
        property bool boxing: false
        onPressed: (m) => {
            boxing = false
            if (m.button === Qt.RightButton) { from = Qt.point(-1e6, -1e6); track.openMenu(this, m.x, m.y); return }
            from = Qt.point(m.x, m.y)
        }
        onPositionChanged: (m) => {
            if (from.x < -1e5) return                     // a right press: the menu, no box
            if (!boxing && Math.abs(m.x - from.x) + Math.abs(m.y - from.y) < 5) return
            if (!boxing) { boxing = true; track.rows.boxStart(mapToItem(track.rows.contentItem, from.x, from.y)) }
            track.rows.boxTo(mapToItem(track.rows.contentItem, m.x, m.y))
        }
        onReleased: (m) => {
            if (m.button === Qt.RightButton) return
            if (boxing) track.rows.boxEnd(m.modifiers & Qt.ControlModifier ? "ctrl" : m.modifiers & Qt.ShiftModifier ? "shift" : "")
            else { backend.keys.clear(); backend.select(track.rowData.owner) }   // a click on the row lets picked keys go
            boxing = false
        }
        onCanceled: { if (boxing) track.rows.boxEnd("cancel"); boxing = false }
    }
    Repeater {   // the ease between two keys, a tiny shape on the row: a line (linear), a curve (eased), a step (jump);
                 // a layer's lines draw theirs as clickable stretches instead (StretchBand.qml)
        model: !track.rowData.stretches && track.rowData.keys.length > 1 ? track.rowData.keys.slice(0, -1) : []
        delegate: Canvas {
            required property var modelData
            required property int index
            readonly property real x0: track.xOf(modelData.t)
            readonly property real x1: track.xOf(track.rowData.keys[index + 1].t)
            visible: x1 - x0 > 26
            width: 12; height: 8; x: (x0 + x1) / 2 - width / 2; y: (track.height - height) / 2; z: 1
            opacity: 0.7
            property string shape: modelData.ease || "curve"
            onShapeChanged: requestPaint()
            onPaint: {
                const ctx = getContext("2d")
                ctx.reset(); ctx.strokeStyle = Theme.fg3; ctx.lineWidth = 1.2; ctx.beginPath()
                if (shape === "line") { ctx.moveTo(0, height); ctx.lineTo(width, 0) }
                else if (shape === "step") { ctx.moveTo(0, height); ctx.lineTo(width, height); ctx.moveTo(width, height); ctx.lineTo(width, 0) }
                else { ctx.moveTo(0, height); ctx.bezierCurveTo(width * 0.9, height, width * 0.1, 0, width, 0) }
                ctx.stroke()
            }
        }
    }

    Rectangle {  // the bar: first key to last key, centred in the row
        id: bar
        visible: track.barKeys.length > 0
        opacity: track.rowData.hidden ? 0.35 : 1       // a hidden layer dims
        readonly property real pad: 6                  // half a diamond: the end keys sit inside it
        x: track.barKeys.length ? track.xOf(track.barKeys[0].t) - pad : 0
        width: track.barKeys.length ? track.xOf(track.barKeys[track.barKeys.length - 1].t) + pad - x : 0
        height: 12; y: Math.round((parent.height - height) / 2); radius: height / 2
        color: track.lit ? Qt.rgba(Theme.accent.r, Theme.accent.g, Theme.accent.b, 0.30) : Theme.raised
        MouseArea {
            id: barArea
            anchors.fill: parent; hoverEnabled: true; preventStealing: true
            acceptedButtons: Qt.LeftButton | Qt.RightButton
            cursorShape: held ? Qt.ClosedHandCursor : Qt.OpenHandCursor
            property string held: ""
            onPressed: (m) => {          // a selected bar moves every selected bar (drags.py); else it is selected alone
                if (m.button === Qt.RightButton) { track.openMenu(barArea, m.x, m.y); return }
                if (!backend.multi.has(track.rowData.id)) backend.select(track.rowData.id)
                held = backend.beginBarDrag(track.rowData.id, "move", track.tAt(barArea, m.x)) === false ? "" : "move"
            }
            onPositionChanged: (m) => {
                if (!held) return
                backend.barDragTo(track.tAt(barArea, m.x), (m.modifiers & Qt.ControlModifier) ? 0 : 6 / track.ruler.perSec)
            }
            onReleased: { if (held) backend.endDrag(); held = "" }
            onCanceled: { if (held) backend.endDrag(); held = "" }
        }
        Repeater {   // the stretches of the animations on the layer's first line, under its keys (SPEC §9.2)
            model: bar.visible ? track.rowData.stretches || [] : []
            delegate: StretchBand { row: track; shift: bar.x; room: bar.width }
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
            visible: track.rowData.bar === true && modelData.name !== ""
            x: track.xOf(modelData.at === "start" ? track.rowData.start || 0 : track.rowData.end || 0) - (modelData.at === "start" ? 0 : width); y: 1
            width: 7; height: 7; radius: 1; color: Theme.warn
            HoverHandler { id: flagHover }
            HoverTip { hovered: flagHover.hovered; text: (modelData.at === "start" ? "Starts at marker " : "Ends at marker ") + modelData.name }
        }
    }
    Repeater {   // a spring still moving at its next key: a faint tail to where it would have settled (key_ghosts.py)
        model: track.rowData.tails || []
        delegate: Rectangle {
            required property var modelData
            x: track.xOf(modelData.t0); width: Math.max(2, track.xOf(modelData.t1) - x)
            y: track.height / 2 - 1.5; height: 3; radius: 1.5; z: 1
            color: Theme.fg3; opacity: tailHover.hovered ? 0.7 : 0.35
            HoverHandler { id: tailHover }
            HoverTip { hovered: tailHover.hovered; text: "The spring is still moving here: at the key it jumps. Move the key this much later for it to settle." }
        }
    }
    Repeater {   // Repeat / Back and forth: faint copies of the keys after the last one, as playback plays them (key_ghosts.py)
        model: track.rowData.ghosts || []
        delegate: Rectangle {
            required property var modelData
            width: 7; height: 7; rotation: 45; z: 1
            x: track.xOf(modelData) - width / 2; y: (track.height - height) / 2
            color: "transparent"; border.width: 1; border.color: Theme.fg2; opacity: 0.45
        }
    }
    Repeater {   // a line's stretches (or a barless layer's), under its keys
        model: bar.visible ? [] : track.rowData.stretches || []
        delegate: StretchBand { row: track }
    }
    Repeater {   // the keys of a row with no bar (a setting, an effect, a mask)
        model: bar.visible ? track.rowData.keys.filter(k => !track.onBar(k)) : track.rowData.keys
        delegate: KeyDot { row: track }
    }
}
