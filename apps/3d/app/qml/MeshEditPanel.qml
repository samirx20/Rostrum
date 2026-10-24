import QtQuick
import RostrumKit

// The settings panel while Edit mesh is on (SPEC §4.3; screen3d/mesh_edit_qt.py, mesh_actions.py). A shape that isn't
// an editable mesh yet: one line and Edit (one undo step). Then Points | Edges | Faces (1 2 3), what is picked
// ("1 face"), the actions that fit it (faces: Extrude, Inset; each runs at once), and the last action's numbers, which
// run it again as the same one step. Only what applies now is shown. Tab or Esc leaves.
Item {
    Column {
        anchors { left: parent.left; right: parent.right; top: parent.top; margins: Theme.pad }
        spacing: Theme.gap

        Row {   // what this is, and how to leave
            width: parent.width; spacing: Theme.grid
            Text { text: "Edit mesh"; color: Theme.fg; font.family: uiFont; font.pixelSize: Theme.body; font.weight: Font.DemiBold
                   anchors.verticalCenter: parent.verticalCenter }
            Text { text: "Tab to leave"; color: Theme.fg4; font.family: uiFont; font.pixelSize: Theme.label
                   anchors.verticalCenter: parent.verticalCenter }
        }

        Column {   // not an editable mesh yet
            visible: meshEdit.needsEdit
            width: parent.width; spacing: Theme.gap
            Text { width: parent.width; wrapMode: Text.Wrap; color: Theme.fg2; font.family: uiFont; font.pixelSize: Theme.body
                   text: "Turns the " + meshEdit.shapeWord + " into an editable mesh" }
            Button { objectName: "meshEditConvert"; text: "Edit"; kind: "primary"; onClicked: meshEdit.convert() }
        }

        Column {
            visible: !meshEdit.needsEdit
            width: parent.width; spacing: Theme.gap
            Segmented {
                options: [{ value: "points", label: "Points  1" }, { value: "edges", label: "Edges  2" }, { value: "faces", label: "Faces  3" }]
                current: meshEdit.kind
                onPicked: (v) => meshEdit.setKind(v)
            }
            Text { text: meshEdit.count; color: meshEdit.picked ? Theme.fg : Theme.fg3; font.family: uiFont; font.pixelSize: Theme.body }
            Text { visible: meshEdit.picked === 0; width: parent.width; wrapMode: Text.Wrap
                   color: Theme.fg4; font.family: uiFont; font.pixelSize: Theme.label
                   text: "Click to pick · Shift-click adds · drag a box · middle-drag orbits" }
            Flow {
                visible: meshEdit.actions.length > 0
                width: parent.width; spacing: Theme.grid
                Repeater {
                    model: meshEdit.actions
                    delegate: Button { text: modelData.label; kind: meshEdit.lastAction === modelData.label ? "primary" : "normal"
                                       onClicked: meshEdit.runAction(modelData.id) }
                }
            }
            Repeater {   // the last action's numbers: typing one runs it again (still one undo step)
                model: meshEdit.numbers
                delegate: Row {
                    spacing: Theme.grid
                    Text { width: 72; text: modelData.label; color: Theme.fg3; font.family: uiFont; font.pixelSize: Theme.body
                           anchors.verticalCenter: parent.verticalCenter }
                    NumberField { width: 110; value: modelData.value; unit: "mm"; step: 0.1; from: modelData.name === "depth" ? -1000 : 0; to: 1000
                                  label: modelData.label; onEdited: (v) => meshEdit.setNumber(modelData.name, v) }
                }
            }
        }
    }
}
