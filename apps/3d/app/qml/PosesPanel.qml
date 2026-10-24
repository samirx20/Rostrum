import QtQuick
import RostrumKit

// The Poses flyout (SPEC §9, Animate rail › Poses, P): Save pose (a name, from the selection), then the saved poses.
// Click one = keys at the playhead for every setting it holds; Shift+click = a breakdown, halfway between the
// neighbouring keys. × deletes a pose (its keys stay). backend.poses (poses_qt.py) runs the operations agents use.
Popover {
    id: pop
    objectName: "posesPanel"
    title: "Poses"
    focusItem: nameField
    width: 248
    onAccepted: if (backend.poses.canSave) { backend.poses.save(nameField.input.text); nameField.input.text = "" }

    Row {   // Save pose: shown only with something selected (rule of individuality)
        visible: backend.poses.canSave
        spacing: Theme.gap
        width: pop.availableWidth
        TextField { id: nameField; objectName: "poseName"; width: parent.width - saveButton.width - Theme.gap
                    placeholder: "Pose " + (backend.poses.saved.length + 1) }
        Button { id: saveButton; objectName: "poseSave"; text: "Save pose"; kind: "primary"
                 help: "The selected items' position, turn and scale at the playhead"
                 onClicked: { backend.poses.save(nameField.input.text); nameField.input.text = "" } }
    }
    Column {
        width: pop.availableWidth
        Repeater {
            model: backend.poses.saved
            delegate: Rectangle {
                id: row
                required property var modelData
                objectName: "pose_" + modelData.id
                width: parent.width; height: Theme.rowDense; radius: Theme.radiusCtl
                color: hover.hovered ? Theme.hover : "transparent"
                HoverHandler { id: hover; cursorShape: Qt.PointingHandCursor }
                Text { anchors { left: parent.left; leftMargin: Theme.gap; right: del.left; verticalCenter: parent.verticalCenter }
                       text: row.modelData.name; color: Theme.fg; font.family: uiFont; font.pixelSize: Theme.body; elide: Text.ElideRight }
                MouseArea {
                    anchors.fill: parent
                    onClicked: (m) => backend.poses.apply(row.modelData.id, (m.modifiers & Qt.ShiftModifier) !== 0)
                }
                HoverTip { x: row.width + 6; y: 0; text: row.modelData.name; help: row.modelData.holds + "  ·  Shift+click: breakdown"
                           hovered: hover.hovered }
                IconButton { id: del; anchors { right: parent.right; verticalCenter: parent.verticalCenter }
                             width: Theme.rowDense; height: Theme.rowDense; kind: "ghost"; glyph: "×"; tip: "Delete pose"
                             visible: hover.hovered; onClicked: backend.poses.remove(row.modelData.id) }
            }
        }
    }
    Text {   // nothing saved yet and nothing selected: say how to start
        visible: !backend.poses.canSave && backend.poses.saved.length === 0
        text: "Select items to save their pose."
        color: Theme.fg3; font.family: uiFont; font.pixelSize: Theme.body
    }
}
