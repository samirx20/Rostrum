import QtQuick
import "."

// Animation layers in the timeline's play cell (TIMELINE.md › Animation layers): a stack of moves over the Base, each
// with a weight (a breath over a walk). One small ⧉ button, lit while a layer takes the new keys (its tip names it).
// It opens a popover: the layers top first, the Base at the bottom, + New layer. A row: click picks it (new keys go
// there; the rows show its keys only), double-click the name renames, the switch turns it on / off, Add | Replace,
// the weight slider (one drag = one change; a faded layer's slider keys the weight at the playhead), ⋯ for Key weight
// here, Move up / down and Delete. `model`: the app's rostrum_gui/anim_layers.py (backend.animLayers).
Item {
    id: root
    property var model: backend.animLayers
    implicitWidth: 24
    implicitHeight: 24

    IconButton {     // one small button whatever the state: the play cell is narrow (Keys | Curves sits after it)
        id: make
        objectName: "animLayersButton"
        glyph: "⧉"; kind: "ghost"; implicitWidth: 24; implicitHeight: 24
        down: root.model.active !== ""          // lit while a layer takes the new keys
        tip: root.model.active === "" ? "Animation layers" : "Animation layers · keys go on " + root.model.activeName
        help: root.model.count === 0 ? "Lay a move over the animation (a breath over a walk), with a weight"
                                     : "New keys go on the chosen layer; the rows show its keys"
        onClicked: pop.openAt(root)
    }

    Popover {
        id: pop
        objectName: "animLayersPopover"
        title: "Animation layers"
        Column {
            width: 300; spacing: Theme.grid
            Repeater {
                model: root.model.rows
                delegate: Rectangle {
                    id: row
                    required property var modelData
                    required property int index
                    objectName: "animLayerRow_" + modelData.id
                    width: 300; height: 2 * Theme.rowDense + Theme.grid; radius: Theme.radiusCtl
                    color: modelData.active ? Theme.active : pick.containsMouse ? Theme.hover : "transparent"
                    MouseArea { id: pick; anchors.fill: parent; hoverEnabled: true; onClicked: root.model.pick(row.modelData.id) }
                    Item {     // the name (double-click renames), on / off, ⋯
                        x: Theme.gap; width: parent.width - 2 * Theme.gap; height: Theme.rowDense
                        Text {
                            id: nameText
                            objectName: "animLayerName_" + row.modelData.id
                            visible: !nameBox.visible
                            anchors.verticalCenter: parent.verticalCenter
                            width: parent.width - onSwitch.width - more.width - 2 * Theme.gap; elide: Text.ElideRight
                            text: row.modelData.name; color: row.modelData.on ? Theme.fg : Theme.fg3
                            font.family: uiFont; font.pixelSize: Theme.body; font.weight: row.modelData.active ? Font.DemiBold : Font.Normal
                            MouseArea { anchors.fill: parent; onClicked: root.model.pick(row.modelData.id)
                                        onDoubleClicked: nameBox.visible = true }
                        }
                        NameBox {
                            id: nameBox
                            objectName: "animLayerNameBox_" + row.modelData.id
                            visible: false; current: row.modelData.name
                            anchors.verticalCenter: parent.verticalCenter; width: nameText.width
                            onDone: (t) => { visible = false; root.model.rename(row.modelData.id, t) }
                            onCancelled: visible = false
                        }
                        Toggle {
                            id: onSwitch
                            objectName: "animLayerOn_" + row.modelData.id
                            anchors { right: more.left; rightMargin: Theme.gap; verticalCenter: parent.verticalCenter }
                            checked: row.modelData.on
                            onToggled: (v) => root.model.setOn(row.modelData.id, v)
                        }
                        IconButton {
                            id: more
                            objectName: "animLayerMore_" + row.modelData.id
                            anchors { right: parent.right; verticalCenter: parent.verticalCenter }
                            glyph: "⋯"; kind: "ghost"; implicitWidth: 24; implicitHeight: 24; tip: "More"
                            onClicked: { moreMenu.entries = [
                                    { value: "key", label: "Key the weight here" },
                                    ...(row.index > 0 ? [{ value: "up", label: "Move up" }] : []),
                                    ...(row.index < root.model.count - 1 ? [{ value: "down", label: "Move down" }] : []),
                                    { value: "delete", label: "Delete layer and its keys" }]
                                moreMenu.open() }
                            Menu {
                                id: moreMenu
                                objectName: "animLayerMenu_" + row.modelData.id
                                y: parent.height
                                onPicked: (v) => v === "key" ? root.model.keyWeight(row.modelData.id)
                                               : v === "up" ? root.model.move(row.modelData.id, 1)
                                               : v === "down" ? root.model.move(row.modelData.id, -1)
                                               : root.model.remove(row.modelData.id)
                            }
                        }
                    }
                    Item {     // Add | Replace, the weight
                        x: Theme.gap; y: Theme.rowDense + Theme.grid; width: parent.width - 2 * Theme.gap; height: Theme.rowDense
                        Segmented {
                            id: modeSeg
                            objectName: "animLayerMode_" + row.modelData.id
                            anchors.verticalCenter: parent.verticalCenter; implicitHeight: 24
                            options: [{ value: "add", label: "Add" }, { value: "replace", label: "Replace" }]
                            current: row.modelData.mode
                            onPicked: (v) => root.model.setMode(row.modelData.id, v)
                        }
                        Slider {
                            id: weight
                            objectName: "animLayerWeight_" + row.modelData.id
                            anchors { left: modeSeg.right; leftMargin: Theme.pad; right: weightText.left; rightMargin: Theme.gap
                                      verticalCenter: parent.verticalCenter }
                            height: Theme.field; defaultValue: 1
                            value: row.modelData.weight
                            onScrubStarted: root.model.beginWeight(row.modelData.id)
                            onScrubbed: (v) => root.model.weightTo(v)
                            onScrubEnded: root.model.endWeight()
                            onEdited: (v) => root.model.setWeight(row.modelData.id, v)
                        }
                        Text {
                            id: weightText
                            anchors { right: parent.right; verticalCenter: parent.verticalCenter }
                            width: 40; horizontalAlignment: Text.AlignRight
                            text: Math.round(row.modelData.weight * 100) + " %" + (row.modelData.faded ? " ◆" : "")
                            color: Theme.fg2; font.family: uiFont; font.pixelSize: Theme.label
                        }
                    }
                }
            }
            Rectangle {     // the Base: always at the bottom, picked = new keys go where they always went
                objectName: "animLayerBase"
                width: 300; height: Theme.rowDense; radius: Theme.radiusCtl
                color: root.model.active === "" ? Theme.active : baseArea.containsMouse ? Theme.hover : "transparent"
                Text { x: Theme.gap; anchors.verticalCenter: parent.verticalCenter; text: "Base"; color: Theme.fg
                       font.family: uiFont; font.pixelSize: Theme.body; font.weight: root.model.active === "" ? Font.DemiBold : Font.Normal }
                MouseArea { id: baseArea; anchors.fill: parent; hoverEnabled: true; onClicked: root.model.pick("") }
            }
            Button {
                objectName: "animLayerNew"
                text: "+ New layer"; kind: "ghost"; implicitHeight: 26
                help: "A layer on top; new keys go on it"
                onClicked: root.model.add()
            }
        }
    }
}
