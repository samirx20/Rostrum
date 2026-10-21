import QtQuick
import "."

// A swatch and its hex value.
Row {
    id: f
    property string hex: "#ffffff"
    spacing: Theme.gap
    Rectangle { width: 24; height: 24; radius: Theme.radiusCtl; color: f.hex; border.width: 1; border.color: Qt.rgba(1, 1, 1, 0.18) }
    Rectangle {
        width: 80; height: 24; radius: Theme.radiusCtl; color: Theme.raised
        Text { anchors.centerIn: parent; text: f.hex.toUpperCase(); color: Theme.fg; font.pixelSize: Theme.body; font.family: monoFont }
    }
}
