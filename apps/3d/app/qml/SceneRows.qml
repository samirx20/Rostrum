import QtQuick
import RostrumKit

// The timeline's rows, which are the scene list too (backend.layers, screen3d/outline.py): an item's row, then, while
// it is selected, a second line where two of its animations overlap and a row per animated setting; children and an
// import's parts indented under their item. Each row is its name (SceneName.qml) and the kit's track (LayerTrack.qml:
// the bar from first key to last, the keys as diamonds, the stretches between two keys to click). The track sits under
// the ruler, at ruler.x - 8 like the ruler's 8 px room for a key at 0.
ListView {
    id: list
    property Item ruler
    property int labelWidth: 240
    model: backend.layers
    spacing: 2; clip: true; boundsBehavior: Flickable.StopAtBounds

    // the kit's hooks (LayerTimeline.qml, LayerTrack.qml): the item menu at (px, py) in the list's px, a row's middle
    // for the drag label, and the box that picks keys
    function openMenu(id, px, py) { backend.select(id); itemMenu.openAt(list, px === undefined ? Theme.gap * 4 : px, py === undefined ? 0 : py, id) }
    function rowMid(id) {
        const item = itemAtIndex(model.findIndex(r => r.id === id))
        return item ? item.y - contentY + item.height / 2 : -1
    }
    function boxStart(p) { keyBox.start(p) }
    function boxTo(p) { keyBox.to(p) }
    function boxEnd(how) { keyBox.end(how) }
    KeyBox { id: keyBox; list: list; ruler: list.ruler }
    ContextMenu3D { id: itemMenu }
    Connections {   // the selected item's row scrolls into view (picked in the viewport, by a stretch, by a step)
        target: backend
        function onOutlineChanged() {
            const rows = backend.layers, i = rows.findIndex(r => r.id === backend.selectedOwner)
            let last = i                                   // its own setting rows under it come into view too
            while (last + 1 < rows.length && rows[last + 1].owner === backend.selectedOwner) last++
            if (i >= 0) Qt.callLater(() => { list.positionViewAtIndex(last, ListView.Contain); list.positionViewAtIndex(i, ListView.Contain) })
        }
    }

    delegate: Item {
        id: row
        required property var modelData
        width: ListView.view.width
        height: modelData.row === "field" && !modelData.line ? Theme.rowDense - 2 : Theme.rowDense   // a second line: as tall as its item's
        SceneName { x: Theme.grid; width: list.labelWidth - Theme.grid; height: row.height; modelData: row.modelData; menu: itemMenu }
        LayerTrack {
            objectName: "track:" + row.modelData.id
            x: list.ruler.x - 8; width: list.ruler.width + 16; height: row.height
            rowData: row.modelData; ruler: list.ruler; rows: list
        }
    }
}
