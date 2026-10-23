import QtQuick
import "."

// The kit's one set of tool icons: clean line drawings on a 20 x 20 grid, 1.5 px strokes, round ends, one ink.
// Every app's tool rail and flyouts use these by `name` (2D's rail; Sound can reuse them). An unknown name draws
// nothing, so a missing icon shows up at once.
// select, rect, ellipse, pen, text, brush, picture, video, render3d, import, library, sound, camera, hand, zoom, bone
Canvas {
    id: c
    property string name: ""
    property color ink: Theme.fg2
    width: 20; height: 20
    onNameChanged: requestPaint()
    onInkChanged: requestPaint()
    onPaint: {
        const g = getContext("2d")
        g.reset()
        g.scale(width / 20, height / 20)
        g.strokeStyle = ink; g.fillStyle = ink; g.lineWidth = 1.5; g.lineCap = "round"; g.lineJoin = "round"
        const line = (pts) => { g.beginPath(); g.moveTo(pts[0], pts[1]); for (let i = 2; i < pts.length; i += 2) g.lineTo(pts[i], pts[i + 1]); g.stroke() }
        const box = (x, y, w, h, r) => { g.beginPath(); g.roundedRect(x, y, w, h, r, r); g.stroke() }
        const ring = (x, y, r) => { g.beginPath(); g.ellipse(x - r, y - r, 2 * r, 2 * r); g.stroke() }
        const dot = (x, y, r) => { g.beginPath(); g.ellipse(x - r, y - r, 2 * r, 2 * r); g.fill() }
        switch (name) {
        case "select":       // the arrow pointer
            g.beginPath(); g.moveTo(5, 3); g.lineTo(5, 16); g.lineTo(8.5, 12.5); g.lineTo(11, 17.5); g.lineTo(13, 16.5)
            g.lineTo(10.5, 11.5); g.lineTo(15, 11.5); g.closePath(); g.stroke(); break
        case "rect": box(3.5, 4.5, 13, 11, 2); break
        case "ellipse": g.beginPath(); g.ellipse(3, 4, 14, 12); g.stroke(); break
        case "pen":          // a pen nib over its point
            g.beginPath(); g.moveTo(10, 3); g.lineTo(15.5, 10); g.lineTo(12.5, 16); g.lineTo(7.5, 16); g.lineTo(4.5, 10); g.closePath(); g.stroke()
            line([10, 3, 10, 10]); ring(10, 11, 1.2); line([7.5, 18, 12.5, 18]); break
        case "text": line([4.5, 4.5, 15.5, 4.5]); line([10, 4.5, 10, 16]); line([7.5, 16, 12.5, 16]); break
        case "brush":        // a round brush, its handle up to the right
            line([16.5, 3.5, 9.5, 10.5])
            g.beginPath(); g.moveTo(9.5, 10.5); g.bezierCurveTo(6.5, 10, 5, 12.5, 5, 14.5); g.bezierCurveTo(5, 16, 4, 16.5, 3, 17)
            g.bezierCurveTo(7, 17.5, 10.5, 16, 10, 12.5); g.closePath(); g.stroke(); break
        case "picture":
            box(2.5, 4, 15, 12, 2); line([4.5, 14, 8.5, 9.5, 11.5, 12.5, 13.5, 10.5, 15.5, 13]); dot(13, 7.5, 1.2); break
        case "video":
            box(2.5, 5, 11, 10, 2); g.beginPath(); g.moveTo(13.5, 9); g.lineTo(17.5, 6.5); g.lineTo(17.5, 13.5); g.lineTo(13.5, 11); g.stroke(); break
        case "render3d":     // a cube
            g.beginPath(); g.moveTo(10, 2.5); g.lineTo(16.5, 6); g.lineTo(16.5, 14); g.lineTo(10, 17.5); g.lineTo(3.5, 14); g.lineTo(3.5, 6)
            g.closePath(); g.stroke(); line([3.5, 6, 10, 9.5, 16.5, 6]); line([10, 9.5, 10, 17.5]); break
        case "import":       // an arrow down into a tray
            line([10, 3, 10, 12]); line([6.5, 8.5, 10, 12, 13.5, 8.5]); line([3.5, 12.5, 3.5, 16.5, 16.5, 16.5, 16.5, 12.5]); break
        case "library":      // three books on a shelf
            box(3.5, 4, 3.5, 12.5, 0.8); box(8.5, 4, 3.5, 12.5, 0.8); line([13.5, 5, 16.8, 15.8]); line([13.5, 5, 13.5, 16.5]); break
        case "sound":        // a speaker with two waves
            g.beginPath(); g.moveTo(3, 8); g.lineTo(6, 8); g.lineTo(10, 4.5); g.lineTo(10, 15.5); g.lineTo(6, 12); g.lineTo(3, 12)
            g.closePath(); g.stroke()
            g.beginPath(); g.arc(10, 10, 3.5, -0.3 * Math.PI, 0.3 * Math.PI); g.stroke()
            g.beginPath(); g.arc(10, 10, 6.5, -0.3 * Math.PI, 0.3 * Math.PI); g.stroke(); break
        case "camera":       // a film camera body and its lens
            box(2.5, 6, 11, 9, 2); g.beginPath(); g.moveTo(13.5, 9); g.lineTo(17.5, 7); g.lineTo(17.5, 14); g.lineTo(13.5, 12); g.stroke()
            ring(6, 4, 1.8); ring(10.5, 4, 1.8); break
        case "hand":         // an open hand
            g.beginPath(); g.moveTo(6, 11); g.lineTo(6, 5.5); g.quadraticCurveTo(6, 4, 7.25, 4); g.quadraticCurveTo(8.5, 4, 8.5, 5.5)
            g.lineTo(8.5, 9.5); g.lineTo(8.5, 3.8); g.quadraticCurveTo(8.5, 2.5, 9.75, 2.5); g.quadraticCurveTo(11, 2.5, 11, 3.8)
            g.lineTo(11, 9.5); g.lineTo(11, 4.5); g.quadraticCurveTo(11, 3.2, 12.25, 3.2); g.quadraticCurveTo(13.5, 3.2, 13.5, 4.5)
            g.lineTo(13.5, 10); g.lineTo(13.5, 7); g.quadraticCurveTo(13.5, 5.8, 14.75, 5.8); g.quadraticCurveTo(16, 5.8, 16, 7)
            g.lineTo(16, 12); g.quadraticCurveTo(16, 17.5, 11, 17.5); g.quadraticCurveTo(8, 17.5, 6.5, 15.5); g.lineTo(3.8, 12)
            g.quadraticCurveTo(3, 10.8, 4.2, 10.3); g.quadraticCurveTo(5.2, 10, 6, 11); g.stroke(); break
        case "zoom": ring(8.5, 8.5, 5); line([12.2, 12.2, 16.5, 16.5]); line([6.5, 8.5, 10.5, 8.5]); line([8.5, 6.5, 8.5, 10.5]); break
        case "bone": line([6, 14, 14, 6]); ring(4.8, 15.2, 2); ring(15.2, 4.8, 2); break
        }
    }
}
