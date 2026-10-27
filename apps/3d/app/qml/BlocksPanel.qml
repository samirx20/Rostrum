import QtQuick
import RostrumKit

// The bottom panel as a material's blocks (brief 23b; backend.blocks, screen3d/blocks_qt.py), in the timeline's place
// while open: a header line "‹ Back · <material> blocks", then the kit's block view (RostrumKit/BlockView.qml) with the
// material's blocks and wires. Every change in the view is one operation (graph.add / connect / set / remove), one
// undo step; the picked block's settings show in the right panel (BlockSettings.qml). ‹ Back or Esc (with nothing
// open in the view) returns to the timeline. While the keyboard is in the view, its own keys (Delete, Tab, F, Space,
// Esc) are the view's, not the window's (Main.qml's KeyMap skips them: `holds`).
Rectangle {
    id: panel
    objectName: "blocksPanel"
    readonly property var bk: backend.blocks
    color: Theme.panel
    function holds(item) {           // the keyboard is somewhere in the view
        for (let it = item; it; it = it.parent)
            if (it === view) return true
        return false
    }
    onVisibleChanged: if (visible) view.forceActiveFocus()

    Item {
        id: head
        x: Theme.padLeft; width: parent.width - Theme.padLeft - Theme.padRight; height: Theme.row
        Button {
            id: back
            objectName: "blocksBack"
            anchors.verticalCenter: parent.verticalCenter
            kind: "ghost"; text: "‹ Back"
            tip: "Back to the timeline"; help: "The timeline again (Esc does the same); the blocks stay as they are."
            onClicked: panel.bk.close()
        }
        Text {
            anchors { left: back.right; leftMargin: Theme.grid; verticalCenter: parent.verticalCenter }
            text: "· " + panel.bk.title + " blocks"
            color: Theme.fg2; font.family: uiFont; font.pixelSize: Theme.body; elide: Text.ElideRight
            width: parent.width - back.width - Theme.grid
        }
    }
    BlockView {
        id: view
        objectName: "blockView"
        anchors { left: parent.left; right: parent.right; top: head.bottom; bottom: parent.bottom }
        catalogue: panel.bk.catalogue
        blocks: panel.bk.blocks
        wires: panel.bk.wires
        selected: panel.bk.selected
        kindColours: panel.bk.kindColours
        converts: panel.bk.converts
        onAddRequested: (type, x, y, fromPort) => panel.bk.add(type, x, y, fromPort || "")
        onMoved: (id, x, y) => panel.bk.move(id, x, y)
        onConnectRequested: (from, to) => panel.bk.wire(from, to)
        onDisconnectRequested: (to) => panel.bk.unwire(to)
        onRemoveRequested: (ids) => panel.bk.remove(ids)
        onPicked: (id) => panel.bk.pick(id)
        onEscaped: panel.bk.close()
    }
}
