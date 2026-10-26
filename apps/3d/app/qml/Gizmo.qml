import QtQuick
import RostrumKit

// The selected item's gizmo over the viewport (screen3d/gizmo_qt.py has the maths and the edits): move arrows and the
// middle square, turn rings, scale cubes, in the axis colours (X red, Y green, Z blue). A press on a handle drags it
// (one undo step); a press anywhere else falls through to the viewport (orbit, pick). Ctrl while dragging frees the
// snapping. While D is held only the move handles show: they move the pivot. A click on a handle that never drags goes
// to a bone drawn there (a mesh's arrows cross its bones on the Animate page): the bone is picked.
Item {
    id: gz
    readonly property var colours: [Theme.danger, "#5fbf6a", Theme.accent]
    property string hot: ""

    Canvas {
        id: canvas
        anchors.fill: parent
        renderStrategy: Canvas.Cooperative
        onPaint: {
            var c = getContext("2d"), w = width, h = height
            c.reset()
            var hs = gizmo.handles
            for (var i = 0; i < hs.length; i++) {
                var hd = hs[i], col = hd.axis < 0 ? Theme.fg : gz.colours[hd.axis]
                c.strokeStyle = col; c.fillStyle = col
                c.lineWidth = hd.id === gz.hot ? 3 : 1.5
                if (hd.kind === "turn") {
                    c.beginPath()
                    for (var k = 0; k < hd.points.length; k++) {
                        var p = hd.points[k]
                        if (k === 0) c.moveTo(p[0] * w, p[1] * h); else c.lineTo(p[0] * w, p[1] * h)
                    }
                    c.stroke()
                } else if (hd.id === "plane") {
                    c.strokeRect(hd.a[0] * w - 5, hd.a[1] * h - 5, 10, 10)
                } else if (hd.kind === "scale") {
                    c.fillRect(hd.b[0] * w - 4, hd.b[1] * h - 4, 8, 8)
                } else {
                    c.beginPath(); c.moveTo(hd.a[0] * w, hd.a[1] * h); c.lineTo(hd.b[0] * w, hd.b[1] * h); c.stroke()
                    c.beginPath(); c.arc(hd.b[0] * w, hd.b[1] * h, gizmo.pivot ? 4 : 5, 0, 2 * Math.PI)
                    if (gizmo.pivot) c.stroke(); else c.fill()
                }
            }
        }
        Connections { target: gizmo; function onChanged() { canvas.requestPaint() } }
        onWidthChanged: requestPaint()
        onHeightChanged: requestPaint()
    }

    MouseArea {
        anchors.fill: parent
        hoverEnabled: true
        preventStealing: true
        property string grabbed: ""
        property point from: Qt.point(0, 0)
        onPositionChanged: (m) => {
            if (grabbed !== "") gizmo.dragTo(m.x / width, m.y / height, (m.modifiers & Qt.ControlModifier) !== 0)
            else gz.hot = gizmo.hitAt(m.x / width, m.y / height)
        }
        onExited: if (grabbed === "") gz.hot = ""
        cursorShape: gz.hot !== "" ? Qt.PointingHandCursor : Qt.ArrowCursor
        onPressed: (m) => {
            var h = m.button === Qt.LeftButton ? gizmo.hitAt(m.x / width, m.y / height) : ""
            if (h === "" || !gizmo.begin(h, m.x / width, m.y / height)) { m.accepted = false; return }
            grabbed = h; from = Qt.point(m.x, m.y)
        }
        onReleased: (m) => {
            if (grabbed === "") return
            grabbed = ""; gizmo.end()
            if (Math.abs(m.x - from.x) + Math.abs(m.y - from.y) <= 3) gizmo.tap(m.x / width, m.y / height)
        }
        onCanceled: { if (grabbed !== "") { grabbed = ""; gizmo.end() } }
    }

    Rectangle {   // what the drag is doing ("X 0.150 m · ground", "Turn 15.0°", "Scale ×1.25")
        visible: gizmo.label !== ""
        x: Theme.pad; y: Theme.pad
        width: readout.implicitWidth + 2 * Theme.grid; height: Theme.button
        radius: Theme.radiusCtl; color: Theme.panel
        Text { id: readout; anchors.centerIn: parent; text: gizmo.label; color: Theme.fg
               font.family: uiFont; font.pixelSize: Theme.label }
    }
}
