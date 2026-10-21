import QtQuick
import RostrumKit

// The document's things: the scene tree (a group's or import's children indented, the arrow folds them), then
// materials, then shots. Click selects (screen state, through backend.select). A mesh row names its material at the
// right, dim; clicking that name selects the material, to edit it.
Panel {
    id: panel
    title: "Outliner"
    bodyPad: Theme.gap

    ListView {
        anchors.fill: parent
        model: backend.outline
        spacing: 2
        clip: true
        boundsBehavior: Flickable.StopAtBounds
        delegate: Item {
            id: row
            required property var modelData
            readonly property bool section: modelData.row === "section"
            readonly property bool selected: modelData.id === backend.selected
            readonly property bool inSelected: !selected && modelData.id === backend.selectedOwner   // a key of it is selected
            readonly property int indent: Theme.gap + modelData.depth * 16
            width: ListView.view.width
            height: section ? Theme.rowDense + (modelData.id === "section:scene" ? 0 : Theme.gap) : Theme.rowDense

            Text {  // a section's title
                visible: row.section
                anchors { left: parent.left; leftMargin: Theme.gap; bottom: parent.bottom; bottomMargin: 4 }
                text: row.modelData.label; color: Theme.fg3; font.family: uiFont; font.pixelSize: Theme.label
                font.weight: Font.DemiBold
            }
            Rectangle {
                visible: !row.section
                anchors.fill: parent; radius: Theme.radiusCtl
                color: row.selected ? Theme.accentSoft : hover.containsMouse || row.inSelected ? Theme.hover : "transparent"
                MouseArea { id: hover; anchors.fill: parent; hoverEnabled: true; onClicked: backend.select(row.modelData.id) }
                Item {  // the fold arrow (absent when there is nothing to fold)
                    x: row.indent - 2; width: 14; height: parent.height
                    visible: row.modelData.fold !== ""
                    Chevron { anchors.centerIn: parent; rotation: row.modelData.fold === "open" ? 0 : -90
                              color: foldArea.containsMouse ? Theme.fg : Theme.fg3 }
                    MouseArea { id: foldArea; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                                onClicked: backend.toggleFold(row.modelData.id) }
                }
                KindIcon {
                    id: icon
                    x: row.indent + 16; anchors.verticalCenter: parent.verticalCenter
                    kind: row.modelData.kind
                    ink: row.selected ? Theme.accentHover : row.modelData.row === "part" ? Theme.fg3 : Theme.fg2
                }
                Text {
                    anchors { left: icon.right; leftMargin: Theme.gap; verticalCenter: parent.verticalCenter
                              right: matName.visible ? matName.left : mark.left; rightMargin: Theme.gap }
                    text: row.modelData.label; elide: Text.ElideRight; font.family: uiFont; font.pixelSize: Theme.body
                    color: row.modelData.row === "part" && !row.selected ? Theme.fg2 : Theme.fg
                }
                Text {  // its material: click to edit it
                    id: matName
                    visible: row.modelData.material !== ""
                    anchors { right: mark.left; rightMargin: Theme.gap; verticalCenter: parent.verticalCenter }
                    text: row.modelData.material; font.family: uiFont; font.pixelSize: Theme.label
                    color: matArea.containsMouse ? Theme.fg : Theme.fg3
                    MouseArea { id: matArea; anchors.fill: parent; anchors.margins: -4; hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor; onClicked: backend.select(row.modelData.material) }
                }
                KeyMark {  // this item has keys
                    id: mark
                    anchors { right: parent.right; rightMargin: Theme.gap; verticalCenter: parent.verticalCenter }
                    visible: row.modelData.animated; size: 6; color: row.selected ? Theme.accent : Theme.fg4
                    width: visible ? implicitWidth : 0
                }
            }
        }
    }
}
