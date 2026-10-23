import QtQuick
import RostrumKit

// The take as it is being recorded, over its armed lane (recorder.take, recording.py): a red-edged block from where
// it started to the playhead, growing as it records, with the microphone's level drawn along it (as Logic and
// Ableton draw a take). It stays until the take lands as its clip. Drawing only (clicks pass through).
Item {
    id: lt
    property var take: ({})
    property var ruler
    property color hue: Theme.danger
    readonly property real x0: ruler.xOf(take.t || 0)
    readonly property real w: Math.max(2, ruler.wOf(take.dur || 0))

    Rectangle {
        x: lt.x0; y: 3; width: lt.w; height: lt.height - 6; radius: 4
        color: Qt.rgba(lt.hue.r, lt.hue.g, lt.hue.b, 0.18); border.width: 1; border.color: Theme.danger
    }
    Canvas {
        id: c
        x: lt.x0; y: 3; width: lt.w; height: lt.height - 6
        onWidthChanged: requestPaint()
        onHeightChanged: requestPaint()
        Connections { target: lt; function onTakeChanged() { c.requestPaint() } }
        onPaint: {
            var g = getContext("2d"); g.reset()
            var lv = lt.take.levels || [], bw = Math.max(1, lt.ruler.wOf(0.1) - 1)
            var top = height > 30 ? 14 : 2, ih = height - top - 2
            g.fillStyle = lt.hue; g.globalAlpha = 0.85
            for (var i = 0; i < lv.length; i++) {
                var ph = Math.max(1, ih * lv[i][1])
                g.fillRect(lt.ruler.wOf(lv[i][0]), top + (ih - ph) / 2, bw, ph)
            }
            g.globalAlpha = 1
            if (top > 2 && width > 70) {
                g.font = (Theme.label - 1) + "px '" + uiFont + "'"
                g.fillStyle = Theme.fg; g.textBaseline = "top"
                g.fillText("Recording…", 6, 2)
            }
        }
    }
}
