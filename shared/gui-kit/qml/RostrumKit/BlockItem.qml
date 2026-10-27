import QtQuick
import RostrumCursors 1.0
import "."
import "Blocks.js" as Blocks

// One block of a BlockView: the header (its label), a grey summary line ("Scale 8") with the note at its right ("Final
// only"), then a row per port: outputs at the right edge, inputs at the left, each a small circle in its kind's colour.
// Pressing the block picks it; dragging it moves it (drawn here, `moved` sent once at the release). Pressing a port
// starts a wire (BlockView does the wiring). Lives in the view's canvas, so x / y / sizes are canvas units.
Item {
    id: blk
    required property string bid
    property var view                       // the BlockView
    readonly property var d: view.byId[bid] || ({ id: bid, inputs: [], outputs: [], x: 0, y: 0, label: "" })
    property real hx: NaN                   // where a drag holds it, until the app's data says where it is
    property real hy: NaN
    property bool dragging: false
    objectName: "block:" + bid
    x: isNaN(hx) ? d.x : hx
    y: isNaN(hy) ? d.y : hy
    z: dragging ? 3 : view.selected === bid ? 2 : 1
    width: Blocks.WIDTH
    height: Blocks.height(d)
    onDChanged: { hx = NaN; hy = NaN }      // new data from the app: its place wins

    // a port's centre in canvas units (BlockWire ends bind to these, so a move redraws only this block's wires)
    function portX(side) { return x + (side === "out" ? Blocks.WIDTH : 0) }
    function portY(side, name) { const p = Blocks.portAt(d, side, name); return y + (p ? p.y : 0) }

    Rectangle {                             // the body
        anchors.fill: parent
        radius: Theme.radiusPanel
        color: Theme.panel
        border.width: view.selected === blk.bid ? 1.5 : 1
        border.color: view.selected === blk.bid ? Theme.accent : body.containsMouse ? Theme.lineHover : Theme.line
    }
    Rectangle {                             // the header: a step lighter, square where it meets the body
        id: header
        objectName: "blockHeader:" + blk.bid
        x: 1; y: 1; width: parent.width - 2; height: Blocks.HEADER - 1
        topLeftRadius: Theme.radiusPanel - 1; topRightRadius: Theme.radiusPanel - 1
        color: Theme.raised
        Text {
            anchors.left: parent.left; anchors.right: parent.right; anchors.leftMargin: 10; anchors.rightMargin: 10
            anchors.verticalCenter: parent.verticalCenter
            text: blk.d.label; elide: Text.ElideRight
            color: Theme.fg; font.family: uiFont; font.pixelSize: Theme.body; font.weight: Font.DemiBold
            font.hintingPreference: Font.PreferNoHinting
        }
    }
    Item {                                  // summary (left, elided) and note (right)
        visible: Blocks.hasLine(blk.d)
        x: 10; y: Blocks.HEADER + 2; width: parent.width - 20; height: Blocks.LINE
        Text {
            id: note
            anchors.right: parent.right; anchors.verticalCenter: parent.verticalCenter
            text: blk.d.note || ""; visible: text !== ""
            color: Theme.warn; font.family: uiFont; font.pixelSize: Theme.label; font.hintingPreference: Font.PreferNoHinting
        }
        Text {
            anchors.left: parent.left; anchors.verticalCenter: parent.verticalCenter
            anchors.right: note.visible ? note.left : parent.right; anchors.rightMargin: note.visible ? Theme.gap : 0
            text: blk.d.summary || ""; elide: Text.ElideRight
            color: Theme.fg3; font.family: uiFont; font.pixelSize: Theme.label; font.features: { "tnum": 1 }
            font.hintingPreference: Font.PreferNoHinting
        }
    }

    MouseArea {                             // press = pick; drag = move (4 px first, so a click moves nothing)
        id: body
        anchors.fill: parent
        hoverEnabled: true
        acceptedButtons: Qt.LeftButton | Qt.RightButton
        preventStealing: true
        property point start
        property point at0
        onPressed: (m) => {
            view.forceActiveFocus(); view.cancelled = false
            view.picked(blk.bid)
            start = mapToItem(view, m.x, m.y); at0 = Qt.point(blk.x, blk.y)
        }
        onPositionChanged: (m) => {
            if (!pressed || !(pressedButtons & Qt.LeftButton) || view.cancelled) return
            const p = mapToItem(view, m.x, m.y)
            if (!blk.dragging && Math.abs(p.x - start.x) + Math.abs(p.y - start.y) < 4) return
            blk.dragging = true; view.draggingBlock = blk
            blk.hx = at0.x + (p.x - start.x) / view.zoom
            blk.hy = at0.y + (p.y - start.y) / view.zoom
        }
        onReleased: {
            if (!blk.dragging) return
            blk.dragging = false; view.draggingBlock = null
            view.moved(blk.bid, Math.round(blk.hx), Math.round(blk.hy))
        }
        onCanceled: blk.cancelDrag()
        CanvasCursor { kind: "pick" }
    }
    function cancelDrag() { dragging = false; hx = NaN; hy = NaN; if (view.draggingBlock === blk) view.draggingBlock = null }

    Repeater {
        model: blk.d.outputs || []
        delegate: BlockPort { view: blk.view; block: blk; side: "out"; row: index }
    }
    Repeater {
        model: blk.d.inputs || []
        delegate: BlockPort { view: blk.view; block: blk; side: "in"; row: (blk.d.outputs || []).length + index }
    }
}
