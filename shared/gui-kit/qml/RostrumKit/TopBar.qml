import QtQuick
import QtQuick.Layouts
import "."

// Wordmark, the open document's tab, the history status (small), and the command-bar button.
Item {
    id: bar
    property var bridge
    property string appName: "Rostrum"
    property string documentName: ""
    signal commandClicked()
    implicitHeight: Theme.topBar

    RowLayout {
        anchors.fill: parent
        anchors.leftMargin: Theme.pad + Theme.gap; anchors.rightMargin: Theme.gap
        spacing: Theme.groupGap

        Text { text: bar.appName; color: Theme.fg; font.family: uiFont; font.pixelSize: Theme.title; font.weight: Font.DemiBold }
        Rectangle {
            visible: bar.documentName !== ""
            implicitHeight: Theme.button; implicitWidth: tabLabel.implicitWidth + 2 * Theme.pad
            radius: Theme.radiusCtl; color: Theme.panel
            Text { id: tabLabel; anchors.centerIn: parent; text: bar.documentName; color: Theme.fg; font.family: uiFont; font.pixelSize: Theme.body }
        }
        Item { Layout.fillWidth: true }
        Text {  // history: how many changes, and the last thing that happened (or what failed)
            Layout.maximumWidth: 420
            elide: Text.ElideRight
            text: bar.bridge.historyCount + (bar.bridge.historyCount === 1 ? " change" : " changes")
                  + (bar.bridge.status ? "  ·  " + bar.bridge.status : "")
            color: /^Error/.test(bar.bridge.status) ? Theme.danger : Theme.fg3
            font.family: uiFont; font.pixelSize: Theme.label
        }
        Rectangle {
            implicitHeight: Theme.button; implicitWidth: 280
            radius: Theme.radiusCtl
            color: cmdHover.containsMouse ? Theme.hover : Theme.raised
            Behavior on color { ColorAnimation { duration: Theme.fast } }
            Text {
                anchors.left: parent.left; anchors.leftMargin: Theme.pad; anchors.verticalCenter: parent.verticalCenter
                text: "Search or run a command"; color: Theme.fg3; font.family: uiFont; font.pixelSize: Theme.body
            }
            KeyHint { text: "Ctrl K"; anchors.right: parent.right; anchors.rightMargin: Theme.grid; anchors.verticalCenter: parent.verticalCenter }
            MouseArea { id: cmdHover; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: bar.commandClicked() }
        }
    }
}
