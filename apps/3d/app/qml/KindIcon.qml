import QtQuick
import RostrumKit

// A small drawn icon per 3D thing: mesh (a cube), group, import (a file), part, light (a bulb), camera, rig (a camera on an arc),
// material (a shaded ball), shot (a frame with a play mark).
Canvas {
    id: c
    property string kind: "mesh"
    property color ink: Theme.fg2
    width: 14; height: 14
    onKindChanged: requestPaint()
    onInkChanged: requestPaint()
    onPaint: {
        var g = getContext("2d")
        g.reset()
        g.strokeStyle = ink; g.fillStyle = ink; g.lineWidth = 1.3; g.lineJoin = "round"
        function rr(x, y, w, h, r) { g.beginPath(); g.roundedRect(x, y, w, h, r, r) }
        if (kind === "mesh") {           // a cube: front face and its top and side
            g.beginPath(); g.moveTo(2, 5); g.lineTo(5, 2); g.lineTo(12, 2); g.lineTo(12, 9); g.lineTo(9, 12)
            g.lineTo(2, 12); g.closePath(); g.moveTo(2, 5); g.lineTo(9, 5); g.lineTo(12, 2); g.moveTo(9, 5)
            g.lineTo(9, 12); g.stroke()
        } else if (kind === "group") {
            rr(1.5, 4.5, 8, 8, 1.5); g.stroke(); rr(4.5, 1.5, 8, 8, 1.5); g.stroke()
        } else if (kind === "import") {  // a page with a folded corner
            g.beginPath(); g.moveTo(3, 1.5); g.lineTo(8.5, 1.5); g.lineTo(11.5, 4.5); g.lineTo(11.5, 12.5)
            g.lineTo(3, 12.5); g.closePath(); g.moveTo(8.5, 1.5); g.lineTo(8.5, 4.5); g.lineTo(11.5, 4.5); g.stroke()
        } else if (kind === "part") {
            g.beginPath(); g.ellipse(4.5, 4.5, 5, 5); g.fill()
        } else if (kind === "light") {   // a bulb and its base
            g.beginPath(); g.ellipse(3, 1.5, 8, 8); g.stroke()
            g.beginPath(); g.moveTo(5.5, 11); g.lineTo(8.5, 11); g.moveTo(6, 13); g.lineTo(8, 13); g.stroke()
        } else if (kind === "camera") {  // a body and its lens
            rr(1.5, 4, 8, 7, 1.5); g.stroke()
            g.beginPath(); g.moveTo(9.5, 6.5); g.lineTo(12.5, 4.5); g.lineTo(12.5, 10.5); g.lineTo(9.5, 8.5); g.stroke()
        } else if (kind === "rig") {     // a small camera riding an arc
            g.beginPath(); g.arc(7, 13, 6, Math.PI * 1.1, Math.PI * 1.9); g.stroke()
            rr(4.5, 1.5, 5, 4, 1); g.fill()
        } else if (kind === "material") {  // a ball with a highlight
            g.beginPath(); g.ellipse(2, 2, 10, 10); g.stroke()
            g.beginPath(); g.ellipse(4.5, 4.5, 2.6, 2.6); g.fill()
        } else {                          // a shot: a frame with a play mark
            rr(1.5, 3, 11, 8, 1.5); g.stroke()
            g.beginPath(); g.moveTo(5.5, 5.5); g.lineTo(5.5, 8.5); g.lineTo(9, 7); g.closePath(); g.fill()
        }
    }
}
