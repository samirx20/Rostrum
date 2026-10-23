import QtQuick
import "."

// The grey-and-white squares behind anything see-through (alpha strip, gradient bar, swatches). Rounded by `radius`.
// `light` / `dark`: the two squares (a paint layer's thumbnail uses two mid greys, so white and black ink both read).
Canvas {
    id: c
    property int radius: 3
    property int cell: 6
    property color light: "#d9d9d9"
    property color dark: "#9a9a9a"
    onLightChanged: requestPaint()
    onDarkChanged: requestPaint()
    onRadiusChanged: requestPaint()
    onWidthChanged: requestPaint()
    onHeightChanged: requestPaint()
    onPaint: {
        var g = getContext("2d")
        g.reset()
        g.roundedRect(0, 0, width, height, radius, radius); g.clip()
        g.fillStyle = c.light; g.fillRect(0, 0, width, height)
        g.fillStyle = c.dark
        for (var y = 0; y * cell < height; y++)
            for (var x = (y % 2); x * cell < width; x += 2) g.fillRect(x * cell, y * cell, cell, cell)
    }
}
