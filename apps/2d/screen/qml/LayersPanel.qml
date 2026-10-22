import QtQuick
import RostrumKit

// The composition's layers, top of the stack first. A layer's effects and masks sit under it, then a group's
// own layers; the arrow folds them. Click selects (screen state, through backend.select).
Panel {
    id: panel
    title: "Layers"
    bodyPad: Theme.gap

    // Right-click menu of a layer: what applies to the selection (backend.layerMenu), the same commands as Ctrl+K.
    function openMenu(id, px, py) {
        const rows = backend.layers
        const at = rows.findIndex(r => r.id === id)
        const item = list.itemAtIndex(at)
        menu.entries = backend.layerMenu(id)
        menu.x = px === undefined ? Theme.gap * 4 : px
        menu.y = py === undefined ? (item ? item.y - list.contentY + item.height : 0) : py
        if (menu.entries.length) menu.open()
    }

    Text {
        visible: backend.layers.length === 0
        anchors { left: parent.left; right: parent.right; top: parent.top; topMargin: Theme.gap }
        text: "Add a shape, text or picture with + Add"
        wrapMode: Text.WordWrap; color: Theme.fg3; font.family: uiFont; font.pixelSize: Theme.body
    }

    Menu {
        id: menu
        parent: list
        onPicked: (key) => backend.run(key)
    }

    ListView {
        id: list
        objectName: "layersList"            // (the scripted steps show a drop in progress through it)
        anchors.fill: parent
        model: backend.layers
        spacing: 2
        clip: true
        boundsBehavior: Flickable.StopAtBounds

        // drag-to-reorder: the dragged row, and where it would land (the row, above | below | into a group)
        property string dragId: ""
        property string dropRow: ""
        property string dropWhere: ""
        function dropAt(y) {
            let i = indexAt(width / 2, y)
            if (i < 0) i = indexAt(width / 2, y - 3)
            const rows = backend.layers
            const item = i < 0 ? null : itemAtIndex(i)
            if (i < 0 || !item || rows[i].owned || rows[i].id === dragId) { dropRow = ""; return }
            const f = (y - item.y) / item.height
            const holds = rows[i].kind === "group" || rows[i].kind === "rig"
            dropRow = rows[i].id
            dropWhere = holds && f > 0.25 && f < 0.75 ? "into" : f < 0.5 ? "above" : "below"
        }
        function finishDrag() {
            if (dragId !== "" && dropRow !== "") backend.moveLayer(dragId, dropRow, dropWhere)
            dragId = ""; dropRow = ""
        }
        Rectangle {  // the drop line (between rows), or an outline round a group the layer would go into
            readonly property var target: list.dropRow === "" ? null : list.itemAtIndex(backend.layers.findIndex(r => r.id === list.dropRow))
            visible: target !== null
            z: 5
            x: target ? target.x : 0; width: target ? target.width : 0
            y: !target ? 0 : list.dropWhere === "into" ? target.y : list.dropWhere === "above" ? target.y - 2 : target.y + target.height
            height: list.dropWhere === "into" ? (target ? target.height : 0) : 2
            radius: list.dropWhere === "into" ? Theme.radiusCtl : 1
            color: list.dropWhere === "into" ? "transparent" : Theme.accent
            border.color: Theme.accent; border.width: list.dropWhere === "into" ? 2 : 0
        }
        delegate: Rectangle {
            id: row
            required property var modelData
            readonly property bool selected: modelData.id === backend.selected
            readonly property bool inSelected: !selected && modelData.id === backend.selectedLayer   // a key of it is selected
            readonly property int indent: Theme.gap + modelData.depth * 16
            width: ListView.view.width; height: modelData.owned ? Theme.rowDense : Theme.row
            radius: Theme.radiusCtl
            color: selected ? Theme.accentSoft : hover.containsMouse || inSelected ? Theme.hover : "transparent"

            property bool renaming: false
            function beginRename() { if (!modelData.owned) { renaming = true; nameBox.text = modelData.label; nameBox.forceActiveFocus(); nameBox.selectAll() } }
            function endRename(keep) { if (renaming) { renaming = false; if (keep) backend.renameLayer(modelData.id, nameBox.text) } }
            Connections { target: backend; function onRenameRequested(id) { if (id === row.modelData.id) row.beginRename() } }

            opacity: list.dragId === modelData.id ? 0.45 : 1
            MouseArea {
                id: hover
                property real pressY: 0
                property bool dragging: false
                property bool dropped: false
                anchors.fill: parent; hoverEnabled: true; acceptedButtons: Qt.LeftButton | Qt.RightButton
                onPressed: (m) => { pressY = m.y; dropped = false }
                onPositionChanged: (m) => {          // pulling a layer row up or down moves it (not an effect or mask row)
                    if (!pressed || row.modelData.owned || !(m.buttons & Qt.LeftButton)) return
                    if (!dragging && Math.abs(m.y - pressY) > 6) { dragging = true; list.dragId = row.modelData.id }
                    if (dragging) list.dropAt(mapToItem(list.contentItem, m.x, m.y).y)
                }
                onReleased: { if (dragging) { dragging = false; dropped = true; list.finishDrag() } }
                onCanceled: { dragging = false; list.dragId = ""; list.dropRow = "" }
                onClicked: (m) => {
                    if (dropped) return
                    if (m.button === Qt.RightButton) { if (!row.modelData.owned) panel.openMenu(row.modelData.id, mapToItem(list, m.x, m.y).x, mapToItem(list, m.x, m.y).y) }
                    else backend.select(row.modelData.id)
                }
                onDoubleClicked: row.beginRename()   // double-click (or F2, Ctrl+K "Rename layer") renames
            }
            Item {  // the fold arrow (absent when there is nothing to fold)
                id: fold
                x: row.indent - 2; width: 14; height: parent.height
                visible: row.modelData.fold !== ""
                Chevron { anchors.centerIn: parent; rotation: row.modelData.fold === "open" ? 0 : -90
                          color: foldArea.containsMouse ? Theme.fg : Theme.fg3 }
                MouseArea { id: foldArea; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                            onClicked: backend.toggleFold(row.modelData.id) }
            }
            LayerIcon {
                id: icon
                x: row.indent + 16; anchors.verticalCenter: parent.verticalCenter
                kind: row.modelData.kind; shape: row.modelData.shape
                ink: row.selected ? Theme.accentHover : row.modelData.owned ? Theme.fg3 : Theme.fg2
            }
            TextInput {  // the name box while renaming: Enter keeps, Esc or leaving the row drops
                id: nameBox
                visible: row.renaming
                anchors.left: icon.right; anchors.leftMargin: Theme.gap; anchors.verticalCenter: parent.verticalCenter
                anchors.right: mark.left; anchors.rightMargin: Theme.gap
                font.family: uiFont; font.pixelSize: Theme.body; color: Theme.fg; selectByMouse: true; clip: true
                onAccepted: row.endRename(true)
                onActiveFocusChanged: if (!activeFocus) row.endRename(true)
                Keys.onEscapePressed: row.endRename(false)
            }
            Text {
                visible: !row.renaming
                anchors.left: icon.right; anchors.leftMargin: Theme.gap; anchors.verticalCenter: parent.verticalCenter
                anchors.right: mark.left; anchors.rightMargin: Theme.gap
                text: row.modelData.label; elide: Text.ElideRight; font.family: uiFont
                font.pixelSize: row.modelData.owned ? Theme.label + 1 : Theme.body
                color: row.modelData.owned && !row.selected ? Theme.fg2 : Theme.fg
            }
            KeyMark {  // this item has keys
                id: mark
                anchors.right: parent.right; anchors.rightMargin: Theme.gap; anchors.verticalCenter: parent.verticalCenter
                visible: row.modelData.animated; size: 6; color: row.selected ? Theme.accent : Theme.fg4
            }
        }
    }
}
