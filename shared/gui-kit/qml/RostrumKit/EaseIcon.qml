import QtQuick
import "."

// An ease's small curve (the one ease list's `curve`: points [x, y] from 0 to 1, rostrum_core.keys.easing.EASE_LIST),
// drawn whole inside its box: a spring's overshoot is fitted in. The ease picker's rows and its closed button.
Canvas {
    id: c
    property var points: []
    property color ink: Theme.fg2
    implicitWidth: 28; implicitHeight: 18
    onPointsChanged: requestPaint()
    onInkChanged: requestPaint()
    onPaint: {
        const g = getContext("2d"), p = points || [], pad = 2
        g.reset()
        if (p.length < 2) return
        let lo = 0, hi = 1
        for (const q of p) { lo = Math.min(lo, q[1]); hi = Math.max(hi, q[1]) }
        const w = width - 2 * pad, h = height - 2 * pad
        const X = (x) => pad + x * w, Y = (y) => pad + (hi - y) / (hi - lo) * h
        g.strokeStyle = ink; g.lineWidth = 1.3; g.lineJoin = "round"
        g.beginPath(); g.moveTo(X(p[0][0]), Y(p[0][1]))
        for (let i = 1; i < p.length; i++) {
            if (p[i - 1][1] === 0 && p[i][1] === 1) g.lineTo(X(p[i][0]), Y(p[i - 1][1]))  // a hold: the step stands upright
            g.lineTo(X(p[i][0]), Y(p[i][1]))
        }
        g.stroke()
    }
}
