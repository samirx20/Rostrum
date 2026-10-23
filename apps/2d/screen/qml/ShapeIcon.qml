import QtQuick
import RostrumKit

// The shape kinds' icons (fields.SHAPE_KINDS, backend.create.kinds): rect and ellipse are the kit's; the others are
// drawn here in the kit's style (20 x 20 grid, 1.5 px round strokes, one ink). An unknown kind draws nothing.
Item {
    id: icon
    property string name: "rect"
    property color ink: Theme.fg2
    width: 20; height: 20
    readonly property bool kit: name === "rect" || name === "ellipse"
    ToolIcon { anchors.fill: parent; visible: icon.kit; name: icon.kit ? icon.name : ""; ink: icon.ink }
    Canvas {
        id: c
        anchors.fill: parent
        visible: !icon.kit
        Connections { target: icon; function onNameChanged() { c.requestPaint() } function onInkChanged() { c.requestPaint() } }
        onPaint: {
            const g = getContext("2d")
            g.reset()
            g.scale(width / 20, height / 20)
            g.strokeStyle = icon.ink; g.fillStyle = icon.ink; g.lineWidth = 1.5; g.lineCap = "round"; g.lineJoin = "round"
            const line = (pts) => { g.beginPath(); g.moveTo(pts[0], pts[1]); for (let i = 2; i < pts.length; i += 2) g.lineTo(pts[i], pts[i + 1]); g.stroke() }
            const closed = (pts) => { g.beginPath(); g.moveTo(pts[0], pts[1]); for (let i = 2; i < pts.length; i += 2) g.lineTo(pts[i], pts[i + 1]); g.closePath(); g.stroke() }
            const around = (n, r, inner) => {     // a polygon (inner = 0) or a star round (10, 10.5), a point up
                const pts = [], k = inner ? 2 * n : n
                for (let i = 0; i < k; i++) {
                    const a = -Math.PI / 2 + i * 2 * Math.PI / k, rr = inner && i % 2 ? inner : r
                    pts.push(10 + rr * Math.cos(a), 10.5 + rr * Math.sin(a))
                }
                closed(pts)
            }
            switch (icon.name) {
            case "arc":         // three quarters of a ring, open at the top left
                g.beginPath(); g.arc(10, 10, 6.5, -Math.PI / 2, Math.PI, false); g.stroke(); break
            case "triangle": closed([10, 3.5, 17, 16, 3, 16]); break
            case "polygon": around(6, 7, 0); break
            case "star": around(5, 7.5, 3.2); break
            case "line": line([4, 16, 16, 4]); break
            case "arrow": line([4, 16, 15.5, 4.5]); line([9.5, 4.5, 15.5, 4.5, 15.5, 10.5]); break
            case "spiral": {    // two and a half turns out from the middle
                g.beginPath()
                for (let i = 0; i <= 60; i++) {
                    const t = i / 60, a = t * 5 * Math.PI, r = 0.6 + t * 6.8
                    const x = 10 + r * Math.cos(a), y = 10 + r * Math.sin(a)
                    if (i === 0) g.moveTo(x, y); else g.lineTo(x, y)
                }
                g.stroke(); break
            }
            }
        }
    }
}
