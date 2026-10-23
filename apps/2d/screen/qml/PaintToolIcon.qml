import QtQuick
import RostrumKit

// The Brush group's tool icons (paint_tool.py): brush is the kit's; eraser, fill, pick and select (a lasso) are drawn
// here in the kit's style (20 x 20 grid, 1.5 px round strokes, one ink). Only 2D paints, so they live with 2D.
Item {
    id: icon
    property string name: "brush"
    property color ink: Theme.fg2
    width: 20; height: 20
    ToolIcon { anchors.fill: parent; visible: icon.name === "brush"; name: "brush"; ink: icon.ink }
    Canvas {
        id: c
        anchors.fill: parent
        visible: icon.name !== "brush"
        Connections { target: icon; function onNameChanged() { c.requestPaint() } function onInkChanged() { c.requestPaint() } }
        onPaint: {
            const g = getContext("2d")
            g.reset()
            g.scale(width / 20, height / 20)
            g.strokeStyle = icon.ink; g.fillStyle = icon.ink; g.lineWidth = 1.5; g.lineCap = "round"; g.lineJoin = "round"
            const line = (pts) => { g.beginPath(); g.moveTo(pts[0], pts[1]); for (let i = 2; i < pts.length; i += 2) g.lineTo(pts[i], pts[i + 1]); g.stroke() }
            switch (icon.name) {
            case "eraser":      // a block on its corner, the rubbing end marked, a line under it
                g.beginPath(); g.moveTo(11, 3.5); g.lineTo(17, 9.5); g.lineTo(10, 16.5); g.lineTo(6.5, 16.5); g.lineTo(3, 13)
                g.closePath(); g.stroke(); line([7, 9.5, 13, 15.5]); line([10, 17, 17, 17]); break
            case "fill":        // a tipped bucket and a drop
                g.beginPath(); g.moveTo(9, 3.5); g.lineTo(15.5, 10); g.lineTo(10, 15.5); g.lineTo(3.5, 9); g.closePath(); g.stroke()
                line([3.5, 9, 15.5, 9.5]); g.beginPath(); g.moveTo(17, 12.5); g.bezierCurveTo(15.5, 15, 15.5, 16.5, 17, 16.5)
                g.bezierCurveTo(18.5, 16.5, 18.5, 15, 17, 12.5); g.fill(); break
            case "pick":        // an eyedropper
                line([4, 16, 11.5, 8.5]); line([9.5, 6.5, 13.5, 10.5])
                g.beginPath(); g.moveTo(12, 6); g.lineTo(14, 4); g.bezierCurveTo(15, 3, 17, 5, 16, 6); g.lineTo(14, 8); g.stroke()
                line([4, 16, 3.5, 16.5]); break
            case "select":      // a dashed lasso loop and its tail
                g.setLineDash([2.2, 2]); g.beginPath(); g.ellipse(3, 3.5, 14, 10); g.stroke(); g.setLineDash([])
                g.beginPath(); g.moveTo(7, 13); g.bezierCurveTo(5, 15, 7.5, 17, 9, 16.5); g.stroke(); break
            }
        }
    }
}
