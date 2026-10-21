import QtQuick
import "."

// The six items. Click (or Up / Down) selects, through doc.select.
Panel {
    id: panel
    property var doc
    title: "Project"
    bodyPad: Theme.gap

    ListView {
        anchors.fill: parent
        model: panel.doc.itemList()
        spacing: 2
        interactive: false
        delegate: Rectangle {
            id: row
            required property var modelData
            readonly property bool selected: modelData.id === panel.doc.selected
            width: ListView.view.width; height: Theme.row
            radius: Theme.radiusCtl
            color: selected ? Theme.accentSoft : hover.containsMouse ? Theme.hover : "transparent"
            Rectangle {
                id: chip
                anchors.left: parent.left; anchors.leftMargin: Theme.gap; anchors.verticalCenter: parent.verticalCenter
                width: 20; height: 20; radius: 4
                color: row.selected ? Theme.accent : Theme.active
                Text { anchors.centerIn: parent; text: row.modelData.glyph; color: row.selected ? "white" : Theme.fg2
                       font.pixelSize: 10; font.weight: Font.DemiBold }
            }
            Text {
                anchors.left: chip.right; anchors.leftMargin: Theme.gap; anchors.verticalCenter: parent.verticalCenter
                anchors.right: kindLabel.left; anchors.rightMargin: Theme.gap
                text: row.modelData.name; color: Theme.fg; elide: Text.ElideRight; font.pixelSize: Theme.body
            }
            Text {
                id: kindLabel
                anchors.right: parent.right; anchors.rightMargin: Theme.gap; anchors.verticalCenter: parent.verticalCenter
                text: row.modelData.kind; color: Theme.fg3; font.pixelSize: Theme.label
            }
            MouseArea { id: hover; anchors.fill: parent; hoverEnabled: true; onClicked: panel.doc.select(row.modelData.id) }
        }
    }
}
