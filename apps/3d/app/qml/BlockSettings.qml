import QtQuick
import RostrumKit

// The right panel while a material's blocks are open (BlocksPanel.qml) and a block is picked in the view: that block's
// settings (backend.blocks.rows, screen3d/blocks_qt.py), in place of the item's own (hidden meanwhile). Surface = the material's own rows (as
// under its item); any other block = its type's settings (Noise: Scale, Detail, Roughness, Distortion). A setting a wire
// feeds says so under its field. No ‹ here: the block view's own ‹ Back (and Esc) closes both.
Rectangle {
    id: panel
    objectName: "blockSettings"
    readonly property var bk: backend.blocks
    visible: bk.open && bk.selected !== "" && backend.page !== "render"
    color: Theme.panel; z: 2
    readonly property real w: width - Theme.padLeft - Theme.padRight
    MouseArea { anchors.fill: parent; acceptedButtons: Qt.AllButtons; onWheel: (e) => e.accepted = true }   // the item's settings under it stay untouched

    SheetScroll {
        Column {
            x: Theme.padLeft; y: Theme.gap; width: panel.w; spacing: 0; bottomPadding: Theme.gap
            Item {
                width: parent.width; height: Theme.row
                Text { id: word; anchors.verticalCenter: parent.verticalCenter; text: panel.bk.pickedLabel + " block"
                       color: Theme.fg; font.bold: true; font.family: uiFont; font.pixelSize: Theme.body }
                Text { anchors { left: word.right; leftMargin: Theme.gap; right: parent.right; verticalCenter: parent.verticalCenter }
                       text: panel.bk.title; elide: Text.ElideRight
                       color: Theme.fg3; font.family: uiFont; font.pixelSize: Theme.label }
            }
            Item { width: 1; height: Theme.gap }
            Repeater {
                model: panel.bk.rows
                delegate: InspectorRow { width: panel.w; bridge: panel.bk; instant: panel.bk.rows.instant }
            }
        }
    }
}
