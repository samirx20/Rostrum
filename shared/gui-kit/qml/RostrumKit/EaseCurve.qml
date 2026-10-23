import QtQuick
import RostrumKit

// The Key block's curve (UX_SPEC 3.18): the first picked key's ease drawn from 0 to 1 (backend.keyBar.curve, the one
// evaluation), and, where the ease is a cubic, its two handles to drag (like a CSS cubic curve). A whole drag is one
// change on every picked key (backend.keyBar.begin / curveTo / end: key.handles). y may leave the box (overshoot).
// `source`: whatever offers curve, handles, begin / curveTo / end (the Key block, or a picked stretch: backend.stretch).
Item {
    id: c
    implicitWidth: 96; implicitHeight: Theme.field
    property var source: backend.keyBar
    readonly property var pts: source.curve
    readonly property var h: source.handles
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
    Repeater {   // the two handles (drawn only; the one grab area below drags them)
        model: c.h.length === 4 ? [0, 1] : []
        delegate: Rectangle {
            required property int modelData
            width: 7; height: 7; radius: 3.5; color: Theme.fg; border.color: Theme.accent
            x: c.px(c.h[2 * modelData]) - 3.5; y: c.py(c.h[2 * modelData + 1]) - 3.5
        }
    }
    MouseArea {   // one grab area for both handles: a press takes the nearer one (within 9 px), so their targets never cross
        anchors.fill: parent
        enabled: c.h.length === 4
        preventStealing: true
        hoverEnabled: true
        property int which: -1
        function nearest(mx, my) {
            let best = -1, bestD = 9 * 9
            for (let i = 0; i < 2; i++) {
                const dx = c.px(c.h[2 * i]) - mx, dy = c.py(c.h[2 * i + 1]) - my, d = dx * dx + dy * dy
                if (d <= bestD) { best = i; bestD = d }
            }
            return best
        }
        cursorShape: which >= 0 || containsMouse && nearest(mouseX, mouseY) >= 0 ? Qt.SizeAllCursor : Qt.ArrowCursor
        onPressed: (m) => {
            const i = nearest(m.x, m.y)
            if (i < 0 || !c.source.begin("curve")) { m.accepted = false; return }
            which = i
        }
        onPositionChanged: (m) => {
            if (which < 0) return
            const x = (m.x - c.pad) / (c.width - 2 * c.pad), y = (c.height - c.pad - m.y) / (c.height - 2 * c.pad)
            const v = c.h.slice()
            v[2 * which] = x; v[2 * which + 1] = y
            c.source.curveTo(v[0], v[1], v[2], v[3])
        }
        onReleased: { if (which >= 0) c.source.end(); which = -1 }
        onCanceled: { if (which >= 0) c.source.end(); which = -1 }
    }
}
