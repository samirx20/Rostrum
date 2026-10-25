import QtQuick
import QtQuick.Controls as QQC
import RostrumKit

// A small button that lists choices when pressed: `choices` is [{id, label}]; picking one is picked(id).
MixChip {
    id: pick
    property var choices: []
    property int popupWidth: 132         // wider for choices with a second line of detail
    signal picked(string id)
    onClicked: menu.open()
    SmallPopup {
        id: menu
        parent: pick
        y: pick.height + 2
        width: pick.popupWidth; padding: Theme.grid
        background: Rectangle { color: Theme.raised; radius: Theme.radiusCtl; border.color: Theme.popupEdge }
        contentItem: Column {
            Repeater {
                model: pick.choices
                delegate: Rectangle {
                    required property var modelData
                    width: pick.popupWidth - 2 * Theme.grid; height: Theme.popupRow; radius: 4
                    color: row.containsMouse ? Theme.hover : "transparent"
                    Text { anchors.left: parent.left; anchors.leftMargin: Theme.gap - 2; anchors.verticalCenter: parent.verticalCenter
                           text: modelData.label; color: Theme.fg; font.pixelSize: Theme.body; font.family: uiFont }
                    MouseArea { id: row; anchors.fill: parent; hoverEnabled: true
                                onClicked: { menu.close(); pick.picked(modelData.id) } }
                }
            }
        }
    }
}
