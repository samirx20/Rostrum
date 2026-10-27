import QtQuick
import RostrumKit

// The bottom panel as a material's blocks (brief 23b; backend.blocks, screen3d/blocks_qt.py), in the timeline's place
// while open: a header line "‹ Back · <material> blocks", then the kit's block view (RostrumKit/BlockView.qml) with the
// material's blocks and wires. Every change in the view is one operation (graph.add / connect / set / remove), one
// undo step; the picked block's settings show in the right panel (BlockSettings.qml). ‹ Back or Esc (with nothing
// open in the view) returns to the timeline. While the keyboard is in the view, its own keys (Delete, Tab, F, Space,
// Esc) are the view's, not the window's (Main.qml's KeyMap skips them: `holds`).
// It opens at 100 % with Surface in the right third, level with the middle (wires run left to right, so new blocks
// have room on the left); a graph too big for that is fitted. A block added from + Add block or Tab lands left of the
// leftmost block (blocks_qt.add) and the view moves just enough to show it.
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
    onVisibleChanged: if (visible) { view.forceActiveFocus(); placeSoon() }
    Connections { target: panel.bk; function onMaterialChanged() { if (panel.visible) panel.placeSoon() } }
    onHeightChanged: if (settle.running) place()       // the bottom panel still growing to its blocks height
    function placeSoon() { Qt.callLater(place); settle.restart() }
    Timer { id: settle; interval: Theme.reveal + 80; onTriggered: panel.place() }
    function place() {
        const r = bk.box(""), s = bk.box("surface"), W = view.width, H = view.height, m = 48
        if (!r.x1 || W <= 0 || H <= 0) return
        view.fitted = true                              // the kit's own first fit is not wanted (it ran at the old height)
        if (r.x1 - r.x0 > W - 2 * m || r.y1 - r.y0 > H - 2 * m) { view.fit(); return }
        view.zoom = 1
        const px = W * 5 / 6 - (s.x0 + s.x1) / 2, py = H / 2 - (s.y0 + s.y1) / 2
        view.panX = Math.max(m - r.x0, Math.min(W - m - r.x1, px))     // every block inside the margins
        view.panY = Math.max(m - r.y0, Math.min(H - m - r.y1, py))
    }
    function show(id) {                                 // pan just enough that this block is in view
        const b = bk.box(id), m = 48, z = view.zoom
        if (!b.x1) return
        const l = b.x0 * z + view.panX, t = b.y0 * z + view.panY, rr = b.x1 * z + view.panX, bb = b.y1 * z + view.panY
        if (l < m) view.panX += m - l; else if (rr > view.width - m) view.panX -= rr - (view.width - m)
        if (t < m) view.panY += m - t; else if (bb > view.height - m) view.panY -= bb - (view.height - m)
    }
    function added(type, x, y, fromPort) {
        // the kit's + Add block / Tab put the list's block at the view's middle (BlockView.openAddAtCentre): no point
        // was chosen there, so the screen places it (left of the others); a double-click / right-click point is kept
        const c = view.toCanvas(Qt.point(view.width / 2, view.height / 2))
        const centred = !fromPort && Math.abs(x - (c.x - bk.blockWidth / 2)) < 2 && Math.abs(y - (c.y - 40)) < 2
        const before = bk.blocks.length
        bk.add(type, x, y, fromPort || "", !centred)    // (one operation; the view's data is new when it returns)
        if (bk.blocks.length > before) show(bk.selected)
    }

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
        onAddRequested: (type, x, y, fromPort) => panel.added(type, x, y, fromPort)
        onMoved: (id, x, y) => panel.bk.move(id, x, y)
        onConnectRequested: (from, to) => panel.bk.wire(from, to)
        onDisconnectRequested: (to) => panel.bk.unwire(to)
        onRemoveRequested: (ids) => panel.bk.remove(ids)
        onPicked: (id) => panel.bk.pick(id)
        onEscaped: panel.bk.close()
    }
}
