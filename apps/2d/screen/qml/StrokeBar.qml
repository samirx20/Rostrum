import QtQuick
import RostrumKit

// Draw's part of the context bar while strokes are picked (backend.strokeSelect, UX_SPEC 3.8 "Select and move paint"):
// what applies to them. Dragging them moves them; Delete, Copy and Paste are one change each; Esc or Done lets go.
Row {
    id: sb
    spacing: Theme.gap
    readonly property var sel: backend.strokeSelect
    Text {
        anchors.verticalCenter: parent.verticalCenter; color: Theme.fg3; font.family: uiFont; font.pixelSize: Theme.label
        text: sb.sel.count + (sb.sel.count === 1 ? " stroke" : " strokes") + "  ·  drag to move"
    }
    Button { anchors.verticalCenter: parent.verticalCenter; text: "Copy"; onClicked: sb.sel.copy() }
    Button { anchors.verticalCenter: parent.verticalCenter; visible: sb.sel.canPaste; text: "Paste"; onClicked: sb.sel.paste() }
    Button { anchors.verticalCenter: parent.verticalCenter; text: "Delete"; onClicked: sb.sel.remove() }
    Button { anchors.verticalCenter: parent.verticalCenter; text: "Done  Esc"; onClicked: sb.sel.clear() }
}
