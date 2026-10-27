import QtQuick
import RostrumCursors 1.0
import "."
import "Blocks.js" as Blocks

// One port row of a BlockItem: its label and its circle on the block's edge (outputs right, inputs left), coloured by
// kind. While a wire is being drawn the ports it may reach light up and the rest dim (BlockView.portState). Pressing
// the circle starts a wire; pressing a wired input picks its wire end up (move it, or drop it on nothing to unwire).
Item {
    id: port
    required property var modelData
    required property int index
    property var view
    property var block
    property string side: "in"
    property int row: 0
    readonly property string key: block.bid + "." + modelData.name
    readonly property int look: view.portState(block.bid, side, modelData.name, modelData.kind)    // 0 rest, 1 lit, 2 dim
    readonly property color colour: view.kindColours[modelData.kind] || Theme.fg4
    objectName: "port:" + block.bid + ":" + side + ":" + modelData.name
    x: side === "out" ? Blocks.WIDTH - width / 2 : -width / 2
    y: Blocks.rowsTop(block.d) + row * Blocks.ROW
    width: 22; height: Blocks.ROW
    z: 1
    opacity: look === 2 ? 0.3 : 1

    Text {
        anchors.verticalCenter: parent.verticalCenter
        anchors.left: port.side === "in" ? parent.horizontalCenter : undefined
        anchors.right: port.side === "out" ? parent.horizontalCenter : undefined
        anchors.leftMargin: 10; anchors.rightMargin: 10
        width: Blocks.WIDTH - 20; elide: Text.ElideRight
        horizontalAlignment: port.side === "out" ? Text.AlignRight : Text.AlignLeft
        text: port.modelData.label
        color: port.look === 1 ? Theme.fg : Theme.fg2; font.family: uiFont; font.pixelSize: Theme.label
        font.hintingPreference: Font.PreferNoHinting          // the canvas is scaled: hinted letters left gaps in words
    }
    Rectangle {                             // lit: a ring around it, the port drawn a size up
        anchors.centerIn: parent
        width: Blocks.PORT + 8; height: width; radius: width / 2
        color: "transparent"; border.width: 1.5; border.color: Theme.fg
        visible: port.look === 1 && view.wireOver === port.side + ":" + port.key
    }
    Rectangle {
        anchors.centerIn: parent
        readonly property real size: port.look === 1 ? Blocks.PORT + 2 : Blocks.PORT
        width: size; height: size; radius: size / 2
        color: port.colour
    }
    MouseArea {
        anchors.fill: parent
        preventStealing: true
        onPressed: (m) => { view.forceActiveFocus(); view.pressPort(port.block.bid, port.side, port.modelData, mapToItem(view, m.x, m.y)) }
        onPositionChanged: (m) => view.moveWire(mapToItem(view, m.x, m.y))
        onReleased: view.endWire()
        onCanceled: view.cancelWire()
        CanvasCursor { kind: port.side === "in" && port.modelData.linked ? "pick" : "make" }
    }
}
