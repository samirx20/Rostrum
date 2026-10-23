import QtQuick
import "."

// The grey-and-white squares behind anything see-through (alpha strip, gradient bar, swatches). Rounded by `radius`.
Canvas {
    id: c
    property int radius: 3
    property int cell: 6
    onRadiusChanged: requestPaint()
    onWidthChanged: requestPaint()
    onHeightChanged: requestPaint()
    onPaint: {
        var g = getContext("2d")
        g.reset()
        g.roundedRect(0, 0, width, height, radius, radius); g.clip()
        g.fillStyle = "#d9d9d9"; g.fillRect(0, 0, width, height)
        g.fillStyle = "#9a9a9a"
        for (var y = 0; y * cell < height; y++)
            for (var x = (y % 2); x * cell < width; x += 2) g.fillRect(x * cell, y * cell, cell, cell)
    }
}
