import QtQuick
import RostrumKit

// A timeline row's name side (LayerRows.qml): the fold arrow, the layer's icon and name, indented by depth. Click
// selects; Ctrl+click adds or removes it, Shift+click selects the range from the first selected (as any Windows list);
// a selected layer's name is lit: accent text and a slim accent bar at the row's left edge (Sam: no box across the
// row; its bar in the track lights too, LayerTrack.qml). Double-click (or F2, Ctrl+K "Rename layer") renames; right-click opens the
// layer menu; pulling a layer row up or down moves it (not a setting, effect or mask row). A setting row selects its
// layer; it has no icon.
Rectangle {
    id: name
    property var rowData
    property ListView rows
    enabled: !rows.compact           // compact: the one name row is the list of every layer (LayerTimeline.qml)
    readonly property bool isLayer: rowData.row === "layer"
    readonly property bool isFrame: rowData.frame === true     // the frame: pinned on top, a lock but no eye, never renamed or moved
    readonly property string lit: rows.lit[rowData.id] || ""     // the list's one lookup (multi.py `lit`)
    readonly property bool selected: lit === "sel"
    readonly property bool inSelected: isLayer && lit === "in"   // a key, effect or mask of it is selected
    readonly property int indent: Theme.gap + rowData.depth * 16
    radius: Theme.radiusCtl
    color: hover.containsMouse || inSelected ? Theme.hover : "transparent"
    Rectangle {  // the selection mark: a slim accent bar at the row's left edge
        visible: name.selected
        width: 2; height: parent.height - 8; radius: 1; anchors.verticalCenter: parent.verticalCenter
        color: Theme.accent
    }

    property bool renaming: false
    function beginRename() { if (isLayer && !isFrame) { renaming = true; nameBox.text = rowData.label; nameBox.forceActiveFocus(); nameBox.selectAll() } }
    function endRename(keep) { if (renaming) { renaming = false; if (keep) backend.renameLayer(rowData.id, nameBox.text) } }
    // the menu or Ctrl+K that asked has not given the keyboard back yet: it does as it closes and would end the rename at once
    Connections { target: backend; function onRenameRequested(id) { if (id === name.rowData.id) askLater.restart() } }
    Timer { id: askLater; interval: 120; onTriggered: name.beginRename() }

    MouseArea {
        id: hover
        property real pressY: 0
        property bool dragging: false
        property bool dropped: false
        anchors.fill: parent; hoverEnabled: true; acceptedButtons: Qt.LeftButton | Qt.RightButton
        enabled: !name.rows.compact      // compact: the row's name is the list of every layer (LayerTimeline.qml)
        onPressed: (m) => { pressY = m.y; dropped = false }
        onPositionChanged: (m) => {
            if (!pressed || !name.isLayer || name.isFrame || !(m.buttons & Qt.LeftButton)) return
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
            model: name.isFrame ? [{ field: "locked", tip: "Locked: the frame can't be moved" }]
                                : [{ field: "locked", tip: "Locked: it can't be picked or moved" }, { field: "hidden", tip: "Hidden: not drawn, not exported" }]
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
        width: parent.width - x - Theme.gap - (name.isLayer ? 38 : 0) - (pin.visible ? pin.width + 4 : 0)
        anchors.verticalCenter: parent.verticalCenter
        text: name.rowData.label; elide: Text.ElideRight; font.family: uiFont
        HoverTip { hovered: hover.containsMouse      // the whole name; the frame also says when Cut here is there
                   text: name.isFrame ? "Frame" : labelText.truncated ? name.rowData.label : ""
                   help: name.isFrame ? "What the export shows. Cut here (a jump to the next shot) is there once the playhead is past 0 s." : "" }
        font.pixelSize: name.isLayer ? Theme.body : Theme.label + 1
        color: name.selected ? Theme.accentHover : name.isLayer ? Theme.fg : Theme.fg2
    }
    LayerSwitchIcon {  // pinned to the frame: a quiet pin right after the name (it rides the frame, not the world)
        id: pin
        visible: name.rowData.pinned === true && !name.renaming
        kind: "pin"; on: false; hot: name.selected
        x: labelText.x + labelText.contentWidth + 4; anchors.verticalCenter: parent.verticalCenter
    }
}
