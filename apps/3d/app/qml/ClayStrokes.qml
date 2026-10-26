import QtQuick
import RostrumKit

// The Clay tool on the viewport (screen3d/clay_tool_qt.py, clay_stroke.py): with a brush chosen and a clay selected, a
// left drag goes to the brush. On the clay it sculpts (Ctrl: the opposite, Shift: Smooth), one undo step per stroke;
// a pen's pressure goes with every point (`pen`, a PointHandler for styluses only: it watches, the MouseArea still gets
// the pen as a mouse; a mouse sends -1, no pressure). With F held (`sizing`) the pointer's moves size the ring instead;
// on empty space the same drag turns the view and a click selects what is there (the tool decides from the engine's
// answer, so the press is always taken here). The brush is a ring lying on the surface under the pointer, nothing
// else is drawn (no helper text on the viewport). Lump's click and every other button fall through to the viewport.
Item {
    id: cs
    visible: viewport.clay.on
    readonly property real dpr: Screen.devicePixelRatio

    Canvas {
        id: ring
        anchors.fill: parent
        onPaint: {
            var c = getContext("2d"), r = viewport.clay.ring
            c.clearRect(0, 0, width, height)
            if (r.length < 3 || !area.inside) return
            c.lineJoin = "round"
            c.beginPath(); c.moveTo(r[0][0] * width, r[0][1] * height)
            for (var i = 1; i < r.length; ++i) c.lineTo(r[i][0] * width, r[i][1] * height)
            c.closePath()
            c.strokeStyle = Qt.rgba(0, 0, 0, 0.45); c.lineWidth = 3; c.stroke()     // a dark edge: readable on light clay
            c.strokeStyle = "white"; c.lineWidth = 1.5; c.stroke()
            if (viewport.clay.sizing) return                                         // F + drag: the ring alone
            c.fillStyle = "white"
            c.beginPath(); c.arc(area.mouseX, area.mouseY, 1.5, 0, 2 * Math.PI); c.fill()
        }
        Connections { target: viewport.clay; function onRingChanged() { ring.requestPaint() } }
    }

    PointHandler {      // a pen's pressure, read by the MouseArea's handlers below (they come from the same pen event)
        id: pen
        objectName: "clayPen"
        enabled: viewport.clay.sculpts
        acceptedDevices: PointerDevice.Stylus | PointerDevice.Airbrush
    }
    function pressure() { return pen.active ? pen.point.pressure : -1 }

    MouseArea {
        id: area
        objectName: "clayArea"
        anchors.fill: parent
        enabled: viewport.clay.sculpts
        acceptedButtons: Qt.LeftButton
        hoverEnabled: true
        preventStealing: true
        cursorShape: viewport.clay.ring.length > 2 ? Qt.BlankCursor : Qt.ArrowCursor
        property bool inside: false
        onEntered: inside = true
        onExited: { inside = false; viewport.clay.unhover(); ring.requestPaint() }
        onPressed: (m) => viewport.clay.press(m.x, m.y, cs.dpr, !!(m.modifiers & Qt.ControlModifier),
                                              !!(m.modifiers & Qt.ShiftModifier), cs.pressure())
        onPositionChanged: (m) => {
            if (viewport.clay.sizing) viewport.clay.sizeMove(m.x, m.y)
            else if (pressed) viewport.clay.move(m.x, m.y, cs.pressure())
            else viewport.clay.hover(m.x, m.y, cs.dpr)
        }
        onReleased: viewport.clay.release()
        onCanceled: viewport.clay.cancel()
        onWheel: (w) => viewport.zoom(w.angleDelta.y / 120)
    }
}
