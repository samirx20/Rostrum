import QtQuick
import RostrumKit

// One selected layer's outline on the canvas, turned with the layer (about its anchor). With `editable` it also has
// 4 corner + 4 edge resize knobs and a turn zone just outside each corner (screen2d/handle_slots.py: one gesture =
// one undo step each; Shift = same proportion / 15° steps, Alt = from the centre). `box` is a bounds.boxes entry in
// composition px; `fit` is canvas px per composition px; `space` is the (unturned) item the pointer is read in.
Item {
    id: h
    property var box: ({})
    property real fit: 1
    property Item space
    property bool editable: false
    readonly property real bw: (box.w || 0) * fit
    readonly property real bh: (box.h || 0) * fit
    x: (box.x || 0) * fit; y: (box.y || 0) * fit; width: bw; height: bh
    transform: Rotation { origin.x: (h.box.ax || 0) * h.bw; origin.y: (h.box.ay || 0) * h.bh; angle: h.box.rot || 0 }

    Rectangle {
        anchors.fill: parent; anchors.margins: -1
        color: "transparent"; border.width: 1; border.color: Theme.accent
    }
    // the turn zones sit under the knobs
    Repeater {
        model: h.editable ? [[-1, -1], [1, -1], [1, 1], [-1, 1]] : []
        delegate: Item {
            id: zone
            required property var modelData
            width: 28; height: 28
            x: (modelData[0] + 1) / 2 * h.bw + modelData[0] * 11 - 14
            y: (modelData[1] + 1) / 2 * h.bh + modelData[1] * 11 - 14
            MouseArea {
                anchors.fill: parent
                cursorShape: pressed ? Qt.ClosedHandCursor : Qt.OpenHandCursor
                preventStealing: true
                property bool on: false
                function at(m) { var q = mapToItem(h.space, m.x, m.y); return Qt.point(q.x / h.fit, q.y / h.fit) }
                onPressed: (m) => { on = backend.beginRotate(); if (on) { var q = at(m); backend.rotateTo(q.x, q.y, false) } }
                onPositionChanged: (m) => { if (on) { var q = at(m); backend.rotateTo(q.x, q.y, (m.modifiers & Qt.ShiftModifier) !== 0) } }
                onReleased: { if (on) backend.endDrag(); on = false }
                onCanceled: { if (on) backend.endDrag(); on = false }
            }
        }
    }
    Repeater {
        model: h.editable ? [[-1, -1], [1, -1], [1, 1], [-1, 1], [0, -1], [1, 0], [0, 1], [-1, 0]] : []
        delegate: Rectangle {
            id: knob
            required property var modelData
            readonly property int hx: modelData[0]
            readonly property int hy: modelData[1]
            readonly property bool edge: hx === 0 || hy === 0
            visible: !edge || (hx === 0 ? h.bw : h.bh) > 36          // a small box keeps only its corners
            width: 9; height: 9; color: "white"; border.width: 1; border.color: Theme.accent
            x: (hx + 1) / 2 * h.bw - width / 2; y: (hy + 1) / 2 * h.bh - height / 2
            MouseArea {
                anchors.fill: parent; anchors.margins: -4
                cursorShape: ({"hor": Qt.SizeHorCursor, "ver": Qt.SizeVerCursor, "fdiag": Qt.SizeFDiagCursor,
                               "bdiag": Qt.SizeBDiagCursor})[backend.resizeCursor(knob.hx, knob.hy, h.box.rot || 0)]
                preventStealing: true
                property bool on: false
                property point p0
                function at(m) { var q = mapToItem(h.space, m.x, m.y); return Qt.point(q.x / h.fit, q.y / h.fit) }
                onPressed: (m) => { on = backend.beginResize(knob.hx, knob.hy); p0 = at(m) }
                onPositionChanged: (m) => {
                    if (!on) return
                    var q = at(m)
                    backend.resizeBy(q.x - p0.x, q.y - p0.y, (m.modifiers & Qt.ShiftModifier) !== 0, (m.modifiers & Qt.AltModifier) !== 0)
                }
                onReleased: { if (on) backend.endDrag(); on = false }
                onCanceled: { if (on) backend.endDrag(); on = false }
            }
        }
    }
}
