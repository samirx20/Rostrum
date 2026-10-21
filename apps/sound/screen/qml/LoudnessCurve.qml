import QtQuick
import RostrumKit
import "MixFormat.js" as F

// The short-term loudness over the song (one value per hop) with the delivery target as a dashed line and the playhead.
// `values[k]` ends at k * hop + window seconds. `target` is a LUFS number, or null while there is no target to show.
Item {
    id: c
    property var values: []
    property real hop: 0.1
    property real window: 3
    property real seconds: 0
    property var target: null
    property real now: 0
    readonly property real span: Math.max(seconds, values.length * hop + window, 0.1)
    // the vertical range: the data and the target, a few LU of air, never less than 12 LU tall
    readonly property var range: {
        var lo = 1e9, hi = -1e9
        for (var i = 0; i < values.length; i++) if (values[i] > -100) { lo = Math.min(lo, values[i]); hi = Math.max(hi, values[i]) }
        if (target !== null) { lo = Math.min(lo, target); hi = Math.max(hi, target) }
        if (hi < lo) return [-30, -10]
        var mid = (lo + hi) / 2, half = Math.max(6, (hi - lo) / 2 + 2)
        return [mid - half, mid + half]
    }
    function yOf(v) { return height * (1 - (v - range[0]) / (range[1] - range[0])) }

    Rectangle { anchors.fill: parent; color: Theme.sunken; radius: Theme.radiusCtl }
    Canvas {
        id: cv
        anchors.fill: parent
        onPaint: {
            var ctx = getContext("2d")
            ctx.reset()
            if (c.target !== null) {
                ctx.strokeStyle = Theme.ok; ctx.lineWidth = 1; ctx.setLineDash([4, 3])
                ctx.beginPath(); ctx.moveTo(0, c.yOf(c.target)); ctx.lineTo(width, c.yOf(c.target)); ctx.stroke()
                ctx.setLineDash([])
            }
            ctx.strokeStyle = Theme.accent; ctx.lineWidth = 1.5
            ctx.beginPath()
            var pen = false
            for (var i = 0; i < c.values.length; i++) {
                if (c.values[i] <= -100) { pen = false; continue }
                var x = (i * c.hop + c.window) / c.span * width, y = c.yOf(c.values[i])
                if (pen) ctx.lineTo(x, y); else ctx.moveTo(x, y)
                pen = true
            }
            ctx.stroke()
        }
    }
    Connections {
        target: c
        function onValuesChanged() { cv.requestPaint() }
        function onTargetChanged() { cv.requestPaint() }
        function onWidthChanged() { cv.requestPaint() }
        function onHeightChanged() { cv.requestPaint() }
        function onSecondsChanged() { cv.requestPaint() }
    }
    Text {
        visible: c.target !== null
        anchors { right: parent.right; rightMargin: 4; bottom: parent.bottom; bottomMargin: 2 }
        text: "target " + F.num(c.target, 0) + " LUFS"; color: Theme.ok
        font.family: uiFont; font.pixelSize: Theme.label - 1
    }
    Rectangle {   // the playhead
        x: Math.min(c.width - 1, c.now / c.span * c.width); width: 1; height: parent.height; color: Theme.fg
        visible: c.values.length > 0
    }
}
