import QtQuick
import RostrumKit

// One selected layer's outline (or, with `group`, the one box round several, whose handles act on all of them) on the canvas, turned with the layer (about its anchor). With `editable` it also has
// 4 corner + 4 edge resize knobs and a turn zone just outside each corner (screen2d/handle_slots.py: one gesture =
// one undo step each; Shift = same proportion / 15° steps, Alt = from the centre). `box` is a bounds.boxes entry in
// composition px; `fit` is canvas px per composition px; `space` is the (unturned) item the pointer is read in.
// While the Fill row's picker is open on a gradient, the kit's GradientHandles lie over the box (backend scrub "paint").
Item {
    id: h
    property var box: ({})
    property real fit: 1
    property Item space
    property bool editable: false
    property bool group: false          // the one box round several selected layers: its drags act on all of them (group_slots.py)
    readonly property real bw: (box.w || 0) * fit
    readonly property real bh: (box.h || 0) * fit
    x: (box.x || 0) * fit; y: (box.y || 0) * fit; width: bw; height: bh
    transform: Rotation { origin.x: (h.box.ax || 0) * h.bw; origin.y: (h.box.ay || 0) * h.bh; angle: h.box.rot || 0 }

    HaloLine { anchors.fill: parent; anchors.margins: -1 }
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
                onPressed: (m) => { on = (h.group ? backend.beginGroupRotate() : backend.beginRotate()); if (on) { var q = at(m); h.group ? backend.groupRotateTo(q.x, q.y, false) : backend.rotateTo(q.x, q.y, false) } }
                onPositionChanged: (m) => { if (on) { var q = at(m); var sh = (m.modifiers & Qt.ShiftModifier) !== 0; h.group ? backend.groupRotateTo(q.x, q.y, sh) : backend.rotateTo(q.x, q.y, sh) } }
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
            required property int index
            readonly property int hx: modelData[0]
            readonly property int hy: modelData[1]
            readonly property bool edge: hx === 0 || hy === 0
            objectName: (h.group ? "groupHandle:" : "handle:") + ["nw", "ne", "se", "sw", "n", "e", "s", "w"][index]   // what a scripted hand drags (dragobj)
            visible: !edge || (hx === 0 ? h.bw : h.bh) > 36          // a small box keeps only its corners
            width: 9; height: 9; color: "white"; border.width: 1; border.color: Theme.accent
            Rectangle { anchors.fill: parent; anchors.margins: -1; color: "transparent"; border.width: 1; border.color: Qt.rgba(0, 0, 0, 0.6) }   // the halo
            x: (hx + 1) / 2 * h.bw - width / 2; y: (hy + 1) / 2 * h.bh - height / 2
            MouseArea {
                anchors.fill: parent; anchors.margins: -4
                cursorShape: ({"hor": Qt.SizeHorCursor, "ver": Qt.SizeVerCursor, "fdiag": Qt.SizeFDiagCursor,
                               "bdiag": Qt.SizeBDiagCursor})[backend.resizeCursor(knob.hx, knob.hy, h.box.rot || 0)]
                preventStealing: true
                property bool on: false
                property point p0
                function at(m) { var q = mapToItem(h.space, m.x, m.y); return Qt.point(q.x / h.fit, q.y / h.fit) }
                onPressed: (m) => { on = h.group ? backend.beginGroupResize(knob.hx, knob.hy) : backend.beginResize(knob.hx, knob.hy); p0 = at(m) }
                onPositionChanged: (m) => {
                    if (!on) return
                    var q = at(m)
                    backend.snap.keys((m.modifiers & Qt.ControlModifier) !== 0, false)   // Ctrl: no snapping (snapper.py)
                    var sh = (m.modifiers & Qt.ShiftModifier) !== 0, al = (m.modifiers & Qt.AltModifier) !== 0
                    if (h.group) backend.groupResizeBy(q.x - p0.x, q.y - p0.y, sh, al)
                    else backend.resizeBy(q.x - p0.x, q.y - p0.y, sh, al)
                }
                onReleased: { if (on) backend.endDrag(); on = false }
                onCanceled: { if (on) backend.endDrag(); on = false }
            }
        }
    }
    // the fill's gradient handles, over the box while the Fill row's picker is open on a gradient (one drag = one change)
    GradientHandles {
        anchors.fill: parent
        visible: h.editable && !h.group && PaintSession.gradient
        paint: PaintSession.paint || ({})
        selected: PaintSession.selected
        points: h.box.type !== "text"            // a text's letters take no point-to-point span
        onBegan: backend.beginScrub("paint")
        onEdited: (p) => backend.scrub("paint", p)
        onEnded: backend.endScrub()
        HoverHandler { onHoveredChanged: PaintSession.hold = hovered && parent.visible }   // a press here keeps the picker open
        onVisibleChanged: if (!visible) PaintSession.hold = false
    }
}
