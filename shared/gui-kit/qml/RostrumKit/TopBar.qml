import QtQuick
import QtQuick.Layouts
import "."

// Wordmark, the open document's tab, the app's own tools (`tools`: e.g. a page switch, centred), the history
// status (small), the app's action buttons (`actions`: e.g. Export, right side), and the command-bar button.
Item {
    id: bar
    property var bridge
    property string appName: "Rostrum"
    property string documentName: ""
    property alias tools: toolsSlot.data
    property alias actions: actionsSlot.data
    signal commandClicked()
    implicitHeight: Theme.topBar

    Row {  // the app's tools sit in the middle of the window
        id: toolsSlot
        anchors.centerIn: parent
        spacing: Theme.gap
        z: 1
    }
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
        Text {  // history: how many changes, and the last thing that happened (or what failed); never under the tools
            Layout.maximumWidth: Math.max(0, Math.min(420, bar.width / 2 - toolsSlot.width / 2 - actionsSlot.width - 280
                                                      - 3 * Theme.groupGap - Theme.gap))
            elide: Text.ElideRight
            text: bar.bridge.historyCount + (bar.bridge.historyCount === 1 ? " change" : " changes")
                  + (bar.bridge.status ? "  ·  " + bar.bridge.status : "")
            color: /^Error/.test(bar.bridge.status) ? Theme.danger : Theme.fg3
            font.family: uiFont; font.pixelSize: Theme.label
        }
        Row {  // the app's action buttons: things to do, not pages to be on
            id: actionsSlot
            spacing: Theme.gap
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
