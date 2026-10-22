import QtQuick
import RostrumKit

// A timeline row's name side (LayerRows.qml): the fold arrow, the layer's icon and name, indented by depth. Click
// selects; double-click (or F2, Ctrl+K "Rename layer") renames; right-click opens the layer menu; pulling a layer
// row up or down moves it (not a setting, effect or mask row). A setting row selects its layer; it has no icon.
Rectangle {
    id: name
    property var rowData
    property ListView rows
    readonly property bool isLayer: rowData.row === "layer"
    readonly property bool selected: rowData.id === backend.selected
    readonly property bool inSelected: !selected && isLayer && rowData.id === backend.selectedLayer   // a key of it is selected
    readonly property int indent: Theme.gap + rowData.depth * 16
    radius: Theme.radiusCtl
    color: selected ? Theme.accentSoft : hover.containsMouse || inSelected ? Theme.hover : "transparent"

    property bool renaming: false
    function beginRename() { if (isLayer) { renaming = true; nameBox.text = rowData.label; nameBox.forceActiveFocus(); nameBox.selectAll() } }
    function endRename(keep) { if (renaming) { renaming = false; if (keep) backend.renameLayer(rowData.id, nameBox.text) } }
    Connections { target: backend; function onRenameRequested(id) { if (id === name.rowData.id) name.beginRename() } }

    MouseArea {
        id: hover
        property real pressY: 0
        property bool dragging: false
        property bool dropped: false
        anchors.fill: parent; hoverEnabled: true; acceptedButtons: Qt.LeftButton | Qt.RightButton
        onPressed: (m) => { pressY = m.y; dropped = false }
        onPositionChanged: (m) => {
            if (!pressed || !name.isLayer || !(m.buttons & Qt.LeftButton)) return
            if (!dragging && Math.abs(m.y - pressY) > 6) { dragging = true; name.rows.dragId = name.rowData.id }
            if (dragging) name.rows.dropAt(mapToItem(name.rows.contentItem, m.x, m.y).y)
        }
        onReleased: { if (dragging) { dragging = false; dropped = true; name.rows.finishDrag() } }
        onCanceled: { dragging = false; name.rows.dragId = ""; name.rows.dropRow = "" }
        onClicked: (m) => {
            if (dropped) return
            if (m.button === Qt.RightButton) {
                if (name.isLayer) { const p = mapToItem(name.rows, m.x, m.y); name.rows.openMenu(name.rowData.id, p.x, p.y) }
            } else backend.select(name.rowData.owner)
        }
        onDoubleClicked: name.beginRename()
    }
    Item {  // the fold arrow (absent when there is nothing to fold)
        x: name.indent - 2; width: 14; height: parent.height
        visible: name.rowData.fold !== ""
        Chevron { anchors.centerIn: parent; rotation: name.rowData.fold === "open" ? 0 : -90
                  color: foldArea.containsMouse ? Theme.fg : Theme.fg3 }
        MouseArea { id: foldArea; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                    onClicked: backend.toggleFold(name.rowData.id) }
    }
    LayerIcon {
        id: icon
        visible: name.rowData.row !== "field"
        x: name.indent + 16; anchors.verticalCenter: parent.verticalCenter
        kind: name.rowData.kind; shape: name.rowData.shape
        ink: name.selected ? Theme.accentHover : name.rowData.owned ? Theme.fg3 : Theme.fg2
    }
    TextInput {  // the name box while renaming: Enter keeps, Esc or leaving the row drops
        id: nameBox
        visible: name.renaming
        anchors { left: icon.right; leftMargin: Theme.gap; right: parent.right; rightMargin: Theme.gap; verticalCenter: parent.verticalCenter }
        font.family: uiFont; font.pixelSize: Theme.body; color: Theme.fg; selectByMouse: true; clip: true
        onAccepted: name.endRename(true)
        onActiveFocusChanged: if (!activeFocus) name.endRename(true)
        Keys.onEscapePressed: name.endRename(false)
    }
    Text {
        visible: !name.renaming
        x: icon.visible ? icon.x + icon.width + Theme.gap : name.indent + 16
        width: parent.width - x - Theme.gap; anchors.verticalCenter: parent.verticalCenter
        text: name.rowData.label; elide: Text.ElideRight; font.family: uiFont
        font.pixelSize: name.isLayer ? Theme.body : Theme.label + 1
        color: name.isLayer || name.selected ? Theme.fg : Theme.fg2
    }
}
