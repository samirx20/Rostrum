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
    readonly property var kit: box.kit || ({ knobs: [], turn: false, anchor: false })   // which knobs and turn zones (handle_kinds.dressed)
    readonly property real tiny: 32       // screen px: under this a side's knobs sit outside the box
    readonly property real tinyOut: 7     // how far outside (half a knob and its hit margin, less the body's edge)
    readonly property real bw: (box.w || 0) * fit
    readonly property real bh: (box.h || 0) * fit
    x: (box.x || 0) * fit; y: (box.y || 0) * fit; width: bw; height: bh
    transform: Rotation { origin.x: (h.box.ax || 0) * h.bw; origin.y: (h.box.ay || 0) * h.bh; angle: h.box.rot || 0 }

    HaloLine { anchors.fill: parent; anchors.margins: -1 }
    // the turn zones sit under the knobs
    Repeater {
        model: [[-1, -1], [1, -1], [1, 1], [-1, 1]]        // always made, shown while editable and the kit turns: a pick remakes nothing
        delegate: Item {
            id: zone
            required property var modelData
            visible: h.editable && h.kit.turn === true
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
    Loader {            // a picked shape's orange setting handles (corner radius, points, arc ends ...), under the knobs: a corner wins
        id: shapeKnobs
        anchors.fill: parent
        active: h.editable && !h.group && h.box.type === "shape"
        sourceComponent: ShapeHandles { box: h.box; fit: h.fit }
    }
    KeptRepeater {      // the kit's knobs, kept: a pick (or the frame, and back) remakes none
        id: knobs
        needed: h.editable ? h.kit.knobs.length : 0
        delegate: Rectangle {
            id: knob
            required property int index
            readonly property var info: h.kit.knobs[index] || ({})
            readonly property int hx: info.hx || 0
            readonly property int hy: info.hy || 0
            readonly property bool edge: hx === 0 || hy === 0
            objectName: (h.group ? "groupHandle:" : "handle:") + (info.name || "")   // what a scripted hand drags (dragobj)
            visible: index < knobs.needed && (!edge || info.always === true || (hx === 0 ? h.bw : h.bh) > 36)   // a small box keeps only its corners
                     && !(edge && shapeKnobs.item && shapeKnobs.item.covers.indexOf(info.name) >= 0)   // a setting handle sits there
            width: 9; height: 9; color: "white"; border.width: 1; border.color: Theme.accent
            Rectangle { anchors.fill: parent; anchors.margins: -1; color: "transparent"; border.width: 1; border.color: Qt.rgba(0, 0, 0, 0.6) }   // the halo
            // A small box on screen (under `tiny` px a side): its knobs sit just OUTSIDE it on that side, so the knobs never cover the
            // body and a drag or Alt+drag from the middle of a 15 px dot moves / copies it (Figma). One rule, the one place knobs are placed and hit.
            readonly property bool outX: h.bw < h.tiny && hx !== 0
            readonly property bool outY: h.bh < h.tiny && hy !== 0
            x: (hx + 1) / 2 * h.bw - width / 2 + (outX ? hx * h.tinyOut : 0)
            y: (hy + 1) / 2 * h.bh - height / 2 + (outY ? hy * h.tinyOut : 0)
            MouseArea {
                anchors.fill: parent; anchors.margins: -4
                cursorShape: ({"hor": Qt.SizeHorCursor, "ver": Qt.SizeVerCursor, "fdiag": Qt.SizeFDiagCursor,
                               "bdiag": Qt.SizeBDiagCursor})[(h.box.cursors || [])[knob.index] || "hor"]
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
    // the anchor: a ring round the point the layer turns and scales about, only while the settings panel's Anchor group is open
    // (anchor_slots.py: the layer stays where it shows, one drag = one undo step). Over the knobs: one sitting on a knob would be unreachable under it.
    Rectangle {
        id: anchorRing
        objectName: "anchorPoint"
        visible: h.editable && !h.group && h.kit.anchor === true && backend.anchorOpen
        width: 19; height: 19; radius: 10; color: "transparent"; border.width: 2; border.color: Theme.accent
        x: (h.box.ax || 0) * h.bw - width / 2; y: (h.box.ay || 0) * h.bh - height / 2
        Rectangle { anchors.centerIn: parent; width: 3; height: 3; radius: 2; color: Theme.accent }
        MouseArea {
            anchors.fill: parent
            cursorShape: pressed ? Qt.ClosedHandCursor : Qt.OpenHandCursor
            preventStealing: true
            property bool on: false
            property point p0
            function at(m) { var q = mapToItem(h.space, m.x, m.y); return Qt.point(q.x / h.fit, q.y / h.fit) }
            onPressed: (m) => { on = backend.beginAnchor(); p0 = at(m) }
            onPositionChanged: (m) => { if (on) { var q = at(m); backend.anchorBy(q.x - p0.x, q.y - p0.y, (m.modifiers & Qt.ControlModifier) !== 0) } }
            onReleased: { if (on) backend.endDrag(); on = false }
            onCanceled: { if (on) backend.endDrag(); on = false }
        }
    }
    // the fill's gradient handles, over the box while the Fill row's picker is open on a gradient (one drag = one change)
    // (made only while shown: kept, its ~60 bindings ran on every change of the box)
    Loader {
        anchors.fill: parent
        active: h.editable && !h.group && PaintSession.gradient
        onActiveChanged: if (!active) PaintSession.hold = false
        sourceComponent: GradientHandles {
            anchors.fill: parent
            paint: PaintSession.paint || ({})
            selected: PaintSession.selected
            points: h.box.type !== "text"            // a text's letters take no point-to-point span
            onBegan: backend.beginScrub("paint")
            onEdited: (p) => backend.scrub("paint", p)
            onEnded: backend.endScrub()
            HoverHandler { onHoveredChanged: PaintSession.hold = hovered }   // a press here keeps the picker open
        }
    }
}
