import QtQuick
import RostrumKit

// Paint on the viewport (SPEC §5; screen3d/paint_mode_qt.py, paint_stroke.py): while Paint is on, a left drag paints on
// the mesh (On the surface: each point picked by the engine; From the view: kept as drawn; the paint lands on release, one
// undo step), the drag's trail is drawn in the brush's colour and width over the picture until the painted picture is on
// screen, and the brush shows as a disc at the pointer, its size as it lands on the surface.
// Right drag turns the view, middle drag too, Shift + drag pans (they fall through to the viewport); right-click is its menu.
Item {
    id: ps
    visible: paintMode.on
    readonly property real dpr: Screen.devicePixelRatio

    Canvas {
        id: trail
        anchors.fill: parent
        onPaint: {
            var c = getContext("2d"), t = paintMode.trail
            c.clearRect(0, 0, width, height)
            if (t.length > 1) {
                c.strokeStyle = paintMode.brushObj.colour; c.globalAlpha = 0.85
                c.lineWidth = Math.max(2, 2 * paintMode.cursorRadius / ps.dpr); c.lineCap = "round"; c.lineJoin = "round"
                c.beginPath(); c.moveTo(t[0][0] * width, t[0][1] * height)
                for (var i = 1; i < t.length; ++i) c.lineTo(t[i][0] * width, t[i][1] * height)
                c.stroke()
                c.globalAlpha = 1
            }
            if (area.inside) {
                var r = paintMode.cursorRadius / ps.dpr
                c.strokeStyle = "white"; c.lineWidth = 1.5
                c.beginPath(); c.arc(area.mouseX, area.mouseY, r, 0, 2 * Math.PI); c.stroke()
                c.strokeStyle = Qt.rgba(0, 0, 0, 0.5); c.lineWidth = 1
                c.beginPath(); c.arc(area.mouseX, area.mouseY, r + 1.5, 0, 2 * Math.PI); c.stroke()
            }
        }
        Connections { target: paintMode; function onTrailChanged() { trail.requestPaint() } }
    }

    MouseArea {
        id: area
        objectName: "paintArea"
        anchors.fill: parent
        enabled: paintMode.on
        acceptedButtons: Qt.LeftButton
        hoverEnabled: true
        preventStealing: true
        cursorShape: Qt.BlankCursor
        property bool inside: false
        onEntered: inside = true
        onExited: { inside = false; trail.requestPaint() }
        onPressed: (m) => {
            if (m.modifiers & Qt.ShiftModifier) { m.accepted = false; return }   // Shift + drag pans (the viewport's)
            paintMode.press(m.x * ps.dpr, m.y * ps.dpr)
        }
        onPositionChanged: (m) => { if (pressed) paintMode.move(m.x * ps.dpr, m.y * ps.dpr); trail.requestPaint() }
        onReleased: paintMode.release()
        onCanceled: paintMode.release()
    }
}
