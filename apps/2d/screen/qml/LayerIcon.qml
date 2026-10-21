import QtQuick
import RostrumKit

// A small drawn icon per item kind: rectangle / ellipse shape, text, image, group, effect, mask.
Canvas {
    id: c
    property string kind: "shape"
    property string shape: "rect"
    property color ink: Theme.fg2
    width: 14; height: 14
    onKindChanged: requestPaint()
    onShapeChanged: requestPaint()
    onInkChanged: requestPaint()
    onPaint: {
        var g = getContext("2d")
        g.reset()
        g.strokeStyle = ink; g.fillStyle = ink; g.lineWidth = 1.4; g.lineJoin = "round"
        function rr(x, y, w, h, r) { g.beginPath(); g.roundedRect(x, y, w, h, r, r) }
        if (kind === "text") {
            g.beginPath(); g.moveTo(2.5, 3); g.lineTo(11.5, 3); g.moveTo(7, 3); g.lineTo(7, 12); g.stroke()
        } else if (kind === "shape" && shape === "ellipse") {
            g.beginPath(); g.ellipse(2, 2, 10, 10); g.stroke()
        } else if (kind === "shape") {
            rr(2, 2, 10, 10, 2); g.stroke()
        } else if (kind === "image") {
            rr(1.5, 2.5, 11, 9, 1.5); g.stroke()
            g.beginPath(); g.moveTo(3, 10); g.lineTo(6, 6.5); g.lineTo(8, 8.5); g.lineTo(9.5, 7); g.lineTo(11, 10); g.stroke()
        } else if (kind === "group") {
            rr(1.5, 4.5, 8, 8, 1.5); g.stroke(); rr(4.5, 1.5, 8, 8, 1.5); g.stroke()
        } else if (kind === "mask") {
            rr(1.5, 1.5, 11, 11, 2); g.stroke(); g.beginPath(); g.ellipse(4.5, 4.5, 5, 5); g.fill()
        } else {   // an effect: a small spark
            g.beginPath(); g.moveTo(7, 1.5); g.lineTo(8.3, 5.7); g.lineTo(12.5, 7); g.lineTo(8.3, 8.3)
            g.lineTo(7, 12.5); g.lineTo(5.7, 8.3); g.lineTo(1.5, 7); g.lineTo(5.7, 5.7); g.closePath(); g.fill()
        }
    }
}
