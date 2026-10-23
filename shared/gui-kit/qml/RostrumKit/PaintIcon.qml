import QtQuick
import "."

// The small drawn icons of the paint pickers, 14 x 14, one `ink` colour: the fill types (none, solid, linear, radial,
// angular, picture) and "pipette" (pick from the screen) and "swap" (reverse the stops).
Canvas {
    id: c
    property string kind: "solid"
    property color ink: Theme.fg2
    width: 14; height: 14
    onKindChanged: requestPaint()
    onInkChanged: requestPaint()
    function fade(a) { return Qt.rgba(ink.r, ink.g, ink.b, a) }
    onPaint: {
        var g = getContext("2d")
        g.reset()
        g.strokeStyle = ink; g.fillStyle = ink; g.lineWidth = 1.4; g.lineCap = "round"; g.lineJoin = "round"
        var k = kind, grad = null
        if (k === "none") {
            g.beginPath(); g.roundedRect(1.5, 1.5, 11, 11, 2.5, 2.5); g.stroke()
            g.beginPath(); g.moveTo(3, 11); g.lineTo(11, 3); g.stroke()
        } else if (k === "solid") {
            g.beginPath(); g.roundedRect(1.5, 1.5, 11, 11, 2.5, 2.5); g.fill()
        } else if (k === "linear" || k === "radial" || k === "angular") {
            if (k === "linear") { grad = g.createLinearGradient(1, 0, 13, 0); grad.addColorStop(0, fade(1)); grad.addColorStop(1, fade(0.15)) }
            else if (k === "radial") { grad = g.createRadialGradient(7, 7, 0, 7, 7, 8); grad.addColorStop(0, fade(1)); grad.addColorStop(1, fade(0.15)) }
            else { grad = g.createConicalGradient(7, 7, 0); grad.addColorStop(0, fade(1)); grad.addColorStop(0.5, fade(0.15)); grad.addColorStop(1, fade(1)) }
            g.fillStyle = grad
            g.beginPath(); g.roundedRect(1.5, 1.5, 11, 11, 2.5, 2.5); g.fill()
        } else if (k === "picture") {
            g.beginPath(); g.roundedRect(1.5, 1.5, 11, 11, 2.5, 2.5); g.stroke()
            g.beginPath(); g.moveTo(2.5, 10.5); g.lineTo(5.5, 6.5); g.lineTo(8, 9); g.lineTo(9.5, 7.5); g.lineTo(11.5, 10.5); g.stroke()
        } else if (k === "pipette") {
            g.beginPath(); g.moveTo(2, 12); g.lineTo(3, 9); g.lineTo(9, 3); g.lineTo(11, 5); g.lineTo(5, 11); g.closePath(); g.stroke()
            g.beginPath(); g.moveTo(8, 2); g.lineTo(12, 6); g.stroke()
        } else if (k === "swap") {
            g.beginPath(); g.moveTo(1.5, 4.5); g.lineTo(12, 4.5); g.moveTo(9, 1.8); g.lineTo(12, 4.5); g.lineTo(9, 7.2); g.stroke()
            g.beginPath(); g.moveTo(12.5, 9.5); g.lineTo(2, 9.5); g.moveTo(5, 6.8); g.lineTo(2, 9.5); g.lineTo(5, 12.2); g.stroke()
        }
    }
}
