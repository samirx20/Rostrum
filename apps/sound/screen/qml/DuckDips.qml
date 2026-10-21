import QtQuick
import RostrumKit

// Where a ducked track is pulled down, over its arrangement row: each dip the engine reported in the last render
// (lastRender.ducks: [start s, end s, deepest dB], every stretch below −3 dB) as a shaded wedge from the top,
// as deep as the dip (−24 dB reaches the bottom), with its depth written when there is room. The engine's own
// numbers from the render that plays, so what is drawn is what is heard. Drawing only (clicks pass through).
Item {
    id: d
    property string trackId
    property var ruler
    readonly property real floorDb: -24
    readonly property var spans: {
        var all = (backend.lastRender && backend.lastRender.ducks) || []
        for (var i = 0; i < all.length; i++)
            if (all[i].track === trackId) return all[i].spans
        return []
    }
    visible: spans.length > 0

    Repeater {
        model: d.spans
        delegate: Item {
            id: dip
            required property var modelData
            readonly property real x0: d.ruler.xOf(modelData[0])
            readonly property real w: Math.max(2, d.ruler.xOf(modelData[1]) - x0)
            readonly property real depth: Math.min(1, modelData[2] / d.floorDb) * d.height
            x: x0; width: w; height: d.height
            visible: d.ruler.visibleX(x0 + w) || d.ruler.visibleX(x0)
            Canvas {
                anchors.fill: parent
                onWidthChanged: requestPaint(); onHeightChanged: requestPaint()
                Component.onCompleted: requestPaint()
                onPaint: {
                    var c = getContext("2d"); c.reset()
                    var slope = Math.min(width / 4, 6)
                    c.beginPath(); c.moveTo(0, 0); c.lineTo(slope, dip.depth); c.lineTo(width - slope, dip.depth)
                    c.lineTo(width, 0); c.closePath()
                    c.fillStyle = "rgba(0, 0, 0, 0.32)"; c.fill()
                    c.strokeStyle = Theme.warn; c.lineWidth = 1.5; c.globalAlpha = 0.9
                    c.beginPath(); c.moveTo(0, 0); c.lineTo(slope, dip.depth); c.lineTo(width - slope, dip.depth)
                    c.lineTo(width, 0); c.stroke()
                }
            }
            Text {
                visible: dip.w > width + 8 && d.height >= 24
                anchors.horizontalCenter: parent.horizontalCenter
                y: Math.min(dip.depth + 1, d.height - height)
                text: Math.round(dip.modelData[2]) + " dB"; color: Theme.warn
                font.family: uiFont; font.pixelSize: Theme.label - 2; font.features: { "tnum": 1 }
            }
        }
    }
}
