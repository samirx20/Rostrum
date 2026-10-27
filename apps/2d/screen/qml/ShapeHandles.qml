import QtQuick
import RostrumKit

// A picked shape's setting handles, over its box inside Handles.qml (turned with it): orange-ringed dots and diamonds,
// so they never look like the white resize squares. Rectangle: a dot inside each corner (drag along the diagonal = every
// corner's radius; Alt = this corner only). Star: points (sideways), inner radius (in / out), roundness. Polygon: sides,
// roundness. Triangle: tip (along the top edge), roundness. Arc: start and end (round the middle, Shift = 15°), hole.
// Ellipse: the arc's dots at the top (one drag makes it an arc). Spiral: turns (round the middle). Which, where and
// when they hide by size: screen2d/shape_handle_slots.py + shape_handle_geom.py; each drag = one undo step, the same
// value.set an agent calls. 9 px drawn, 15 px hit (CANVAS §3 rule 2). While one is dragged the others fade out and a
// chip by the pointer says the value. `covers`: the edge squares a handle sits on (Handles.qml hides them).
Item {
    id: s
    property var box: ({})
    property real fit: 1
    readonly property color ring: "#f59e0b"           // the one orange for shape settings (stand-in until the kit's Theme has it)
    // re-asked on every box, zoom or picture change (selBox: each previewed step of a drag is a new picture)
    readonly property var info: { backend.selBox; return backend.shapeHandles(box, fit) }
    readonly property var list: info.handles || []
    readonly property var covers: info.covers || []
    property point chipAt: Qt.point(0, 0)
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
                cursorShape: Qt.CrossCursor               // stand-in: the kit's `radius` / `shape-setting` pointers when they land
                preventStealing: true
                property bool on: false
                function at(m) { var q = mapToItem(s, m.x, m.y); s.chipAt = q; return Qt.point(q.x / Math.max(s.width, 1e-6), q.y / Math.max(s.height, 1e-6)) }
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
    Rectangle {     // the value while dragging ("Radius 24"), 16 px below-right of the pointer, upright however the box turns
        objectName: "shapeHandleChip"
        visible: s.held !== "" && (s.info.chip || "") !== ""
        x: s.chipAt.x + 16; y: s.chipAt.y + 16
        transformOrigin: Item.TopLeft; rotation: -(s.box.rot || 0)
        width: chipWords.implicitWidth + 2 * Theme.grid + 4; height: chipWords.implicitHeight + Theme.grid
        radius: Theme.radiusCtl
        color: Theme.raised; border.color: Theme.popupEdge
        Text {
            id: chipWords
            anchors.centerIn: parent
            text: s.info.chip || ""
            color: Theme.fg; font.family: uiFont; font.pixelSize: Theme.body; font.features: { "tnum": 1 }
        }
    }
}
