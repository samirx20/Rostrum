import QtQuick
import RostrumKit

// Draw's part of the context bar while strokes are picked (backend.strokeSelect, UX_SPEC 3.8 "Select and move paint"):
// what applies to them. Dragging them moves them, their box's corners scale and its knob turns them; Delete, Copy and Paste are one change each; Esc or a click on empty canvas lets go.
Row {
    id: sb
    spacing: Theme.gap
    readonly property var sel: backend.strokeSelect
    Text {
        anchors.verticalCenter: parent.verticalCenter; color: Theme.fg3; font.family: uiFont; font.pixelSize: Theme.label
        text: sb.sel.count + (sb.sel.count === 1 ? " stroke" : " strokes")      // drag / corners / knob: the canvas shows them, no words over it
    }
    Button { anchors.verticalCenter: parent.verticalCenter; text: "Copy"; onClicked: sb.sel.copy() }
    Button { anchors.verticalCenter: parent.verticalCenter; enabled: sb.sel.canPaste; opacity: enabled ? 1 : 0.4; text: "Paste"; onClicked: sb.sel.paste() }   // always there, dimmed until something is copied: the bar is centred, so a Paste appearing moved Copy under the pointer
    Button { anchors.verticalCenter: parent.verticalCenter; text: "Delete"; onClicked: sb.sel.remove() }
}
