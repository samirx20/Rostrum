import QtQuick
import RostrumKit

// The Key block's curve (UX_SPEC 3.18): the first picked key's ease drawn from 0 to 1 (backend.keyBar.curve, the one
// evaluation), and, where the ease is a cubic, its two handles to drag (like a CSS cubic curve). A whole drag is one
// change on every picked key (backend.keyBar.begin / curveTo / end: key.handles).
// `source`: whatever offers curve, handles, begin / curveTo / end (the Key block, or a picked stretch: backend.stretch).
// The whole curve is always inside the box (as After Effects' and Cavalry's graph editors fit it): the value range is fitted
// to the curve and its handles (a spring's or a back ease's overshoot included, never less than 0..1), with `pad` px all
// round so a handle at a corner is whole. While a handle is dragged the range holds still (the point stays under the
// pointer) and only grows if the handle leaves it; it fits again on release. Faint lines mark the start and end values.
Item {
    id: c
    implicitWidth: 96; implicitHeight: 136
    clip: true
    property var source: backend.keyBar
    readonly property var pts: source.curve
    readonly property var h: source.handles
    readonly property real pad: 12              // px all round: a handle (and its grab ring) at a corner stays whole
    readonly property real grab: 14             // px: a press this near a handle takes it
    property var held: null                     // [lo, hi] while dragging
    readonly property var fit: {                // [lo, hi] of the values shown, with a little room above and below
        let lo = 0, hi = 1
        for (const p of c.pts) { lo = Math.min(lo, p[1]); hi = Math.max(hi, p[1]) }
        if (c.h.length === 4) { lo = Math.min(lo, c.h[1], c.h[3]); hi = Math.max(hi, c.h[1], c.h[3]) }
        const room = (lo < 0 || hi > 1) ? 0.06 * (hi - lo) : 0
        return [lo - room, hi + room]
    }
    readonly property var range: held ? [Math.min(held[0], fit[0]), Math.max(held[1], fit[1])] : fit
    function px(x) { return pad + x * (width - 2 * pad) }
    function py(y) { return height - pad - (y - range[0]) / (range[1] - range[0]) * (height - 2 * pad) }
    function vx(mx) { return (mx - pad) / (width - 2 * pad) }
    function vy(my) { return range[0] + (height - pad - my) / (height - 2 * pad) * (range[1] - range[0]) }
    Rectangle { anchors.fill: parent; radius: Theme.radiusCtl; color: Theme.sunken; border.color: Theme.border }
    Canvas {
        id: canvas
        anchors.fill: parent
        onPaint: {
            const ctx = getContext("2d")
            ctx.reset()
            ctx.strokeStyle = Theme.line; ctx.lineWidth = 1        // the start and end values
            for (const v of [0, 1]) { ctx.beginPath(); ctx.moveTo(c.px(0), Math.round(c.py(v)) + 0.5); ctx.lineTo(c.px(1), Math.round(c.py(v)) + 0.5); ctx.stroke() }
            if (!c.pts.length) return
            if (c.h.length === 4) {
                ctx.strokeStyle = Theme.fg3; ctx.lineWidth = 1
                ctx.beginPath(); ctx.moveTo(c.px(0), c.py(0)); ctx.lineTo(c.px(c.h[0]), c.py(c.h[1])); ctx.stroke()
                ctx.beginPath(); ctx.moveTo(c.px(1), c.py(1)); ctx.lineTo(c.px(c.h[2]), c.py(c.h[3])); ctx.stroke()
            }
            ctx.strokeStyle = Theme.accent; ctx.lineWidth = 2
            ctx.beginPath()
            ctx.moveTo(c.px(c.pts[0][0]), c.py(c.pts[0][1]))
            for (let i = 1; i < c.pts.length; i++) ctx.lineTo(c.px(c.pts[i][0]), c.py(c.pts[i][1]))
            ctx.stroke()
        }
    }
    onPtsChanged: canvas.requestPaint()
    onHChanged: canvas.requestPaint()
    onRangeChanged: canvas.requestPaint()
    onWidthChanged: canvas.requestPaint()
    onHeightChanged: canvas.requestPaint()
    Repeater {   // the two handles (drawn only; the one grab area below drags them)
        model: c.h.length === 4 ? [0, 1] : []
        delegate: Rectangle {
            required property int modelData
            readonly property bool hot: grabArea.which === modelData || grabArea.near === modelData
            width: hot ? 12 : 10; height: width; radius: width / 2
            color: hot ? Theme.accent : Theme.fg; border.color: Theme.accent; border.width: 1.5
            x: c.px(c.h[2 * modelData]) - width / 2; y: c.py(c.h[2 * modelData + 1]) - height / 2
        }
    }
    MouseArea {   // one grab area for both handles: a press takes the nearer one (within `grab` px), so their targets never cross
        id: grabArea
        anchors.fill: parent
        enabled: c.h.length === 4
        preventStealing: true
        hoverEnabled: true
        property int which: -1
        readonly property int near: containsMouse && which < 0 ? nearest(mouseX, mouseY) : -1
        function nearest(mx, my) {
            let best = -1, bestD = c.grab * c.grab
            for (let i = 0; i < 2; i++) {
                const dx = c.px(c.h[2 * i]) - mx, dy = c.py(c.h[2 * i + 1]) - my, d = dx * dx + dy * dy
                if (d <= bestD) { best = i; bestD = d }
            }
            return best
        }
        cursorShape: which >= 0 || near >= 0 ? Qt.SizeAllCursor : Qt.ArrowCursor
        onPressed: (m) => {
            const i = nearest(m.x, m.y)
            if (i < 0 || !c.source.begin("curve")) { m.accepted = false; return }
            which = i; c.held = c.range
        }
        onPositionChanged: (m) => {
            if (which < 0) return
            const v = c.h.slice()
            v[2 * which] = Math.max(0, Math.min(1, c.vx(m.x))); v[2 * which + 1] = c.vy(m.y)
            c.source.curveTo(v[0], v[1], v[2], v[3])
        }
        function done() { if (which >= 0) c.source.end(); which = -1; c.held = null }
        onReleased: done()
        onCanceled: done()
    }
}
