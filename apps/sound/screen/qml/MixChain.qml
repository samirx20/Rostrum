import QtQuick
import QtQuick.Controls as QQC
import RostrumKit

// The insert chain of a track or the master: chips left to right in insert order, then "+" to add one.
// A chip selects its effect (the inspector edits it). "+" lists the effect types; picking one is effect.add.
Flickable {
    id: chain
    property var chips: []
    property string ownerId: ""
    contentHeight: flow.height; clip: true; boundsBehavior: Flickable.StopAtBounds

    Flow {
        id: flow
        width: chain.width
        spacing: Theme.grid
        Repeater {
            model: chain.chips
            delegate: MixChip {
                required property var modelData
                text: modelData.label; dim: modelData.bypass
                selected: backend.selected === modelData.id
                onClicked: backend.select(modelData.id)
            }
        }
        MixChip { id: plus; text: "+"; plus: true; onClicked: menu.open() }
    }
    QQC.Popup {
        id: menu
        parent: plus
        y: plus.height + 2
        width: 132; padding: Theme.grid
        background: Rectangle { color: Theme.raised; radius: Theme.radiusCtl; border.color: Theme.popupEdge }
        contentItem: Column {
            Repeater {
                model: mixer.effectTypes
                delegate: Rectangle {
                    required property string modelData
                    width: 124; height: Theme.popupRow; radius: 4
                    color: pick.containsMouse ? Theme.hover : "transparent"
                    Text { anchors.left: parent.left; anchors.leftMargin: Theme.gap - 2; anchors.verticalCenter: parent.verticalCenter
                           text: modelData; color: Theme.fg; font.pixelSize: Theme.body; font.family: uiFont }
                    MouseArea { id: pick; anchors.fill: parent; hoverEnabled: true
                                onClicked: { menu.close(); mixer.addEffect(chain.ownerId, modelData) } }
                }
            }
        }
    }
}
