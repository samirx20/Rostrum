import QtQuick
import RostrumKit

// The playhead as text: seconds and frame ("1.20 s  ·  36"), digits all one width.
Row {
    spacing: Theme.gap
    readonly property real fps: backend.frameInfo.fps
    Text { text: backend.time.toFixed(2) + " s"; color: Theme.fg; font.family: uiFont; font.pixelSize: Theme.body
           font.features: { "tnum": 1 }; anchors.verticalCenter: parent.verticalCenter }
    Text { text: "frame " + Math.round(backend.time * parent.fps); color: Theme.fg3; font.family: uiFont
           font.pixelSize: Theme.label; font.features: { "tnum": 1 }; anchors.verticalCenter: parent.verticalCenter }
}
