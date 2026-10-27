import QtQuick
import RostrumKit

// An import just rescaled to metres (importing.py): in the settings panel, under its rows, the unit message and a link
// "Keep original size" (import.keep_size, one undo step). Only for that import, only until the next edit; else absent.
// (The status line says the message once too; the kit's status line has no place for an action yet.)
Item {
    id: root
    readonly property bool applies: backend.importer.keepFor !== "" && backend.importer.keepFor === backend.selected
    readonly property int labelW: Theme.labelColumnFor(width)
    readonly property int fieldW: Theme.fieldFor(width)
    visible: applies
    width: parent ? parent.width : 0
    height: applies ? Math.max(Theme.row, notes.height) + Theme.grid : 0

    Text { x: 0; height: Theme.row; verticalAlignment: Text.AlignVCenter; text: "Size"
           color: Theme.fg2; font.family: uiFont; font.pixelSize: Theme.body }
    Column {
        id: notes
        x: root.labelW; width: root.fieldW
        topPadding: (Theme.row - note.implicitHeight) / 2 > 0 && note.lineCount === 1 ? (Theme.row - note.implicitHeight) / 2 : 0
        Text { id: note; width: parent.width; wrapMode: Text.WordWrap; text: backend.importer.keepNote
               color: Theme.fg3; font.family: uiFont; font.pixelSize: Theme.label }
        Text {
            objectName: "importKeepSize"
            height: Theme.rowDense; verticalAlignment: Text.AlignVCenter
            text: "Keep original size"
            color: keep.containsMouse ? Theme.accentHover : Theme.accent; font.family: uiFont; font.pixelSize: Theme.label
            MouseArea { id: keep; anchors.fill: parent; anchors.margins: -Theme.grid; hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor; onClicked: backend.importer.keepSize() }
        }
    }
}
