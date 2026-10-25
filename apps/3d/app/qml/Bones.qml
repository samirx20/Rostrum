import QtQuick
import RostrumKit

// A mesh's bone chain over the viewport (screen3d/bones_qt.py has the maths): each bone a thin diamond from its head
// to its tail, posed at the playhead; the selected bone in the accent colour. While Bones places a chain, the points
// clicked so far show as dots joined by a line; Enter makes the chain, Backspace takes a point back, Esc cancels.
// Draws only: clicks go through to the viewport.
Item {
    id: bonesLayer
    readonly property var tool: viewport.bones

    Canvas {
        id: canvas
        anchors.fill: parent
        renderStrategy: Canvas.Cooperative
        onPaint: {
            var c = getContext("2d"), w = width, h = height
            c.reset()
            var ls = bonesLayer.tool.lines
            for (var i = 0; i < ls.length; i++) {
                var a = ls[i].a, b = ls[i].b
                var ax = a[0] * w, ay = a[1] * h, bx = b[0] * w, by = b[1] * h
                var dx = bx - ax, dy = by - ay, n = Math.max(1, Math.sqrt(dx * dx + dy * dy))
                var k = Math.min(6, n * 0.12), px = -dy / n * k, py = dx / n * k
                var mx = ax + dx * 0.2, my = ay + dy * 0.2
                c.strokeStyle = ls[i].hot ? Theme.accent : Theme.fg
                c.lineWidth = ls[i].hot ? 2 : 1.25
                c.beginPath(); c.moveTo(ax, ay); c.lineTo(mx + px, my + py); c.lineTo(bx, by)
                c.lineTo(mx - px, my - py); c.closePath(); c.stroke()
                c.beginPath(); c.arc(ax, ay, 3, 0, 2 * Math.PI); c.stroke()
            }
            var ds = bonesLayer.tool.dots
            c.strokeStyle = Theme.accent; c.fillStyle = Theme.accent; c.lineWidth = 1.5
            c.beginPath()
            for (var j = 0; j < ds.length; j++) {
                if (j === 0) c.moveTo(ds[j][0] * w, ds[j][1] * h); else c.lineTo(ds[j][0] * w, ds[j][1] * h)
            }
            c.stroke()
            for (var q = 0; q < ds.length; q++) {
                c.beginPath(); c.arc(ds[q][0] * w, ds[q][1] * h, 4, 0, 2 * Math.PI); c.fill()
            }
        }
        Connections { target: bonesLayer.tool; function onChanged() { canvas.requestPaint() } }
        onWidthChanged: requestPaint()
        onHeightChanged: requestPaint()
    }

    KeyShortcut { sequence: "Return"; enabled: bonesLayer.tool.on; onActivated: bonesLayer.tool.make() }
    KeyShortcut { sequence: "Enter"; enabled: bonesLayer.tool.on; onActivated: bonesLayer.tool.make() }
    KeyShortcut { sequence: "Backspace"; enabled: bonesLayer.tool.on && bonesLayer.tool.count > 0; onActivated: bonesLayer.tool.back() }
    KeyShortcut { sequence: "Escape"; enabled: bonesLayer.tool.on; onActivated: bonesLayer.tool.cancel() }
}
