import QtQuick
import RostrumKit

// An import just rescaled to metres (importing.py): in the settings panel, under its rows, the link "Keep original size"
// (import.keep_size, one undo step). Only for that import, only until the next edit; else absent. The unit message
// itself is said once, on the status line (the kit's status line has no place for an action yet).
Item {
    id: root
    readonly property bool applies: backend.importer.keepFor !== "" && backend.importer.keepFor === backend.selected
    readonly property int labelW: Theme.labelColumnFor(width)
    readonly property int fieldW: Theme.fieldFor(width)
    visible: applies
    width: parent ? parent.width : 0
    height: applies ? Theme.row + Theme.grid : 0

    Text { x: 0; height: Theme.row; verticalAlignment: Text.AlignVCenter; text: "Size"
           color: Theme.fg2; font.family: uiFont; font.pixelSize: Theme.body }
    Text {
        objectName: "importKeepSize"
        x: root.labelW; height: Theme.row; verticalAlignment: Text.AlignVCenter
        text: "Keep original size"
        color: keep.containsMouse ? Theme.accentHover : Theme.accent; font.family: uiFont; font.pixelSize: Theme.body
        MouseArea { id: keep; anchors.fill: parent; hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor; onClicked: backend.importer.keepSize() }
    }
}
