import QtQuick
import RostrumKit
import RostrumCursors 1.0

// A picked shape's setting handles, over its box inside Handles.qml (turned with it): orange-ringed dots and diamonds,
// so they never look like the white resize squares. Rectangle: a dot inside each corner (drag along the diagonal = every
// corner's radius; Alt = this corner only). Star: points (sideways), inner radius (in / out), roundness. Polygon: sides,
// roundness. Triangle: tip (along the top edge), roundness. Arc: start and end (round the middle, Shift = 15°), hole.
// Ellipse: the arc's dots at the top (one drag makes it an arc). Spiral: turns (round the middle). Which, where and
// when they hide by size: screen2d/shape_handle_slots.py + shape_handle_geom.py; each drag = one undo step, the same
// value.set an agent calls. 9 px drawn, 15 px hit (CANVAS §3 rule 2). While one is dragged the others fade out and the
// kit's value chip by the pointer says the value (Stage.qml, drag_chip.py). Pointers: `pick` with the corner-arc badge
// on a radius dot, with the diamond badge on every other setting (CURSORS.md). `covers`: the edge squares a handle sits on (Handles.qml hides them).
Item {
    id: s
    property var box: ({})
    property real fit: 1
    readonly property color ring: "#f59e0b"           // the one orange for shape settings (stand-in until the kit's Theme has it)
    // re-asked on every box, zoom or picture change (selBox: each previewed step of a drag is a new picture)
    readonly property var info: { backend.selBox; return backend.shapeHandles(box, fit) }
    readonly property var list: info.handles || []
    readonly property var covers: info.covers || []
    property string held: ""                          // the handle the mouse holds: the others fade (cleared on release, so Esc + let go brings them back)

    KeptRepeater {     // kept: an ellipse turning into an arc mid-drag keeps the dot being dragged (and its press)
        id: dots
        needed: s.list.length
        delegate: Item {
            id: hd
            required property int index
            readonly property var info: s.list[index] || ({})
            objectName: "shapeHandle:" + (info.name || "")      // what a scripted hand drags (dragobj)
            visible: index < dots.needed
            width: 15; height: 15
            x: (info.u || 0) * s.width - width / 2; y: (info.v || 0) * s.height - height / 2
            opacity: s.held === "" || s.held === info.name ? 1 : 0
            Behavior on opacity { NumberAnimation { duration: 120 } }
            Rectangle {     // a dot, or a square turned into a diamond 9 px across
                anchors.centerIn: parent
                width: hd.info.look === "diamond" ? 6.4 : 9; height: width
                radius: hd.info.look === "diamond" ? 0 : width / 2
                rotation: hd.info.look === "diamond" ? 45 : 0
                color: "white"; border.width: 2; border.color: s.ring
                antialiasing: true
            }
            MouseArea {
                anchors.fill: parent
                preventStealing: true
                CanvasCursor { anchors.fill: parent; kind: "pick"; badge: (hd.info.name || "").startsWith("radius") ? "radius" : "shape" }
                property bool on: false
                function at(m) { var q = mapToItem(s, m.x, m.y); return Qt.point(q.x / Math.max(s.width, 1e-6), q.y / Math.max(s.height, 1e-6)) }
                onPressed: (m) => { var q = at(m); on = backend.beginShapeHandle(hd.info.name, q.x, q.y); if (on) s.held = hd.info.name }
                onPositionChanged: (m) => {
                    if (!on) return
                    var q = at(m)
                    backend.shapeHandleTo(q.x, q.y, (m.modifiers & Qt.ShiftModifier) !== 0, (m.modifiers & Qt.AltModifier) !== 0)
                }
                onReleased: { if (on) backend.endDrag(); on = false; s.held = "" }
                onCanceled: { if (on) backend.endDrag(); on = false; s.held = "" }
            }
        }
    }
}
