import QtQuick
import QtQuick.Shapes
import RostrumKit
import RostrumCursors 1.0

// Draw and Spin on the viewport (screen3d/clay_draw_qt.py, `d`: viewport.clay.drawer). While one is chosen, a left drag
// always draws (it never turns the view): the line follows the pointer (a Shape, drawn on the GPU), the pointer is the
// kit's pen, and a chip 16 px below-right of it says the outline's size. Spin shows its axis, a vertical line at the
// pointer, before the press. The clay a drag would join is outlined in the picture (the viewport's own outline). The
// release makes the clay: until the engine's picture shows it, the outline stays, closed and filled with a clay grey
// (`landing`; Spin's profile stays as a line), so the release is seen at once. Esc mid-drag (esc3d.py) drops the line
// with nothing changed. Other buttons fall through.
Item {
    id: dr
    property QtObject d: null
    visible: d !== null && d.on
    readonly property real dpr: Screen.devicePixelRatio

    function pts(list) {
        var out = []
        for (var i = 0; i < list.length; ++i) out.push(Qt.point(list[i][0], list[i][1]))
        return out
    }

    Shape {
        id: line
        anchors.fill: parent
        preferredRendererType: Shape.CurveRenderer
        readonly property var path: dr.d ? dr.pts(dr.d.line) : []
        readonly property var axis: {      // Spin's axis: parts of the picture
            var a = dr.d ? dr.d.axis : [], out = []
            for (var i = 0; i < a.length; ++i) out.push(Qt.point(a[i][0] * dr.width, a[i][1] * dr.height))
            return out
        }
        ShapePath {      // a dark edge under the line: readable on light clay and sky
            strokeColor: Qt.rgba(0, 0, 0, 0.45); strokeWidth: 3.5; fillColor: "transparent"
            joinStyle: ShapePath.RoundJoin; capStyle: ShapePath.RoundCap
            PathPolyline { path: line.path }
            PathPolyline { path: line.axis }
        }
        ShapePath {
            strokeColor: "white"; strokeWidth: 1.5; fillColor: "transparent"
            joinStyle: ShapePath.RoundJoin; capStyle: ShapePath.RoundCap
            PathPolyline { path: line.path }
        }
        ShapePath {      // the axis: the accent, dashed (it is a guide, not what is drawn)
            strokeColor: Theme.accent; strokeWidth: 1.5; fillColor: "transparent"
            strokeStyle: ShapePath.DashLine; dashPattern: [4, 3]
            PathPolyline { path: line.axis }
        }
    }
    Shape {              // released, not yet built: the outline closed and filled, where the clay is about to puff
        id: landingShape
        objectName: "clayDrawLanding"
        anchors.fill: parent
        visible: dr.d !== null && dr.d.landing.length > 1
        preferredRendererType: Shape.CurveRenderer
        readonly property var path: { var p = dr.d ? dr.pts(dr.d.landing) : []; if (p.length > 2 && dr.d.landingFilled) p.push(p[0]); return p }
        ShapePath {
            strokeColor: Qt.rgba(0, 0, 0, 0.45); strokeWidth: 3.5
            fillColor: dr.d && dr.d.landingFilled ? Qt.rgba(0.72, 0.71, 0.69, 0.55) : "transparent"
            joinStyle: ShapePath.RoundJoin; capStyle: ShapePath.RoundCap
            PathPolyline { path: landingShape.path }
        }
        ShapePath {
            strokeColor: "white"; strokeWidth: 1.5; fillColor: "transparent"
            joinStyle: ShapePath.RoundJoin; capStyle: ShapePath.RoundCap
            PathPolyline { path: landingShape.path }
        }
    }
    Rectangle {          // the outline's size, 16 px below-right of the pointer (flipped near the edges)
        id: chip
        objectName: "clayDrawChip"
        visible: area.pressed && dr.d !== null && dr.d.chip !== ""
        readonly property real gap: 16
        x: area.mouseX + gap + width > dr.width ? area.mouseX - gap - width : area.mouseX + gap
        y: area.mouseY + gap + height > dr.height ? area.mouseY - gap - height : area.mouseY + gap
        width: chipLabel.implicitWidth + 2 * Theme.gap; height: chipLabel.implicitHeight + Theme.grid
        radius: Theme.radiusCtl
        color: Theme.raised; border.color: Theme.popupEdge; border.width: 1
        Text {
            id: chipLabel
            anchors.centerIn: parent
            text: dr.d ? dr.d.chip : ""
            color: Theme.fg; font.family: uiFont; font.pixelSize: Theme.label
            font.features: { "tnum": 1 }
        }
    }

    MouseArea {
        id: area
        objectName: "clayDrawArea"
        anchors.fill: parent
        enabled: dr.visible
        acceptedButtons: Qt.LeftButton
        hoverEnabled: true
        preventStealing: true
        onExited: dr.d.unhover()
        onPressed: (m) => dr.d.press(m.x, m.y, dr.dpr)
        onPositionChanged: (m) => { if (pressed) dr.d.move(m.x, m.y); else dr.d.hover(m.x, m.y, dr.dpr) }
        onReleased: dr.d.release()
        onCanceled: dr.d.cancel()
        CanvasCursor { kind: "pen" }    // the pencil: a press here draws
    }
}
