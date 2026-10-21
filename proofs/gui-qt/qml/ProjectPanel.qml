import QtQuick
import "."

// The project: every edit, Motion piece, 3D scene, sound and comp as one list. Click (or ↑ ↓) selects.
Panel {
    id: panel
    property var app
    title: "Project"
    bodyPad: Theme.gap

    ListView {
        anchors.fill: parent
        model: panel.app.model
        spacing: 2
        interactive: false
        delegate: Rectangle {
            id: row
            required property int index
            required property string name
            required property string kind
            required property string glyph
            readonly property bool selected: index === panel.app.selectedIndex
            width: ListView.view.width; height: Theme.row
            radius: Theme.radiusCtl
            color: selected ? Theme.accentSoft : hover.containsMouse ? Theme.hover : "transparent"

            Rectangle {
                id: chip
                anchors.left: parent.left; anchors.leftMargin: Theme.gap; anchors.verticalCenter: parent.verticalCenter
                width: 20; height: 20; radius: 4
                color: row.selected ? Theme.accent : Theme.active
                Text { anchors.centerIn: parent; text: row.glyph; color: row.selected ? "white" : Theme.fg2
                       font.pixelSize: Theme.label; font.weight: Font.DemiBold }
            }
            Text {
                anchors.left: chip.right; anchors.leftMargin: Theme.gap; anchors.verticalCenter: parent.verticalCenter
                anchors.right: kindLabel.left; anchors.rightMargin: Theme.gap
                text: row.name; color: Theme.fg; elide: Text.ElideRight; font.pixelSize: Theme.body
            }
            Text {
                id: kindLabel
                anchors.right: parent.right; anchors.rightMargin: Theme.gap; anchors.verticalCenter: parent.verticalCenter
                text: row.kind; color: Theme.fg3; font.pixelSize: Theme.label
            }
            MouseArea { id: hover; anchors.fill: parent; hoverEnabled: true; onClicked: panel.app.select(row.index) }
        }
    }
}
