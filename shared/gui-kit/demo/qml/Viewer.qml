import QtQuick
import RostrumKit

// Stand-in for an app's viewer (Hydra, the 2D renderer, video): a dark well with the selection's name.
Panel {
    title: "Viewer"
    Rectangle {
        anchors.fill: parent; color: Theme.sunken; radius: Theme.radiusCtl
        Column {
            anchors.centerIn: parent; spacing: Theme.grid
            Text { anchors.horizontalCenter: parent.horizontalCenter; text: backend.selectedItem.label
                   color: Theme.fg3; font.family: uiFont; font.pixelSize: 20; font.weight: Font.DemiBold }
            Text { anchors.horizontalCenter: parent.horizontalCenter; text: backend.selectedItem.kind
                   color: Theme.fg4; font.family: uiFont; font.pixelSize: Theme.body; font.capitalization: Font.Capitalize }
        }
    }
}
