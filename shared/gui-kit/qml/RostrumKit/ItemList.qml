import QtQuick
import "."

// The document's items. Click selects (screen state, through bridge.select).
Panel {
    id: panel
    property var bridge
    title: "Project"
    bodyPad: Theme.gap

    ListView {
        anchors.fill: parent
        model: panel.bridge.items
        spacing: 2
        clip: true
        boundsBehavior: Flickable.StopAtBounds
        delegate: Rectangle {
            id: item
            required property var modelData
            readonly property bool selected: modelData.id === panel.bridge.selected
            width: ListView.view.width; height: Theme.row
            radius: Theme.radiusCtl
            color: selected ? Theme.accentSoft : hover.containsMouse ? Theme.hover : "transparent"
            Rectangle {
                id: chip
                anchors.left: parent.left; anchors.leftMargin: Theme.gap; anchors.verticalCenter: parent.verticalCenter
                width: 20; height: 20; radius: 4
                color: item.selected ? Theme.accent : Theme.active
                Text { anchors.centerIn: parent; text: item.modelData.kind.slice(0, 2).replace(/^./, c => c.toUpperCase())
                       color: item.selected ? "white" : Theme.fg2; font.family: uiFont; font.pixelSize: 10; font.weight: Font.DemiBold }
            }
            Text {
                anchors.left: chip.right; anchors.leftMargin: Theme.gap; anchors.verticalCenter: parent.verticalCenter
                anchors.right: kindLabel.left; anchors.rightMargin: Theme.gap
                text: item.modelData.label; color: Theme.fg; elide: Text.ElideRight; font.family: uiFont; font.pixelSize: Theme.body
            }
            Text {
                id: kindLabel
                anchors.right: parent.right; anchors.rightMargin: Theme.gap; anchors.verticalCenter: parent.verticalCenter
                text: Theme.sentence(item.modelData.kind); color: Theme.fg3; font.family: uiFont; font.pixelSize: Theme.label
            }
            MouseArea { id: hover; anchors.fill: parent; hoverEnabled: true; onClicked: panel.bridge.select(item.modelData.id) }
        }
    }
}
