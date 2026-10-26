import QtQuick
import RostrumKit

// A small drawn icon per item kind: rectangle / ellipse shape, text, image, video (a film strip), group, drawing (and a painting), path, the frame (kind "camera": a box with corner marks), rig, mask, and (any other) effect.
// `lit` shows it in `litInk` (a selected row). Each ink is drawn once and kept: a pick only swaps which one shows, never
// repaints (a Canvas repaint per row was ~20-45 ms of a pick that un-lit 200 rows). The lit one is made the first time it is lit.
Item {
    id: icon
    property string kind: "shape"
    property string shape: "rect"
    property color ink: Theme.fg2
    property color litInk: ink
    property bool lit: false
    width: 14; height: 14
    onLitChanged: if (lit) litOne.active = true
    Component.onCompleted: if (lit) litOne.active = true
    Drawn { kind: icon.kind; shape: icon.shape; ink: icon.ink; visible: !icon.lit }
    Loader {
        id: litOne
        active: false
        visible: icon.lit
        sourceComponent: Drawn { kind: icon.kind; shape: icon.shape; ink: icon.litInk }
    }

    component Drawn: Canvas {
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
            } else if (kind === "drawing" || kind === "painting") {   // a pen stroke (a painting opened on its own too)
                g.beginPath(); g.moveTo(2, 10.5); g.bezierCurveTo(4, 2, 7, 2, 7, 7); g.bezierCurveTo(7, 12, 10, 11, 12, 3.5); g.stroke()
            } else if (kind === "path") {      // a Bézier curve between two square points
                g.beginPath(); g.moveTo(3.5, 10.5); g.bezierCurveTo(3.5, 3, 10.5, 11, 10.5, 3.5); g.stroke()
                g.fillRect(1.5, 9, 3, 3); g.fillRect(9, 2, 3, 3)
            } else if (kind === "camera") {    // the frame: a box with a mark across each corner
                g.beginPath()
                g.moveTo(1.5, 5); g.lineTo(1.5, 1.5); g.lineTo(5, 1.5); g.moveTo(9, 1.5); g.lineTo(12.5, 1.5); g.lineTo(12.5, 5)
                g.moveTo(12.5, 9); g.lineTo(12.5, 12.5); g.lineTo(9, 12.5); g.moveTo(5, 12.5); g.lineTo(1.5, 12.5); g.lineTo(1.5, 9)
                g.stroke(); g.fillRect(5.5, 5.5, 3, 3)
            } else if (kind === "video") {     // a film strip: a frame with sprocket holes down both sides
                rr(1.5, 2, 11, 10, 1.5); g.stroke()
                g.fillRect(3, 3.5, 1.5, 1.5); g.fillRect(3, 6.3, 1.5, 1.5); g.fillRect(3, 9.1, 1.5, 1.5)
                g.fillRect(9.5, 3.5, 1.5, 1.5); g.fillRect(9.5, 6.3, 1.5, 1.5); g.fillRect(9.5, 9.1, 1.5, 1.5)
            } else if (kind === "rig" || kind === "bone") {    // two joints joined by a bone
                g.beginPath(); g.moveTo(3.5, 10.5); g.lineTo(10.5, 3.5); g.stroke()
                g.beginPath(); g.ellipse(1.5, 8.5, 4, 4); g.fill(); g.beginPath(); g.ellipse(8.5, 1.5, 4, 4); g.fill()
            } else if (kind === "mask") {
                rr(1.5, 1.5, 11, 11, 2); g.stroke(); g.beginPath(); g.ellipse(4.5, 4.5, 5, 5); g.fill()
            } else {   // an effect: a small spark
                g.beginPath(); g.moveTo(7, 1.5); g.lineTo(8.3, 5.7); g.lineTo(12.5, 7); g.lineTo(8.3, 8.3)
                g.lineTo(7, 12.5); g.lineTo(5.7, 8.3); g.lineTo(1.5, 7); g.lineTo(5.7, 5.7); g.closePath(); g.fill()
            }
        }
    }
}
