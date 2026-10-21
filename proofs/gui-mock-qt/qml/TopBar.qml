import QtQuick
import QtQuick.Layouts
import "."

// Wordmark, the open document's tab, and the command-bar button (the visible way into Ctrl+K).
Item {
    id: bar
    property var app
    signal commandClicked()
    implicitHeight: Theme.topBar

    RowLayout {
        anchors.fill: parent
        anchors.leftMargin: Theme.pad + Theme.gap; anchors.rightMargin: Theme.gap
        spacing: Theme.groupGap

        Text { text: "Rostrum"; color: Theme.fg; font.pixelSize: Theme.title; font.weight: Font.DemiBold }
        Rectangle {
            implicitHeight: 28; implicitWidth: tabLabel.implicitWidth + 2 * Theme.pad
            radius: Theme.radiusCtl; color: Theme.panel
            Text { id: tabLabel; anchors.centerIn: parent; text: "Launch film"; color: Theme.fg; font.pixelSize: Theme.body }
        }
        Item { Layout.fillWidth: true }
        Rectangle {
            implicitHeight: 28; implicitWidth: 280
            radius: Theme.radiusCtl
            color: cmdHover.containsMouse ? Theme.hover : Theme.raised
            Behavior on color { ColorAnimation { duration: Theme.fast } }
            Text {
                anchors.left: parent.left; anchors.leftMargin: Theme.pad; anchors.verticalCenter: parent.verticalCenter
                text: "Search or run a command"; color: Theme.fg3; font.pixelSize: Theme.body
            }
            Rectangle {
                anchors.right: parent.right; anchors.rightMargin: Theme.grid; anchors.verticalCenter: parent.verticalCenter
                height: 20; width: keyHint.implicitWidth + 2 * Theme.gap; radius: 4; color: Theme.active
                Text { id: keyHint; anchors.centerIn: parent; text: "Ctrl K"; color: Theme.fg2; font.pixelSize: Theme.label }
            }
            MouseArea { id: cmdHover; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: bar.commandClicked() }
        }
    }
}
