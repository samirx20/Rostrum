import QtQuick
import RostrumKit

// Where you are while a painting is open on its own (mock-4): "Autumn menu › Paper grain" at the canvas's top-left.
// The scene's name goes back to the scene (as Esc does); the painting's name is where you are. Above the canvas's
// mouse area.
Rectangle {
    id: chip
    readonly property var info: backend.opened.info
    width: row.width + 2 * Theme.gap; height: Theme.row
    radius: Theme.radiusCtl; color: Theme.raised
    Row {
        id: row
        x: Theme.gap; height: parent.height; spacing: Theme.grid
        Text { objectName: "pathScene"; height: parent.height; verticalAlignment: Text.AlignVCenter
               text: chip.info.scene || ""; color: back.containsMouse ? Theme.fg : Theme.fg2
               font.family: uiFont; font.pixelSize: Theme.body
               MouseArea { id: back; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                           onClicked: backend.opened.close() }
               HoverTip { hovered: back.containsMouse; text: "Back to the scene"; key: "Esc" } }
        Text { height: parent.height; verticalAlignment: Text.AlignVCenter; text: "›"; color: Theme.fg3
               font.family: uiFont; font.pixelSize: Theme.body }
        Text { height: parent.height; verticalAlignment: Text.AlignVCenter; text: chip.info.name || ""; color: Theme.fg
               font.family: uiFont; font.pixelSize: Theme.body; elide: Text.ElideRight
               width: Math.min(implicitWidth, 320) }
    }
}
