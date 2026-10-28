import QtQuick
import QtQuick.Controls as QQC
import RostrumCursors 1.0
import "."
import "Blocks.js" as Blocks

// The block view (BLOCKS.md): blocks joined by wires, data-driven. The app gives plain data (`catalogue`, `blocks`,
// `wires`, `selected`, `kindColours`, `converts`) and gets requests as signals; it changes its document and gives the
// data back. The view draws what is in hand meanwhile: a moved block stays where it was dropped, a live wire follows
// the pointer. Rules (ports, kinds, loops, search) are Blocks.js, the same as rostrum_gui/blocks.py.
//
// Hands: drag a block to move it; drag from a port to another to wire them (the ports the wire may reach light up,
// the rest dim); drag a wired input's end away to move or remove that wire; drop a new wire on nothing to add a block
// it feeds. Pan: drag empty space, middle-drag, or Space + drag. Wheel: zoom about the pointer (25 % to 200 %). F: fit
// all. Delete: remove the picked block. Tab, a double-click or right-click on empty space, or "Add block": the add list.
// Esc: a drag or wire is dropped; with nothing going on, escaped().
//
// Speed: a drag moves one block item (its x / y) and redraws the wires bound to it; nothing is rebuilt until the app
// sends new data at the release.
FocusScope {
    id: view
    objectName: "blockView"
    property var catalogue: []
    property var blocks: []
    property var wires: []
    property string selected: ""
    property var kindColours: ({})
    property var converts: ({})             // {out kind: [input kinds it also feeds]}
    property real zoom: 1
    property real panX: 0
    property real panY: 0
    readonly property real minZoom: 0.25
    readonly property real maxZoom: 2
    signal addRequested(string type, real x, real y, string fromPort)
    signal moved(string id, real x, real y)
    signal connectRequested(string from, string to)
    signal disconnectRequested(string to)
    signal removeRequested(var ids)
    signal picked(string id)
    signal escaped()                        // ("escape" is a reserved JS name)
    clip: true

    // the data by id, and the block items by id (wire ends bind through these)
    property var byId: ({})
    property var items: ({})
    property int itemsRev: 0
    property Item draggingBlock: null
    property bool cancelled: false          // Esc in a drag: the rest of that drag does nothing
    property bool spaceHeld: false
    property bool fitted: false
    property point lastPointer: Qt.point(width / 2, height / 2)

    // the wire being drawn: its fixed end, which side that is, its kind; the wire end picked up (`wireOld`, an input);
    // where the pointer is (canvas units) and the port it would land on ("in:id.port"); blocks it may not reach (loops)
    property string wireFrom: ""
    property string wireSide: "out"
    property string wireKind: ""
    property string wireOld: ""
    property bool wireLive: false
    property bool wireParked: false         // dropped on nothing: drawn to the add list until it closes
    property point wireStart
    property point wirePointer
    property string wireOver: ""
    property var forbid: ({})

    onBlocksChanged: sync()
    onWidthChanged: fitOnce()
    onHeightChanged: fitOnce()
    ListModel { id: idModel }
    function sync() {
        const m = {}
        for (const b of blocks) m[b.id] = b
        for (let i = idModel.count - 1; i >= 0; i--) if (!m[idModel.get(i).bid]) idModel.remove(i)
        const have = {}
        for (let i = 0; i < idModel.count; i++) have[idModel.get(i).bid] = true
        byId = m
        for (const b of blocks) if (!have[b.id]) idModel.append({ bid: b.id })
        fitOnce()
    }
    function register(id, item) { items[id] = item; itemsRev++ }
    function unregister(id, item) { if (items[id] === item) { delete items[id]; itemsRev++ } }
    function portOf(id, side, name) {
        const b = byId[id]
        return b ? ((side === "out" ? b.outputs : b.inputs) || []).find(p => p.name === name) || null : null
    }
    function kindOf(port, side) { const id = Blocks.blockOf(port); const p = portOf(id, side, port.slice(id.length + 1)); return p ? p.kind : "" }

    // view = canvas × zoom + pan
    function toCanvas(p) { return Qt.point((p.x - panX) / zoom, (p.y - panY) / zoom) }
    function zoomAt(z, vx, vy) {
        const c = toCanvas(Qt.point(vx, vy))
        zoom = Math.max(minZoom, Math.min(maxZoom, z))
        panX = vx - c.x * zoom; panY = vy - c.y * zoom
    }
    function fit() {
        if (!blocks.length || width <= 0 || height <= 0) return false
        let x0 = 1e9, y0 = 1e9, x1 = -1e9, y1 = -1e9
        for (const b of blocks) {
            x0 = Math.min(x0, b.x); y0 = Math.min(y0, b.y)
            x1 = Math.max(x1, b.x + Blocks.WIDTH); y1 = Math.max(y1, b.y + Blocks.height(b))
        }
        const m = 48
        zoom = Math.max(minZoom, Math.min(1, (width - 2 * m) / (x1 - x0), (height - 2 * m) / (y1 - y0)))
        panX = (width - (x1 - x0) * zoom) / 2 - x0 * zoom
        panY = (height - (y1 - y0) * zoom) / 2 - y0 * zoom
        return true
    }
    function fitOnce() { if (!fitted && fit()) fitted = true }

    // 0 at rest, 1 the wire being drawn may land here, 2 it may not (dimmed)
    function portState(id, side, name, kind) {
        if (!wireLive || wireParked) return 0
        if (side === wireSide) return wireFrom === id + "." + name ? 0 : 2
        if (forbid[id]) return 2
        return (side === "in" ? Blocks.compatible(wireKind, kind, converts) : Blocks.compatible(kind, wireKind, converts)) ? 1 : 2
    }
    function pressPort(id, side, port, at) {
        cancelled = false
        const key = id + "." + port.name
        const old = side === "in" && port.linked ? wires.find(w => w.to === key) : null
        if (old) { wireOld = key; wireFrom = old.from; wireSide = "out"; wireKind = kindOf(old.from, "out") }
        else { wireOld = ""; wireFrom = key; wireSide = side; wireKind = port.kind }
        const kept = wireOld ? wires.filter(w => w.to !== wireOld) : wires
        forbid = Blocks.reach(kept, Blocks.blockOf(wireFrom), wireSide === "out" ? "up" : "down")
        wireStart = at; wireLive = false; wireParked = false; wireOver = ""
    }
    function moveWire(at) {
        if (!wireFrom || wireParked) return
        if (!wireLive && Math.abs(at.x - wireStart.x) + Math.abs(at.y - wireStart.y) < 4) return
        wireLive = true
        const c = toCanvas(at)
        wirePointer = c
        wireOver = targetAt(c)
    }
    // The port the pointer would wire to: over a block, its nearest port that may take the wire; else a port within 16 px.
    function targetAt(c) {
        const want = wireSide === "out" ? "in" : "out"
        const near = 16 / zoom
        let best = "", bestD = 1e18
        for (const id in items) {
            const it = items[id]
            if (forbid[id] || c.x < it.x - near || c.x > it.x + it.width + near || c.y < it.y - near || c.y > it.y + it.height + near) continue
            const over = c.x >= it.x && c.x <= it.x + it.width && c.y >= it.y && c.y <= it.y + it.height
            for (const p of (want === "in" ? it.d.inputs : it.d.outputs) || []) {
                if (portState(id, want, p.name, p.kind) !== 1) continue
                const dx = it.portX(want) - c.x, dy = it.portY(want, p.name) - c.y
                const d = over ? dy * dy : dx * dx + dy * dy
                if ((over || d <= near * near) && d < bestD) { bestD = d; best = want + ":" + id + "." + p.name }
            }
        }
        return best
    }
    function endWire() {
        if (!wireFrom || wireParked) return
        if (!wireLive) { cancelWire(); return }
        const target = wireOver.slice(wireOver.indexOf(":") + 1)
        if (target && wireSide === "out") {
            if (target !== wireOld) {
                if (wireOld) disconnectRequested(wireOld)
                connectRequested(wireFrom, target)
            }
        } else if (target) {
            connectRequested(target, wireFrom)
        } else if (wireOld) {
            disconnectRequested(wireOld)
        } else if (wireSide === "out") {        // a new wire dropped on nothing: add a block it feeds, right there
            wireParked = true
            openAdd(Qt.point(wirePointer.x * zoom + panX, wirePointer.y * zoom + panY), wireFrom)
            return
        }
        cancelWire()
    }
    function cancelWire() { wireFrom = ""; wireOld = ""; wireLive = false; wireParked = false; wireOver = ""; forbid = ({}) }

    // the add list at a view point; the new block goes there (a dropped wire's new block: its left edge at the drop)
    property point addAt
    property string addFrom: ""
    // `upTo`: opening upward, the list's bottom stays above this y (the + Add block button's top; else the point)
    function openAdd(at, fromPort, upTo) {
        addAt = toCanvas(at)
        addFrom = fromPort || ""
        addList.fromKind = addFrom ? kindOf(addFrom, "out") : ""
        addList.at = at
        addList.upTo = upTo === undefined ? at.y : upTo
        addList.open()
    }
    function openAddAtCentre() {
        const c = toCanvas(Qt.point(width / 2, height / 2))
        openAdd(Qt.point(Theme.pad, Theme.pad + addButton.height + 12), "", Theme.pad)
        addAt = Qt.point(c.x - Blocks.WIDTH / 2, c.y - 40)
    }

    Keys.onPressed: (e) => {
        if (e.key === Qt.Key_Space && !e.isAutoRepeat) { spaceHeld = true; e.accepted = true }
        else if ((e.key === Qt.Key_Delete || e.key === Qt.Key_Backspace) && selected) {
            const b = byId[selected]
            if (b && b.removable !== false) removeRequested([selected])
            e.accepted = true
        }
        else if (e.key === Qt.Key_F && !(e.modifiers & (Qt.ControlModifier | Qt.AltModifier))) { fit(); e.accepted = true }
        else if (e.key === Qt.Key_Tab) { openAdd(lastPointer, ""); e.accepted = true }
    }
    Keys.onReleased: (e) => { if (e.key === Qt.Key_Space && !e.isAutoRepeat) { spaceHeld = false; e.accepted = true } }
    Keys.onEscapePressed: {
        if (wireFrom) cancelWire()
        else if (draggingBlock) { draggingBlock.cancelDrag(); cancelled = true }
        else escaped()
    }

    Rectangle { anchors.fill: parent; color: Theme.app }
    Image {                                 // a dot every 24 canvas units, so a pan and a zoom read
        readonly property real step: 24 * view.zoom * (view.zoom < 0.5 ? 2 : 1)
        x: (view.panX % step) - step; y: (view.panY % step) - step
        width: view.width + 2 * step; height: view.height + 2 * step
        fillMode: Image.Tile
        smooth: false
        source: "data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='" + Math.round(step) + "' height='"
                + Math.round(step) + "'><rect x='0' y='0' width='1.5' height='1.5' fill='%23303030'/></svg>"
    }
    MouseArea {                             // empty space: pick nothing, pan, zoom, the add list
        id: ground
        anchors.fill: parent
        acceptedButtons: Qt.LeftButton | Qt.MiddleButton | Qt.RightButton
        hoverEnabled: true
        property point start
        property point pan0
        property bool panning: false
        onPressed: (m) => {
            view.forceActiveFocus(); view.cancelled = false
            if (m.button === Qt.RightButton) { view.openAdd(Qt.point(m.x, m.y), ""); return }
            if (m.button === Qt.LeftButton) view.picked("")
            start = Qt.point(m.x, m.y); pan0 = Qt.point(view.panX, view.panY)
            panning = m.button === Qt.MiddleButton
        }
        onPositionChanged: (m) => {
            view.lastPointer = Qt.point(m.x, m.y)
            if (!pressed || view.cancelled || !(pressedButtons & (Qt.LeftButton | Qt.MiddleButton))) return
            if (!panning && Math.abs(m.x - start.x) + Math.abs(m.y - start.y) < 4) return
            panning = true
            view.panX = pan0.x + m.x - start.x; view.panY = pan0.y + m.y - start.y
        }
        onReleased: panning = false
        onDoubleClicked: (m) => { if (m.button === Qt.LeftButton) view.openAdd(Qt.point(m.x, m.y), "") }
        onWheel: (w) => view.zoomAt(view.zoom * Math.pow(1.1, w.angleDelta.y / 120), w.x, w.y)
        CanvasCursor { kind: ground.panning ? "hand-grab" : "hand" }
    }

    Item {                                  // the canvas: blocks and wires in canvas units
        id: canvas
        x: view.panX; y: view.panY
        scale: view.zoom
        transformOrigin: Item.TopLeft
        Repeater {
            model: view.wires
            delegate: BlockWire {
                required property var modelData
                readonly property string fromId: Blocks.blockOf(modelData.from)
                readonly property string toId: Blocks.blockOf(modelData.to)
                readonly property var a: (view.itemsRev, view.items[fromId] || null)
                readonly property var b: (view.itemsRev, view.items[toId] || null)
                readonly property bool lit: view.selected !== "" && (view.selected === fromId || view.selected === toId)
                visible: !!a && !!b && view.wireOld !== modelData.to
                x1: a ? a.portX("out") : 0
                y1: a ? a.portY("out", modelData.from.slice(fromId.length + 1)) : 0
                x2: b ? b.portX("in") : 0
                y2: b ? b.portY("in", modelData.to.slice(toId.length + 1)) : 0
                colour: view.kindColours[view.kindOf(modelData.from, "out")] || Theme.fg4
                opacity: lit ? 1 : 0.75
                thickness: lit ? 2.5 : 2
            }
        }
        Repeater {
            model: idModel
            delegate: BlockItem {
                id: blockItem
                view: canvas.parent             // (the delegate's own `view` hides the id)
                Component.onCompleted: view.register(bid, blockItem)
                Component.onDestruction: if (blockItem.view) blockItem.view.unregister(bid, blockItem)
            }
        }
        BlockWire {                         // the wire being drawn: from its fixed port to the pointer (or the port it snaps to)
            id: live
            z: 10
            visible: view.wireLive
            readonly property var fixed: (view.itemsRev, view.wireFrom ? view.items[Blocks.blockOf(view.wireFrom)] || null : null)
            readonly property string fixedPort: view.wireFrom.slice(Blocks.blockOf(view.wireFrom).length + 1)
            readonly property string overKey: view.wireOver.slice(view.wireOver.indexOf(":") + 1)
            readonly property var over: overKey ? view.items[Blocks.blockOf(overKey)] || null : null
            readonly property point free: over ? Qt.point(over.portX(view.wireSide === "out" ? "in" : "out"),
                                                          over.portY(view.wireSide === "out" ? "in" : "out", overKey.slice(Blocks.blockOf(overKey).length + 1)))
                                               : view.wirePointer
            readonly property point fixedAt: fixed ? Qt.point(fixed.portX(view.wireSide), fixed.portY(view.wireSide, fixedPort)) : Qt.point(0, 0)
            x1: view.wireSide === "out" ? fixedAt.x : free.x
            y1: view.wireSide === "out" ? fixedAt.y : free.y
            x2: view.wireSide === "out" ? free.x : fixedAt.x
            y2: view.wireSide === "out" ? free.y : fixedAt.y
            colour: view.kindColours[view.wireKind] || Theme.fg4
            thickness: 2
        }
    }

    MouseArea {                             // Space held: any drag pans, over blocks too
        anchors.fill: parent
        enabled: view.spaceHeld
        visible: enabled
        acceptedButtons: Qt.LeftButton | Qt.MiddleButton
        property point start
        property point pan0
        onPressed: (m) => { start = Qt.point(m.x, m.y); pan0 = Qt.point(view.panX, view.panY) }
        onPositionChanged: (m) => { if (pressed) { view.panX = pan0.x + m.x - start.x; view.panY = pan0.y + m.y - start.y } }
        CanvasCursor { kind: parent.pressed ? "hand-grab" : "hand" }
    }

    Rectangle {                             // floats over the blocks: a panel of its own, so it never reads as part of one
        x: Theme.pad; y: Theme.pad
        width: addButton.width + 8; height: addButton.height + 8
        radius: Theme.radiusPanel
        color: Theme.panel; border.color: Theme.popupEdge
        Button {
            id: addButton
            objectName: "blockAddButton"
            x: 4; y: 4
            kind: "ghost"
            text: "+ Add block"
            onClicked: view.openAddAtCentre()
        }
    }
    EmptyHint {
        visible: view.blocks.length === 0
        anchors.centerIn: parent; width: 320
        text: "No blocks yet. Press Tab or right-click to add one."
    }

    BlockAddList {
        id: addList
        parent: QQC.Overlay.overlay         // the window's room, not the panel's: a short panel never squeezes it
        from: view
        catalogue: view.catalogue
        converts: view.converts
        kindColours: view.kindColours
        onChosen: (type) => {
            const from = view.addFrom
            view.addFrom = ""
            let x = view.addAt.x, y = view.addAt.y
            const e = view.catalogue.find(c => c.type === type)
            if (from && e) {                // its wired input level with the drop, a little right of it
                const ins = e.inputs || [], name = Blocks.firstInput(e, addList.fromKind, view.converts)
                const row = (e.outputs || []).length + Math.max(0, ins.findIndex(p => p.name === name))
                x += 24; y -= Blocks.HEADER + Blocks.LINE + Blocks.TOP + row * Blocks.ROW + Blocks.ROW / 2
            }
            view.addRequested(type, Math.round(x), Math.round(y), from)
        }
        onClosed: { if (view.wireParked) view.cancelWire(); view.forceActiveFocus() }
    }
}
