import QtQuick
import RostrumKit

// The key bar's small curve (UX_SPEC 3.18): the first picked key's ease drawn from 0 to 1 (backend.keyBar.curve, the one
// evaluation), and, where the ease is a cubic, its two handles to drag (like a CSS cubic curve). A whole drag is one
// change on every picked key (backend.keyBar.begin / curveTo / end: key.handles). y may leave the box (overshoot).
Item {
    id: c
    implicitWidth: 96; implicitHeight: Theme.field
    readonly property var pts: backend.keyBar.curve
    readonly property var h: backend.keyBar.handles
    readonly property real pad: 4
    function px(x) { return pad + x * (width - 2 * pad) }
    function py(y) { return height - pad - y * (height - 2 * pad) }
    Rectangle { anchors.fill: parent; radius: Theme.radiusCtl; color: Theme.sunken; border.color: Theme.border }
    Canvas {
        id: canvas
        anchors.fill: parent
        onPaint: {
            const ctx = getContext("2d")
            ctx.reset()
            if (!c.pts.length) return
            ctx.strokeStyle = Theme.accent; ctx.lineWidth = 1.5
            ctx.beginPath()
            ctx.moveTo(c.px(c.pts[0][0]), c.py(c.pts[0][1]))
            for (let i = 1; i < c.pts.length; i++) ctx.lineTo(c.px(c.pts[i][0]), c.py(c.pts[i][1]))
            ctx.stroke()
            if (c.h.length !== 4) return
            ctx.strokeStyle = Theme.fg3; ctx.lineWidth = 1
            ctx.beginPath(); ctx.moveTo(c.px(0), c.py(0)); ctx.lineTo(c.px(c.h[0]), c.py(c.h[1])); ctx.stroke()
            ctx.beginPath(); ctx.moveTo(c.px(1), c.py(1)); ctx.lineTo(c.px(c.h[2]), c.py(c.h[3])); ctx.stroke()
        }
    }
    onPtsChanged: canvas.requestPaint()
    onHChanged: canvas.requestPaint()
    onWidthChanged: canvas.requestPaint()
    Repeater {   // the two handles
        model: c.h.length === 4 ? [0, 1] : []
        delegate: Rectangle {
            required property int modelData
            width: 7; height: 7; radius: 3.5; color: Theme.fg; border.color: Theme.accent
            x: c.px(c.h[2 * modelData]) - 3.5; y: c.py(c.h[2 * modelData + 1]) - 3.5
            MouseArea {
                anchors.fill: parent; anchors.margins: -5; preventStealing: true; cursorShape: Qt.SizeAllCursor
                property bool held: false
                onPressed: held = backend.keyBar.begin("curve")
                onPositionChanged: (m) => {
                    if (!held) return
                    const p = mapToItem(c, m.x, m.y)
                    const x = (p.x - c.pad) / (c.width - 2 * c.pad), y = (c.height - c.pad - p.y) / (c.height - 2 * c.pad)
                    const v = c.h.slice()
                    v[2 * modelData] = x; v[2 * modelData + 1] = y
                    backend.keyBar.curveTo(v[0], v[1], v[2], v[3])
                }
                onReleased: { if (held) backend.keyBar.end(); held = false }
                onCanceled: { if (held) backend.keyBar.end(); held = false }
            }
        }
    }
}
