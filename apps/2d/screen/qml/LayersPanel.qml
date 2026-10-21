import QtQuick
import RostrumKit

// The composition's layers, top of the stack first. A layer's effects and masks sit under it, then a group's
// own layers; the arrow folds them. Click selects (screen state, through backend.select).
Panel {
    id: panel
    title: "Layers"
    bodyPad: Theme.gap

    ListView {
        anchors.fill: parent
        model: backend.layers
        spacing: 2
        clip: true
        boundsBehavior: Flickable.StopAtBounds
        delegate: Rectangle {
            id: row
            required property var modelData
            readonly property bool selected: modelData.id === backend.selected
            readonly property bool inSelected: !selected && modelData.id === backend.selectedLayer   // a key of it is selected
            readonly property int indent: Theme.gap + modelData.depth * 16
            width: ListView.view.width; height: modelData.owned ? Theme.rowDense : Theme.row
            radius: Theme.radiusCtl
            color: selected ? Theme.accentSoft : hover.containsMouse || inSelected ? Theme.hover : "transparent"

            MouseArea { id: hover; anchors.fill: parent; hoverEnabled: true; onClicked: backend.select(row.modelData.id) }
            Item {  // the fold arrow (absent when there is nothing to fold)
                id: fold
                x: row.indent - 2; width: 14; height: parent.height
                visible: row.modelData.fold !== ""
                Chevron { anchors.centerIn: parent; rotation: row.modelData.fold === "open" ? 0 : -90
                          color: foldArea.containsMouse ? Theme.fg : Theme.fg3 }
                MouseArea { id: foldArea; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                            onClicked: backend.toggleFold(row.modelData.id) }
            }
            LayerIcon {
                id: icon
                x: row.indent + 16; anchors.verticalCenter: parent.verticalCenter
                kind: row.modelData.kind; shape: row.modelData.shape
                ink: row.selected ? Theme.accentHover : row.modelData.owned ? Theme.fg3 : Theme.fg2
            }
            Text {
                anchors.left: icon.right; anchors.leftMargin: Theme.gap; anchors.verticalCenter: parent.verticalCenter
                anchors.right: mark.left; anchors.rightMargin: Theme.gap
                text: row.modelData.label; elide: Text.ElideRight; font.family: uiFont
                font.pixelSize: row.modelData.owned ? Theme.label + 1 : Theme.body
                color: row.modelData.owned && !row.selected ? Theme.fg2 : Theme.fg
            }
            KeyMark {  // this item has keys
                id: mark
                anchors.right: parent.right; anchors.rightMargin: Theme.gap; anchors.verticalCenter: parent.verticalCenter
                visible: row.modelData.animated; size: 6; color: row.selected ? Theme.accent : Theme.fg4
            }
        }
    }
}
