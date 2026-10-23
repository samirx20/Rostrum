import QtQuick
import RostrumKit

// A timeline row's name side (LayerRows.qml): the fold arrow, the layer's icon and name, indented by depth. Click
// selects; Ctrl+click adds or removes it, Shift+click selects the range from the first selected (as any Windows list);
// every selected layer's row is lit. Double-click (or F2, Ctrl+K "Rename layer") renames; right-click opens the
// layer menu; pulling a layer row up or down moves it (not a setting, effect or mask row). A setting row selects its
// layer; it has no icon.
Rectangle {
    id: name
    property var rowData
    property ListView rows
    enabled: !rows.compact           // compact: the one name row is the list of every layer (LayerTimeline.qml)
    readonly property bool isLayer: rowData.row === "layer"
    readonly property bool selected: rowData.id === backend.selected || isLayer && backend.multi.ids.indexOf(rowData.id) >= 0 && backend.multi.count > 1
    readonly property bool inSelected: !selected && isLayer && backend.multi.ids.indexOf(rowData.id) >= 0   // a key, effect or mask of it is selected
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
        enabled: !name.rows.compact      // compact: the row's name is the list of every layer (LayerTimeline.qml)
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
            } else if (name.isLayer && (m.modifiers & Qt.ControlModifier)) backend.multi.toggle(name.rowData.id)   // add / remove
            else if (name.isLayer && (m.modifiers & Qt.ShiftModifier)) backend.multi.selectRange(name.rowData.id)   // a range
            else backend.select(name.rowData.owner)
        }
        onDoubleClicked: name.beginRename()
    }
    Item {  // the fold arrow (absent when there is nothing to fold)
        x: name.indent - 2; width: 14; height: parent.height
        visible: name.rowData.fold !== ""
        Chevron { anchors.centerIn: parent; rotation: name.rowData.fold === "open" ? 0 : -90
                  color: foldArea.containsMouse ? Theme.fg : Theme.fg3 }
        MouseArea { id: foldArea; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; enabled: !name.rows.compact
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
    Row {  // the lock and the eye: on hover, or always while on (a click is one change; hidden layers dim and don't export)
        id: switches
        visible: name.isLayer && !name.renaming
        anchors { right: parent.right; rightMargin: Theme.grid; verticalCenter: parent.verticalCenter }
        Repeater {
            model: [{ field: "locked", tip: "Locked: it can't be picked or moved" }, { field: "hidden", tip: "Hidden: not drawn, not exported" }]
            delegate: Item {
                id: sw
                required property var modelData
                readonly property bool on: !!name.rowData[modelData.field]
                visible: on || hover.containsMouse || swArea.containsMouse
                width: 18; height: 18
                LayerSwitchIcon { anchors.centerIn: parent; kind: sw.modelData.field; on: sw.on; hot: swArea.containsMouse }
                MouseArea { id: swArea; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                            onClicked: backend.toggleSwitch(name.rowData.id, sw.modelData.field) }
                HoverTip { hovered: swArea.containsMouse; pressed: swArea.pressed; text: sw.modelData.tip }
            }
        }
    }
    Text {
        id: labelText
        visible: !name.renaming
        opacity: name.rowData.hidden ? 0.45 : 1
        x: icon.visible ? icon.x + icon.width + Theme.gap : name.indent + 16
        width: parent.width - x - Theme.gap - (name.isLayer ? 38 : 0) - (frameNote.visible ? frameNote.implicitWidth + Theme.gap : 0)
        anchors.verticalCenter: parent.verticalCenter
        text: name.rowData.label; elide: Text.ElideRight; font.family: uiFont
        HoverTip { text: labelText.truncated ? name.rowData.label : ""; hovered: hover.containsMouse }   // the whole name
        font.pixelSize: name.isLayer ? Theme.body : Theme.label + 1
        color: name.isLayer || name.selected ? Theme.fg : Theme.fg2
    }
    Text {      // a frame-by-frame layer: "9 drawings · on twos"
        id: frameNote
        visible: !name.renaming && (name.rowData.frameNote || "") !== "" && !hover.containsMouse
        anchors.right: parent.right; anchors.rightMargin: Theme.gap + 38; anchors.verticalCenter: parent.verticalCenter
        text: name.rowData.frameNote || ""; color: Theme.fg3; font.family: uiFont; font.pixelSize: Theme.label
    }
}
