import QtQuick
import RostrumKit

// What the settings panel shows for an item's material (SPEC 6.1; the Inspector's `below`): a "Material" label, then a
// field (ball, name, chevron) on the settings grid, so it lines up with every other row. A click on the field opens the
// MaterialPicker under it. When the material is shared: a grey "Used by N items" and a link "Make its own". An "Edit"
// link (select the material: the panel shows its settings) whenever the item has a material. The whole row is absent
// when the selection cannot hold a material. openPicker() opens the picker for the scripted layout check.
Item {
    id: root
    readonly property var cur: backend.mats.current
    readonly property bool applies: Object.keys(cur).length > 0
    readonly property bool has: applies && cur.id !== ""
    readonly property bool shared: has && cur.shared === true
    readonly property int labelW: Theme.labelColumnFor(width)
    readonly property int fieldW: Theme.fieldFor(width)
    function openPicker() { picker.openFrom(field) }
    visible: applies
    width: parent ? parent.width : 0
    height: applies ? Theme.row + Theme.grid + notes.height : 0

    Text { x: 0; y: 0; height: Theme.row; verticalAlignment: Text.AlignVCenter; text: "Material"
           color: Theme.fg2; font.family: uiFont; font.pixelSize: Theme.body }
    FieldFrame {
        id: field
        objectName: "materialField"
        x: root.labelW; y: (Theme.row - height) / 2; width: root.fieldW
        engaged: picker.visible
        atRest: root.has ? root.cur.label : "None"
        leading: Ball { size: Theme.field - 2 * Theme.grid; source: root.has ? root.cur.ball : ""
                        colour: root.has ? root.cur.colour : Theme.raised }
        trailing: Chevron { color: Theme.fg2 }
        MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: root.openPicker() }
    }
    Column {    // under the field, on its column
        id: notes
        x: root.labelW; y: Theme.row + Theme.grid; width: root.fieldW
        Text { visible: root.shared; width: parent.width; wrapMode: Text.WordWrap
               text: "Used by " + root.cur.users + " items"; color: Theme.fg3; font.family: uiFont; font.pixelSize: Theme.label }
        Row {
            spacing: Theme.gap
            visible: root.has
            height: visible ? Theme.rowDense : 0
            Text { visible: root.shared; anchors.verticalCenter: parent.verticalCenter; text: "Make its own"
                   color: own.containsMouse ? Theme.accentHover : Theme.accent; font.family: uiFont; font.pixelSize: Theme.label
                   MouseArea { id: own; anchors.fill: parent; anchors.margins: -Theme.grid; hoverEnabled: true
                               cursorShape: Qt.PointingHandCursor; onClicked: backend.mats.split() } }
            Text { anchors.verticalCenter: parent.verticalCenter; text: "Edit"
                   color: edit.containsMouse ? Theme.accentHover : Theme.accent; font.family: uiFont; font.pixelSize: Theme.label
                   MouseArea { id: edit; anchors.fill: parent; anchors.margins: -Theme.grid; hoverEnabled: true
                               cursorShape: Qt.PointingHandCursor; onClicked: backend.mats.edit(root.cur.id) } }
        }
    }
    MaterialPicker { id: picker }
}
