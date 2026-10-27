import QtQuick
import QtQuick.Window
import RostrumKit

// The block view on a toy material graph (demo/blocks_preview.py's `toy`): every request goes to the toy and comes
// back as new data, as an app's document would.
Window {
    width: 1646; height: 900
    visible: true
    color: Theme.app
    title: "Blocks"
    BlockView {
        id: blocks
        anchors.fill: parent
        focus: true
        catalogue: toy.catalogue
        blocks: toy.blocks
        wires: toy.wires
        selected: toy.selected
        kindColours: toy.kindColours
        converts: toy.converts
        onAddRequested: (type, x, y, fromPort) => toy.add(type, x, y, fromPort)
        onMoved: (id, x, y) => toy.move(id, x, y)
        onConnectRequested: (from, to) => toy.connect(from, to)
        onDisconnectRequested: (to) => toy.disconnect(to)
        onRemoveRequested: (ids) => toy.remove(ids)
        onPicked: (id) => toy.pick(id)
    }
}
