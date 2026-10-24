import QtQuick
import RostrumKit

// Edit mesh over the viewport (screen3d/mesh_edit_qt.py has the picking and the edits): the mesh's edges as thin lines,
// the picked points / edges / faces in the selection blue (faces tinted), and with Extrude the arrow on the picked
// faces. A click picks what is under the pointer (Shift adds or takes away), a drag on empty space draws a box, a
// drag on the arrow sets the extrude distance (one undo step on release; Ctrl frees the 0.5 mm steps). The middle
// button still orbits (Viewport.qml). Only there while Edit mesh is on.
Item {
    id: me
    visible: meshEdit.on
    property bool hot: false

    Canvas {
        id: canvas
        anchors.fill: parent
        renderStrategy: Canvas.Cooperative
        onPaint: {
            var c = getContext("2d"), w = width, h = height, o = meshEdit.overlay
            c.reset()
            if (!o.lines) return
            function path(ps) { c.beginPath(); for (var k = 0; k < ps.length; k++) { if (k === 0) c.moveTo(ps[k][0] * w, ps[k][1] * h); else c.lineTo(ps[k][0] * w, ps[k][1] * h) } }
            c.fillStyle = Qt.rgba(Theme.accent.r, Theme.accent.g, Theme.accent.b, 0.28); c.strokeStyle = Theme.accent; c.lineWidth = 1.5
            for (var f = 0; f < o.faces.length; f++) { path(o.faces[f]); c.closePath(); c.fill(); c.stroke() }
            c.strokeStyle = Qt.rgba(1, 1, 1, 0.55); c.lineWidth = 1
            for (var i = 0; i < o.lines.length; i++) { path(o.lines[i]); c.stroke() }
            c.strokeStyle = Theme.accent; c.lineWidth = 2.5
            for (var e = 0; e < o.edges.length; e++) { path(o.edges[e]); c.stroke() }
            c.fillStyle = Qt.rgba(1, 1, 1, 0.8)
            var dots = o.dots || []
            for (var d = 0; d < dots.length; d++) c.fillRect(dots[d][0] * w - 2, dots[d][1] * h - 2, 4, 4)
            c.fillStyle = Theme.accent
            for (var p = 0; p < o.points.length; p++) c.fillRect(o.points[p][0] * w - 3.5, o.points[p][1] * h - 3.5, 7, 7)
            if (o.arrow && o.arrow.length === 2) {
                var a = o.arrow[0], b = o.arrow[1], dx = (b[0] - a[0]) * w, dy = (b[1] - a[1]) * h
                var n = Math.max(1, Math.sqrt(dx * dx + dy * dy)), ux = dx / n, uy = dy / n
                c.strokeStyle = Theme.fg; c.fillStyle = Theme.fg; c.lineWidth = me.hot || area.arrow ? 3 : 2
                c.beginPath(); c.moveTo(a[0] * w, a[1] * h); c.lineTo(b[0] * w, b[1] * h); c.stroke()
                c.beginPath(); c.moveTo(b[0] * w + ux * 10, b[1] * h + uy * 10)
                c.lineTo(b[0] * w - uy * 6, b[1] * h + ux * 6); c.lineTo(b[0] * w + uy * 6, b[1] * h - ux * 6); c.closePath(); c.fill()
            }
        }
        Connections { target: meshEdit; function onChanged() { canvas.requestPaint() } }
        onWidthChanged: requestPaint()
        onHeightChanged: requestPaint()
    }

    Rectangle {   // the box being dragged
        visible: area.boxing
        x: Math.min(area.sx, area.cx); y: Math.min(area.sy, area.cy)
        width: Math.abs(area.cx - area.sx); height: Math.abs(area.cy - area.sy)
        color: Qt.rgba(Theme.accent.r, Theme.accent.g, Theme.accent.b, 0.12); border.width: 1; border.color: Theme.accent
    }

    MouseArea {
        id: area
        anchors.fill: parent
        enabled: meshEdit.on && !meshEdit.needsEdit
        hoverEnabled: true
        preventStealing: true
        property real sx: 0
        property real sy: 0
        property real cx: 0
        property real cy: 0
        property bool boxing: false
        property bool arrow: false
        cursorShape: me.hot || arrow ? Qt.PointingHandCursor : Qt.ArrowCursor
        onPressed: (m) => {
            sx = cx = m.x; sy = cy = m.y; boxing = false
            arrow = meshEdit.arrowHit(m.x / width, m.y / height) && meshEdit.arrowBegin(m.x / width, m.y / height)
        }
        onPositionChanged: (m) => {
            if (!pressed) { me.hot = meshEdit.arrowHit(m.x / width, m.y / height); canvas.requestPaint(); return }
            cx = m.x; cy = m.y
            if (arrow) meshEdit.arrowDrag(m.x / width, m.y / height, (m.modifiers & Qt.ControlModifier) !== 0)
            else boxing = boxing || Math.abs(cx - sx) + Math.abs(cy - sy) > 4
        }
        onReleased: (m) => {
            var shift = (m.modifiers & Qt.ShiftModifier) !== 0
            if (arrow) meshEdit.arrowEnd()
            else if (boxing) meshEdit.boxSelect(sx / width, sy / height, cx / width, cy / height, shift)
            else meshEdit.clickAt(m.x / width, m.y / height, shift)
            arrow = false; boxing = false
        }
        onCanceled: { if (arrow) meshEdit.arrowEnd(); arrow = false; boxing = false }
    }

    Rectangle {   // the arrow drag's distance ("Distance 2.0 mm")
        visible: meshEdit.dragLabel !== ""
        x: Theme.pad; y: Theme.pad
        width: readout.implicitWidth + 2 * Theme.grid; height: Theme.button
        radius: Theme.radiusCtl; color: Theme.panel
        Text { id: readout; anchors.centerIn: parent; text: meshEdit.dragLabel; color: Theme.fg
               font.family: uiFont; font.pixelSize: Theme.label }
    }
}
