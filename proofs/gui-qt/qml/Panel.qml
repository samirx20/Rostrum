import QtQuick
import "."

// A rounded panel with a 32 px header. Children go into `body` (below the header, padded).
Rectangle {
    id: panel
    property string title: ""
    property alias headerRight: headerRightSlot.data
    default property alias body: content.data
    property int bodyPad: Theme.pad
    color: Theme.panel
    radius: Theme.radiusPanel
    clip: true

    Item {
        id: header
        anchors { left: parent.left; right: parent.right; top: parent.top }
        height: Theme.header
        Text {
            anchors.left: parent.left; anchors.leftMargin: Theme.pad; anchors.verticalCenter: parent.verticalCenter
            text: panel.title; color: Theme.fg2; font.pixelSize: Theme.label; font.weight: Font.DemiBold
            font.letterSpacing: 0.4; font.capitalization: Font.AllUppercase
        }
        Row {
            id: headerRightSlot
            anchors.right: parent.right; anchors.rightMargin: Theme.gap; anchors.verticalCenter: parent.verticalCenter
            spacing: Theme.grid
        }
    }
    Item {
        id: content
        anchors { left: parent.left; right: parent.right; top: header.bottom; bottom: parent.bottom
                  leftMargin: panel.bodyPad; rightMargin: panel.bodyPad; bottomMargin: panel.bodyPad }
    }
}
