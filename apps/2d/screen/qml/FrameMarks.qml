import QtQuick
import RostrumKit

// Frame-by-frame on a timeline track: a mark where each drawing starts and a bar for how long it is held
// (`frames` from the layer's row: {at, t0, t1}). Sits in a track whose x is the ruler's x - 8, like the key diamonds.
// The drawing showing at the playhead is lit; `numbered` writes each drawing's frame number in its bar.
Item {
    id: m
    property var frames: []
    property var timeRuler
    property bool numbered: false
    Repeater {
        model: m.frames
        delegate: Item {
            id: f
            required property var modelData
            readonly property bool current: backend.time >= modelData.t0 - 1e-6 && backend.time < modelData.t1 - 1e-6
            x: 8 + Math.round(m.timeRuler.xOf(modelData.t0))
            width: Math.max(3, Math.round(m.timeRuler.xOf(modelData.t1) - m.timeRuler.xOf(modelData.t0)) - 1)
            height: m.height
            Rectangle {
                anchors.fill: parent; anchors.topMargin: 3; anchors.bottomMargin: 3; radius: 3
                color: f.current ? Qt.rgba(76 / 255, 141 / 255, 1, 0.34) : Theme.accentSoft
            }
            Rectangle {
                y: 2; width: 3; height: parent.height - 4; radius: 1.5
                color: f.current ? Theme.accent : Theme.fg3
            }
            Text {
                visible: m.numbered && parent.width > 22
                x: 8; anchors.verticalCenter: parent.verticalCenter
                text: f.modelData.at; color: f.current ? Theme.fg : Theme.fg2; font.family: uiFont
                font.pixelSize: Theme.label; font.features: { "tnum": 1 }
            }
        }
    }
}
