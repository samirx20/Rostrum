import QtQuick
import RostrumKit

// The playhead as text, one format: seconds ("1.20 s"), digits all one width. The frame number and the scene's length
// are on hover.
Item {
    implicitWidth: label.implicitWidth; implicitHeight: label.implicitHeight
    Text { id: label; text: backend.time.toFixed(2) + " s"; color: Theme.fg; font.family: uiFont; font.pixelSize: Theme.body
           font.features: { "tnum": 1 } }
    HoverHandler { id: hov }
    HoverTip { hovered: hov.hovered
               text: "Frame " + Math.round(backend.time * backend.frameInfo.fps) + " · scene "
                     + (backend.frameInfo.duration || 0).toFixed(2) + " s" }
}
