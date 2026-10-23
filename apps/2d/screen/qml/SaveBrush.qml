import QtQuick
import RostrumKit

// "+ Save this brush" (painting design §2.1 step 6): a click opens the name field in place, holding the brush's
// name, all selected; Enter keeps the brush in My brushes (painter.saveBrush), Esc or a click elsewhere leaves it.
// Only there while the document is in a project (where saved brushes are kept).
Item {
    id: sb
    property bool naming: false
    property int align: Text.AlignRight
    signal saved()
    visible: painter.canSave
    implicitWidth: link.implicitWidth + 8; implicitHeight: Theme.rowDense
    Text {
        id: link
        objectName: "saveBrush"
        visible: !sb.naming
        anchors { verticalCenter: parent.verticalCenter; right: sb.align === Text.AlignRight ? parent.right : undefined
                  left: sb.align === Text.AlignRight ? undefined : parent.left; leftMargin: 4; rightMargin: 4 }
        text: "+ Save this brush"; color: linkArea.containsMouse ? Theme.fg : Theme.fg2
        font.family: uiFont; font.pixelSize: Theme.label
        MouseArea { id: linkArea; anchors.fill: parent; anchors.margins: -4; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                    onClicked: { nameEdit.text = painter.brushNow.name; sb.naming = true; nameEdit.forceActiveFocus(); nameEdit.selectAll() } }
    }
    Rectangle {
        visible: sb.naming
        anchors.fill: parent; radius: Theme.radiusCtl; color: Theme.sunken; border.color: Theme.accent
        TextInput {
            id: nameEdit
            objectName: "saveBrushName"
            anchors { fill: parent; leftMargin: 6; rightMargin: 6 }
            verticalAlignment: TextInput.AlignVCenter; clip: true
            color: Theme.fg; selectionColor: Theme.accent; font.pixelSize: Theme.body; font.family: uiFont
            onAccepted: { sb.naming = false; if (text.trim() && painter.saveBrush(text.trim())) sb.saved() }
            Keys.onEscapePressed: sb.naming = false
            onActiveFocusChanged: if (!activeFocus) sb.naming = false
        }
    }
}
