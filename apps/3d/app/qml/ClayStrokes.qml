import QtQuick
import QtQuick.Shapes
import RostrumKit

// The Clay tool on the viewport (screen3d/clay_tool_qt.py, clay_stroke.py): with a brush chosen and a clay selected, a
// left drag goes to the brush. On the clay it sculpts (Ctrl: the opposite, Shift: Smooth), one undo step per stroke;
// a pen's pressure goes with every point (`pen`, a PointHandler for styluses only: it watches, the MouseArea still gets
// the pen as a mouse; a mouse sends -1, no pressure). With F held (`sizing`) the pointer's moves size the ring instead,
// its size in a chip beside it; on empty space the same drag turns the view (the pointer shows it) and a click selects
// what is there (the tool decides from the engine's answer, so the press is always taken here). The brush is a ring
// lying on the surface under the pointer, tilted with it, a faint inner circle where it works at half strength
// (Falloff), and in the middle a dot, or "−" / "+" while Ctrl turns it to its opposite; no other helper text. The ring
// is a Shape drawn on the GPU (a Canvas repainted the whole viewport on the CPU at every move). Lump's click and every
// other button fall through to the viewport.
Item {
    id: cs
    visible: viewport.clay.on
    readonly property real dpr: Screen.devicePixelRatio
    readonly property var ringPts: viewport.clay.ring
    readonly property bool shown: ringPts.length > 2 && area.inside
    readonly property string mark: viewport.clay.sizing ? "" : viewport.clay.ringMark

    function closed(k) {        // the ring's points in px, scaled by k about their middle, closed
        var r = ringPts, n = r.length, out = []
        if (n < 3) return out
        var cx = 0, cy = 0
        for (var i = 0; i < n; ++i) { cx += r[i][0]; cy += r[i][1] }
        cx /= n; cy /= n
        for (var j = 0; j <= n; ++j) {
            var p = r[j % n]
            out.push(Qt.point((cx + (p[0] - cx) * k) * width, (cy + (p[1] - cy) * k) * height))
        }
        return out
    }

    Shape {
        id: ring
        anchors.fill: parent
        visible: cs.shown
        preferredRendererType: Shape.CurveRenderer
        // laid out once per ring; a stroke only slides it (ringShift), so no outline is laid out again per dab
        transform: Translate { x: viewport.clay.ringShift[0] * cs.width; y: viewport.clay.ringShift[1] * cs.height }
        readonly property var outer: cs.shown ? cs.closed(1) : []
        readonly property var inner: cs.shown && !viewport.clay.sizing ? cs.closed(viewport.clay.ringInner) : []
        ShapePath {      // a dark edge under everything: readable on light clay
            strokeColor: Qt.rgba(0, 0, 0, 0.45); strokeWidth: 3; fillColor: "transparent"
            joinStyle: ShapePath.RoundJoin; capStyle: ShapePath.RoundCap
            PathPolyline { path: ring.outer }
        }
        ShapePath {
            strokeColor: "white"; strokeWidth: 1.5; fillColor: "transparent"
            joinStyle: ShapePath.RoundJoin; capStyle: ShapePath.RoundCap
            PathPolyline { path: ring.outer }
        }
        ShapePath {      // half strength (Falloff): faint
            strokeColor: Qt.rgba(1, 1, 1, 0.4); strokeWidth: 1; fillColor: "transparent"
            PathPolyline { path: ring.inner }
        }
    }
    Shape {              // Ctrl's "−" / "+" in the middle: a small fixed shape that follows the pointer
        x: area.mouseX - 6; y: area.mouseY - 6; width: 12; height: 12
        visible: cs.shown && cs.mark !== ""
        preferredRendererType: Shape.CurveRenderer
        ShapePath {
            strokeColor: Qt.rgba(0, 0, 0, 0.45); strokeWidth: 3; fillColor: "transparent"; capStyle: ShapePath.RoundCap
            PathPolyline { path: [Qt.point(2, 6), Qt.point(10, 6)] }
            PathPolyline { path: cs.mark === "+" ? [Qt.point(6, 2), Qt.point(6, 10)] : [] }
        }
        ShapePath {
            strokeColor: "white"; strokeWidth: 1.5; fillColor: "transparent"; capStyle: ShapePath.RoundCap
            PathPolyline { path: [Qt.point(2, 6), Qt.point(10, 6)] }
            PathPolyline { path: cs.mark === "+" ? [Qt.point(6, 2), Qt.point(6, 10)] : [] }
        }
    }
    Rectangle {          // the centre dot (no mark, not sizing)
        visible: cs.shown && cs.mark === "" && !viewport.clay.sizing
        x: area.mouseX - 1.5; y: area.mouseY - 1.5; width: 3; height: 3; radius: 1.5
        color: "white"; border.color: Qt.rgba(0, 0, 0, 0.45); border.width: 0.5
    }
    Rectangle {          // F + drag: the size, 16 px below-right of the pointer (flipped near the edges)
        id: chip
        visible: viewport.clay.sizing && viewport.clay.sizeText !== ""
        readonly property real gap: 16
        x: area.mouseX + gap + width > cs.width ? area.mouseX - gap - width : area.mouseX + gap
        y: area.mouseY + gap + height > cs.height ? area.mouseY - gap - height : area.mouseY + gap
        width: sizeLabel.implicitWidth + 2 * Theme.gap; height: sizeLabel.implicitHeight + Theme.grid
        radius: Theme.radiusCtl
        color: Theme.raised; border.color: Theme.popupEdge; border.width: 1
        Text {
            id: sizeLabel
            anchors.centerIn: parent
            text: viewport.clay.sizeText
            color: Theme.fg; font.family: uiFont; font.pixelSize: Theme.label
            font.features: { "tnum": 1 }
        }
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
        // a drag off the clay turning the view: the move pointer while it lasts; the ring hides the arrow
        cursorShape: pressed && viewport.clay.orbiting ? Qt.SizeAllCursor
                     : viewport.clay.ring.length > 2 ? Qt.BlankCursor : Qt.ArrowCursor
        property bool inside: false
        onEntered: inside = true
        onExited: { inside = false; viewport.clay.unhover() }
        onPressed: (m) => viewport.clay.press(m.x, m.y, cs.dpr, !!(m.modifiers & Qt.ControlModifier),
                                              !!(m.modifiers & Qt.ShiftModifier), cs.pressure())
        onPositionChanged: (m) => {
            viewport.clay.held(!!(m.modifiers & Qt.ControlModifier), !!(m.modifiers & Qt.ShiftModifier))
            if (viewport.clay.sizing) viewport.clay.sizeMove(m.x, m.y)
            else if (pressed) viewport.clay.move(m.x, m.y, cs.pressure())
            else viewport.clay.hover(m.x, m.y, cs.dpr)
        }
        onReleased: viewport.clay.release()
        onCanceled: viewport.clay.cancel()
    }
}
