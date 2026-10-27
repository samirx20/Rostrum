import QtQuick
import RostrumKit

// The settings panel while Edit mesh is on (SPEC §4.3; screen3d/mesh_edit_qt.py, mesh_actions.py). A shape that isn't
// an editable mesh yet: one line and Edit (one undo step). Then Points | Edges | Faces (1 2 3), what is picked
// ("1 face"), the actions that fit it (faces: Extrude, Inset, Material; edges: Bevel, Loop cut, Sharp, Not sharp; each
// runs at once), and the last action's numbers, which run it again as the same one step. Knife (Shift+K) and X-ray
// (Alt+Z) are tools of the mode; their keys show on hover (the key map, keys3d.py). Only what applies now is shown.
// Esc or Shift+Enter leaves.
Item {
    Column {
        anchors { left: parent.left; right: parent.right; top: parent.top; margins: Theme.pad }
        spacing: Theme.gap

        Text { text: "Edit mesh"; color: Theme.fg; font.family: uiFont; font.pixelSize: Theme.body; font.weight: Font.DemiBold }

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
            Row {
                spacing: Theme.grid
                Button { objectName: "meshKnife"; text: "Knife"; job: "mesh_knife"; kind: meshEdit.knifing ? "primary" : "normal"; onClicked: meshEdit.toggleKnife() }
                Button { objectName: "meshXray"; text: "X-ray"; job: "mesh_xray"; kind: meshEdit.xray ? "primary" : "normal"; onClicked: meshEdit.toggleXray() }
            }
            Text { text: meshEdit.count; color: meshEdit.picked ? Theme.fg : Theme.fg3; font.family: uiFont; font.pixelSize: Theme.body }
            Text { visible: meshEdit.picked === 0; width: parent.width; wrapMode: Text.Wrap
                   color: Theme.fg4; font.family: uiFont; font.pixelSize: Theme.label
                   text: "Click to pick · Shift-click adds · drag a box · right-drag turns the view" }
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
                    NumberField { width: 110; value: modelData.value; unit: modelData.unit; step: modelData.step
                                  from: modelData.from; to: modelData.to
                                  label: modelData.label; onEdited: (v) => meshEdit.setNumber(modelData.name, v) }
                }
            }
            Row {   // faces: the material they take (the kit's picker; a face's own material beats the shape's)
                visible: meshEdit.kind === "faces" && meshEdit.picked > 0
                spacing: Theme.grid
                Text { width: 72; text: "Material"; color: Theme.fg3; font.family: uiFont; font.pixelSize: Theme.body
                       anchors.verticalCenter: parent.verticalCenter }
                FieldFrame {
                    id: faceMaterial
                    objectName: "meshFaceMaterial"
                    width: 150; atRest: "Choose…"; engaged: facePicker.visible
                    trailing: Chevron { color: Theme.fg2 }
                    MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: facePicker.openFrom(faceMaterial) }
                }
            }
            MaterialPicker { id: facePicker; faces: true }
        }
    }
}
