import QtQuick
import RostrumKit

// The small lock and eye on a layer's row (LayerName.qml). `on`: locked / hidden (drawn in the accent colour, the eye
// crossed out); off: a quiet outline shown only while the pointer is on the row. Kind "pin": the glyph by a layer's name
// while it is pinned to the frame (a mark, not a switch).
Canvas {
    id: c
    property string kind: "locked"
    property bool on: false
    property bool hot: false
    readonly property color ink: on ? Theme.accentHover : hot ? Theme.fg : Theme.fg3
    width: 14; height: 14
    onKindChanged: requestPaint()
    onOnChanged: requestPaint()
    onInkChanged: requestPaint()
    onPaint: {
        var g = getContext("2d")
        g.reset()
        g.strokeStyle = ink; g.fillStyle = ink; g.lineWidth = 1.3; g.lineJoin = "round"
        if (kind === "locked") {
            g.beginPath(); g.roundedRect(2.5, 6.5, 9, 6, 1.5, 1.5); if (on) g.fill(); else g.stroke()
            g.beginPath(); g.moveTo(4.5, 6.5); g.lineTo(4.5, 4.5); g.bezierCurveTo(4.5, 1.2, 9.5, 1.2, 9.5, 4.5)
            g.lineTo(on ? 9.5 : 9.5, on ? 6.5 : 3); g.stroke()
        } else if (kind === "pin") {
            g.beginPath(); g.moveTo(4.5, 2); g.lineTo(9.5, 2); g.stroke()
            g.beginPath(); g.moveTo(5.5, 2); g.lineTo(5.5, 6.5); g.lineTo(3.5, 8.5); g.lineTo(10.5, 8.5); g.lineTo(8.5, 6.5)
            g.lineTo(8.5, 2); g.stroke()
            g.beginPath(); g.moveTo(7, 8.5); g.lineTo(7, 13); g.stroke()
        } else {
            g.beginPath(); g.moveTo(1, 7); g.bezierCurveTo(4, 2, 10, 2, 13, 7); g.bezierCurveTo(10, 12, 4, 12, 1, 7); g.stroke()
            g.beginPath(); g.ellipse(5, 5, 4, 4); if (on) g.fill(); else g.stroke()
            if (on) { g.beginPath(); g.moveTo(2, 12); g.lineTo(12, 2); g.stroke() }
        }
    }
}
