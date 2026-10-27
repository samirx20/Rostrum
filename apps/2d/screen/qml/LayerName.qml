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
    function beginRename() { if (isLayer && !isFrame) { renaming = true } }     // (the box takes its text and the keys as it shows)
    function endRename(keep) { if (renaming) { renaming = false; if (keep) backend.renameLayer(rowData.id, nameBox.text) } }
    Connections { target: backend; function onRenameRequested(id) { if (id === name.rowData.id) name.beginRename() } }   // menus run a choice once closed (ActionMenu)

    HoverHandler { id: rowHover }   // passive: stays on while a child area (the lock, the eye) has the pointer, so a switch never blinks out under it and loses the first click
    MouseArea {
        id: hover
        property real pressY: 0
        property bool dragging: false
        property bool dropped: false
        anchors.fill: parent; hoverEnabled: true; acceptedButtons: Qt.LeftButton | Qt.RightButton
        enabled: !name.rows.compact      // compact: the row's name is the list of every layer (LayerTimeline.qml)
        preventStealing: name.isLayer && !name.isFrame   // a layer row's drag is a reorder: the list must not take it and flick
        onPressed: (m) => { pressY = m.y; dropped = false }
        onPositionChanged: (m) => {
            if (!pressed || !name.isLayer || name.isFrame || !(m.buttons & Qt.LeftButton)) return
            if (!dragging && Math.abs(m.y - pressY) > 6) { dragging = true; name.rows.beginDrag(name.rowData, pressY) }
            if (dragging && name.rows.dragId === name.rowData.id) name.rows.dropAt(mapToItem(name.rows.contentItem, m.x, m.y).y)   // (Esc ended it: dragId "")
        }
        onReleased: { if (dragging) { dragging = false; dropped = true; name.rows.finishDrag() } }
        onCanceled: { dragging = false; name.rows.cancelDrag() }
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
        objectName: "rowFold:" + name.rowData.id       // a scripted hand finds it
        x: name.indent - 2; width: 14; height: parent.height
        visible: name.rowData.fold !== ""
        Chevron { anchors.centerIn: parent; rotation: name.rowData.fold === "open" ? 0 : -90
                  color: foldArea.containsMouse ? Theme.fg : Theme.fg3 }
        MouseArea { id: foldArea; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; enabled: !name.rows.compact
                    onClicked: (m) => (m.modifiers & Qt.AltModifier)       // Alt: every row at this level, as After Effects
                                      ? backend.foldLevel(name.rowData.id, name.rowData.fold !== "open")
                                      : backend.toggleFold(name.rowData.id) }
    }
    LayerIcon {
        id: icon
        visible: name.rowData.row !== "field"
        x: name.indent + 16; anchors.verticalCenter: parent.verticalCenter
        kind: name.rowData.kind; shape: name.rowData.shape
        ink: name.rowData.owned ? Theme.fg3 : Theme.fg2; litInk: Theme.accentHover; lit: name.selected
    }
    NameBox {  // the kit's name box (Ctrl+Z with nothing typed closes it and undoes): Enter or leaving the row keeps, Esc drops
        id: nameBox
        visible: name.renaming
        current: name.rowData.label
        keepOnAway: true
        anchors { left: icon.right; leftMargin: Theme.gap; right: parent.right; rightMargin: Theme.gap; verticalCenter: parent.verticalCenter }
        onDone: (t) => name.endRename(true)
        onCancelled: name.endRename(false)
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
                objectName: "layerSwitch:" + name.rowData.id + ":" + modelData.field     // the eye and the lock: a scripted hand finds them
                required property var modelData
                readonly property bool swiped: name.rows.swipeField === modelData.field && !!name.rows.swipeIds[name.rowData.id]   // a drag over rows is passing this one
                readonly property bool on: swiped ? name.rows.swipeOn : !!name.rowData[modelData.field]
                visible: on || swiped || swArea.pressed || rowHover.hovered   // pressed: it stays while the pointer is dragged off it
                width: 18; height: 18
                LayerSwitchIcon { anchors.centerIn: parent; kind: sw.modelData.field; on: sw.on; hot: swArea.containsMouse }
                MouseArea {  // a click is one change; Alt+click an eye shows only this layer; press and drag over more rows sets them all to its new state
                    id: swArea
                    property real pressY: 0
                    property bool swiping: false
                    property bool swept: false
                    anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                    preventStealing: true
                    onPressed: (m) => { pressY = m.y; swept = false }
                    onPositionChanged: (m) => {
                        if (!pressed) return
                        if (!swiping && Math.abs(m.y - pressY) > 4) { swiping = true; name.rows.swipeBegin(name.rowData.id, sw.modelData.field, !sw.on) }
                        if (swiping) name.rows.swipeTo(mapToItem(name.rows.contentItem, m.x, m.y).y)
                    }
                    onReleased: { if (swiping) { swiping = false; swept = true; name.rows.swipeEnd() } }
                    onCanceled: { if (swiping) { swiping = false; name.rows.swipeEnd() } }
                    onClicked: (m) => {
                        if (swept) return
                        if ((m.modifiers & Qt.AltModifier) && sw.modelData.field === "hidden") backend.soloLayer(name.rowData.id)
                        else backend.toggleSwitch(name.rowData.id, sw.modelData.field)
                    }
                }
                HoverTip { hovered: swArea.containsMouse; pressed: swArea.pressed; text: sw.modelData.tip }
            }
        }
    }
    Text {
        id: labelText
        visible: !name.renaming
        opacity: (name.rows.swipeField === "hidden" && name.rows.swipeIds[name.rowData.id] ? name.rows.swipeOn : name.rowData.hidden) ? 0.45 : 1
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
