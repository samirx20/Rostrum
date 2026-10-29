import QtQuick
import "."

// Animation layers in the timeline's play cell (TIMELINE.md › Animation layers): a stack of moves over the Base, each
// with a weight (a breath over a walk). One small ⧉ button, lit while a layer takes the new keys (its tip names it).
// It opens a popover: the layers top first, the Base at the bottom, + New layer. A row: click picks it (new keys go
// there; the rows show its keys only), double-click the name renames, the switch turns it on / off, Add | Replace,
// the weight slider (one drag = one change; a faded layer's slider keys the weight at the playhead), ⋯ for Key weight
// here, Move up / down and Delete. `model`: the app's rostrum_gui/anim_layers.py (backend.animLayers).
// The rows are a ListModel kept in step with `model.rows` by layer id (sync): a change updates a row in place, so a
// row (and a weight drag under the pointer) lives through every change the drag itself makes.
Item {
    id: root
    property var model: backend.animLayers
    implicitWidth: 24
    implicitHeight: 24

    ListModel { id: layerRows }
    function sync() {          // the layers top first, each row moved, updated, made or dropped by its id
        const now = root.model.rows
        for (let i = 0; i < now.length; i++) {
            const r = { layerId: now[i].id, name: now[i].name, weight: now[i].weight, mode: now[i].mode, live: now[i].on,
                        faded: now[i].faded, active: now[i].active }
            let j = i
            while (j < layerRows.count && layerRows.get(j).layerId !== r.layerId) j++
            if (j === layerRows.count) { layerRows.insert(i, r); continue }
            if (j !== i) layerRows.move(j, i, 1)
            const was = layerRows.get(i)
            for (const k in r) if (was[k] !== r[k]) layerRows.setProperty(i, k, r[k])
        }
        if (layerRows.count > now.length) layerRows.remove(now.length, layerRows.count - now.length)
    }
    Connections { target: root.model; function onChanged() { root.sync() } }
    Component.onCompleted: sync()

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
                model: layerRows
                delegate: Rectangle {
                    id: row
                    required property int index
                    required property string layerId
                    required property string name
                    required property real weight
                    required property string mode
                    required property bool live           // on
                    required property bool faded
                    required property bool active
                    objectName: "animLayerRow_" + layerId
                    width: 300; height: 2 * Theme.rowDense + Theme.grid; radius: Theme.radiusCtl
                    color: active ? Theme.active : pick.containsMouse ? Theme.hover : "transparent"
                    MouseArea { id: pick; anchors.fill: parent; hoverEnabled: true; onClicked: root.model.pick(row.layerId) }
                    Item {     // the name (double-click renames), on / off, ⋯
                        x: Theme.gap; width: parent.width - 2 * Theme.gap; height: Theme.rowDense
                        Text {
                            id: nameText
                            objectName: "animLayerName_" + row.layerId
                            visible: !nameBox.visible
                            anchors.verticalCenter: parent.verticalCenter
                            width: parent.width - onSwitch.width - more.width - 2 * Theme.gap; elide: Text.ElideRight
                            text: row.name; color: row.live ? Theme.fg : Theme.fg3
                            font.family: uiFont; font.pixelSize: Theme.body; font.weight: row.active ? Font.DemiBold : Font.Normal
                            MouseArea { anchors.fill: parent; onClicked: root.model.pick(row.layerId)
                                        onDoubleClicked: nameBox.visible = true }
                        }
                        NameBox {
                            id: nameBox
                            objectName: "animLayerNameBox_" + row.layerId
                            visible: false; current: row.name
                            anchors.verticalCenter: parent.verticalCenter; width: nameText.width
                            onDone: (t) => { visible = false; root.model.rename(row.layerId, t) }
                            onCancelled: visible = false
                        }
                        Toggle {
                            id: onSwitch
                            objectName: "animLayerOn_" + row.layerId
                            anchors { right: more.left; rightMargin: Theme.gap; verticalCenter: parent.verticalCenter }
                            checked: row.live
                            onToggled: (v) => root.model.setOn(row.layerId, v)
                        }
                        IconButton {
                            id: more
                            objectName: "animLayerMore_" + row.layerId
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
                                objectName: "animLayerMenu_" + row.layerId
                                y: parent.height
                                onPicked: (v) => v === "key" ? root.model.keyWeight(row.layerId)
                                               : v === "up" ? root.model.move(row.layerId, 1)
                                               : v === "down" ? root.model.move(row.layerId, -1)
                                               : root.model.remove(row.layerId)
                            }
                        }
                    }
                    Item {     // Add | Replace, the weight
                        x: Theme.gap; y: Theme.rowDense + Theme.grid; width: parent.width - 2 * Theme.gap; height: Theme.rowDense
                        Segmented {
                            id: modeSeg
                            objectName: "animLayerMode_" + row.layerId
                            anchors.verticalCenter: parent.verticalCenter; implicitHeight: 24
                            options: [{ value: "add", label: "Add" }, { value: "replace", label: "Replace" }]
                            current: row.mode
                            onPicked: (v) => root.model.setMode(row.layerId, v)
                        }
                        Slider {
                            id: weight
                            objectName: "animLayerWeight_" + row.layerId
                            anchors { left: modeSeg.right; leftMargin: Theme.pad; right: weightText.left; rightMargin: Theme.gap
                                      verticalCenter: parent.verticalCenter }
                            height: Theme.field; defaultValue: 1
                            value: row.weight
                            onScrubStarted: root.model.beginWeight(row.layerId)
                            onScrubbed: (v) => root.model.weightTo(v)
                            onScrubEnded: root.model.endWeight()
                            onEdited: (v) => root.model.setWeight(row.layerId, v)
                        }
                        Text {
                            id: weightText
                            anchors { right: parent.right; verticalCenter: parent.verticalCenter }
                            width: 40; horizontalAlignment: Text.AlignRight
                            text: Math.round(row.weight * 100) + " %" + (row.faded ? " ◆" : "")
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
