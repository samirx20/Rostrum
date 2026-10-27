import QtQuick
import QtQuick.Shapes
import RostrumKit

// The selected item's gizmo over the viewport (screen3d/gizmo_qt.py has the maths and the edits): move arrows and the
// middle square, turn rings, scale cubes, in the axis colours (X red, Y green, Z blue). The handle under the pointer
// lights (brighter, thicker) and the pointer says what a press does there: a two-headed arrow along a move arrow or
// scale cube (and along a ring where the pointer is: the way a turn drags), four ways on the middle square, a cross
// while D is held (the moves place the pivot). A press on a handle drags it (one undo step; Esc cancels it); a press
// anywhere else falls through to the viewport (orbit, pick). Ctrl while dragging frees the snapping. A click on a handle
// that never drags goes to a bone drawn there (a mesh's arrows cross its bones on the Animate page): the bone is picked.
// Drawn with Shapes, one item per handle, so a drag's move costs only the handles that moved.
Item {
    id: gz
    readonly property var colours: [Theme.danger, "#5fbf6a", Theme.accent]
    readonly property var slots: ["turn0", "turn1", "turn2", "move0", "move1", "move2", "scale0", "scale1", "scale2", "plane"]
    readonly property var byId: {
        var m = {}, hs = gizmo.handles
        for (var i = 0; i < hs.length; i++) m[hs[i].id] = hs[i]
        return m
    }
    property string hot: ""
    property string grabbed: ""
    property point at: Qt.point(0, 0)                 // the pointer
    property int held: Qt.ArrowCursor                 // the pointer a drag keeps until release

    function px(p) { return Qt.point(p[0] * width, p[1] * height) }

    function along(ax, ay, bx, by) {   // the two-headed arrow closest to the screen direction a -> b
        var dx = (bx - ax) * width, dy = (by - ay) * height
        if (Math.abs(dx) + Math.abs(dy) < 4) return Qt.SizeAllCursor     // pointing at the eye: any way
        var deg = (Math.atan2(-dy, dx) * 180 / Math.PI + 180) % 180
        return deg < 22.5 || deg >= 157.5 ? Qt.SizeHorCursor : deg < 67.5 ? Qt.SizeBDiagCursor
             : deg < 112.5 ? Qt.SizeVerCursor : Qt.SizeFDiagCursor
    }

    function cursorFor(id) {
        var h = byId[id]
        if (!h) return gz.parent && gz.parent.pointer !== undefined ? gz.parent.pointer : Qt.ArrowCursor   // off the handles: the viewport's own (orbit, pan, a shape to place)
        if (h.kind === "turn") {        // along the ring where the pointer is
            var best = 1e9, k = 0, x = at.x / width, y = at.y / height
            for (var i = 0; i < h.points.length; i++) {
                var d = Math.abs(h.points[i][0] - x) * width + Math.abs(h.points[i][1] - y) * height
                if (d < best) { best = d; k = i }
            }
            var a = h.points[Math.max(0, k - 1)], b = h.points[Math.min(h.points.length - 1, k + 1)]
            return along(a[0], a[1], b[0], b[1])
        }
        if (h.kind === "move" && gizmo.pivot) return Qt.CrossCursor
        if (id === "plane") return Qt.SizeAllCursor
        return along(h.a[0], h.a[1], h.b[0], h.b[1])
    }

    Repeater {
        model: gz.slots
        delegate: Item {
            id: hd
            required property string modelData
            readonly property var h: gz.byId[modelData]
            readonly property bool lit: modelData === gz.hot || modelData === gz.grabbed
            readonly property color col: !h ? "transparent" : h.axis < 0 ? Theme.fg : gz.colours[h.axis]
            readonly property color ink: lit ? Qt.lighter(col, 1.3) : col
            readonly property bool line: h !== undefined && (h.kind === "turn" || (h.kind === "move" && modelData !== "plane"))
            anchors.fill: parent
            visible: h !== undefined
            z: lit ? 1 : 0

            Shape {          // a ring, or a move arrow's shaft
                anchors.fill: parent
                visible: hd.line
                preferredRendererType: Shape.CurveRenderer
                ShapePath {
                    strokeColor: hd.ink; strokeWidth: hd.lit ? 3.5 : 1.5; fillColor: "transparent"
                    capStyle: ShapePath.RoundCap; joinStyle: ShapePath.RoundJoin
                    PathPolyline {
                        path: !hd.line ? [] : hd.h.kind === "turn" ? hd.h.points.map(p => gz.px(p)) : [gz.px(hd.h.a), gz.px(hd.h.b)]
                    }
                }
            }
            Rectangle {      // a move arrow's end (hollow while D moves the pivot), a scale cube, the middle square
                readonly property bool dot: hd.h !== undefined && hd.h.kind === "move" && hd.modelData !== "plane"
                readonly property bool plane: hd.modelData === "plane"
                readonly property real s: (plane ? 10 : dot ? (gizmo.pivot ? 8 : 10) : 8) + (hd.lit ? 3 : 0)
                visible: hd.h !== undefined && hd.h.kind !== "turn"
                width: s; height: s
                radius: dot ? s / 2 : 0
                x: hd.h && hd.h.kind !== "turn" ? (plane ? hd.h.a : hd.h.b)[0] * gz.width - s / 2 : 0
                y: hd.h && hd.h.kind !== "turn" ? (plane ? hd.h.a : hd.h.b)[1] * gz.height - s / 2 : 0
                color: plane || (dot && gizmo.pivot) ? "transparent" : hd.ink
                border.color: hd.ink
                border.width: plane || (dot && gizmo.pivot) ? (hd.lit ? 2.5 : 1.5) : 0
            }
        }
    }

    Connections {       // Esc cancelled the drag (esc3d.py): the press ends here too, without a tap
        target: gizmo
        function onChanged() { if (!gizmo.dragging && gz.grabbed !== "") { gz.grabbed = ""; gz.hot = "" } }
    }

    MouseArea {
        anchors.fill: parent
        hoverEnabled: true
        preventStealing: true
        property point from: Qt.point(0, 0)
        onPositionChanged: (m) => {
            gz.at = Qt.point(m.x, m.y)
            if (gz.grabbed !== "") gizmo.dragTo(m.x / width, m.y / height, (m.modifiers & Qt.ControlModifier) !== 0)
            else gz.hot = gizmo.hitAt(m.x / width, m.y / height)
        }
        onExited: if (gz.grabbed === "") gz.hot = ""
        cursorShape: gz.grabbed !== "" ? gz.held : gz.cursorFor(gz.hot)
        onPressed: (m) => {
            var h = m.button === Qt.LeftButton ? gizmo.hitAt(m.x / width, m.y / height) : ""
            gz.at = Qt.point(m.x, m.y)
            var shape = gz.cursorFor(h)
            if (h === "" || !gizmo.begin(h, m.x / width, m.y / height)) { m.accepted = false; return }
            gz.held = shape; gz.grabbed = h; from = Qt.point(m.x, m.y)
        }
        onReleased: (m) => {
            if (gz.grabbed === "") return
            gz.grabbed = ""; gizmo.end()
            if (Math.abs(m.x - from.x) + Math.abs(m.y - from.y) <= 3) gizmo.tap(m.x / width, m.y / height)
        }
        onCanceled: { if (gz.grabbed !== "") { gz.grabbed = ""; gizmo.end() } }
    }

    Rectangle {   // what the drag is doing ("X 0.150 m · ground", "Turn 15.0°", "Scale ×1.25"), beside the pointer
        visible: gizmo.label !== ""
        width: readout.implicitWidth + 2 * Theme.grid; height: Theme.button
        x: Math.max(Theme.pad, Math.min(gz.at.x + 18, gz.width - width - Theme.pad))
        y: gz.at.y + 22 + height < gz.height - Theme.pad ? gz.at.y + 22 : Math.max(Theme.pad, gz.at.y - height - 12)
        radius: Theme.radiusCtl; color: Theme.panel
        Text { id: readout; anchors.centerIn: parent; text: gizmo.label; color: Theme.fg
               font.family: uiFont; font.pixelSize: Theme.label }
    }
}
