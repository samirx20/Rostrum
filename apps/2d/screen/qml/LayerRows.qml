import QtQuick
import RostrumKit

// The timeline's rows, which are the layers list too (backend.layers, screen2d/outline.py): a layer row, then, while
// it is open, a row per animated setting, its effects and masks, and its own layers, indented. Each row is a name
// (LayerName.qml: select, fold, rename, menu, drag to reorder) and a track (LayerTrack.qml: bar, keys, frames).
// Pulling a name up or down moves the layer: above or below a row, or into a group (backend.moveLayer).
// x is the timeline's own (the track sits under the ruler, at ruler.x - 8 like the ruler's 8 px room for a key at 0).
ListView {
    id: list
    objectName: "layersList"            // (the scripted steps show a drop in progress through it)
    property Item ruler
    property int labelWidth: 240
    property bool compact: false        // only the selected layer's row (or the first layer's, when none is selected)
    readonly property string shownLayer: backend.selectedLayer || (backend.layers.length ? backend.layers[0].id : "")
    model: compact ? backend.layers.filter(r => r.row === "layer" && r.id === shownLayer) : backend.layers
    interactive: !compact
    spacing: 2
    clip: true
    boundsBehavior: Flickable.StopAtBounds

    // Right-click menu of a layer: what applies to the selection (backend.layerMenu: an unselected layer is selected
    // alone first), the same list as Ctrl+K and the context bar. (px, py) in the list's px; the kit menu opens in the window's.
    function openMenu(id, px, py) {
        const item = itemAtIndex(backend.layers.findIndex(r => r.id === id))
        const entries = backend.layerMenu(id)
        if (!entries.length) return
        const g = list.mapToItem(null, px === undefined ? Theme.gap * 4 : px,
                                 py === undefined ? (item ? item.y - contentY + item.height : 0) : py)
        menu.entries = entries
        menu.openAt(g.x, g.y)
    }
    ActionMenu { id: menu; onPicked: (key) => backend.run(key) }
    function rowMid(id) {          // the middle of a row in the list's px (-1: not shown), for the drag label
        const item = itemAtIndex(model.findIndex(r => r.id === id))
        return item ? item.y - contentY + item.height / 2 : -1
    }

    // drag-to-reorder: the dragged row, and where it would land (the row, above | below | into a group)
    property string dragId: ""
    property string dropRow: ""
    property string dropWhere: ""
    function dropAt(y) {
        let i = indexAt(labelWidth / 2, y)
        if (i < 0) i = indexAt(labelWidth / 2, y - 3)
        const rows = backend.layers
        const item = i < 0 ? null : itemAtIndex(i)
        if (i < 0 || !item || rows[i].owned || rows[i].id === dragId) { dropRow = ""; return }
        const f = (y - item.y) / item.height
        const holds = rows[i].kind === "group" || rows[i].kind === "rig"
        dropRow = rows[i].id
        dropWhere = holds && f > 0.25 && f < 0.75 ? "into" : f < 0.5 ? "above" : "below"
    }
    function finishDrag() {
        if (dragId !== "" && dropRow !== "") backend.moveLayer(dragId, dropRow, dropWhere)
        dragId = ""; dropRow = ""
    }
    Rectangle {  // the drop line (between rows), or an outline round a group the layer would go into
        readonly property var target: list.dropRow === "" ? null : list.itemAtIndex(backend.layers.findIndex(r => r.id === list.dropRow))
        visible: target !== null
        z: 5
        x: Theme.gap; width: list.width - x
        y: !target ? 0 : list.dropWhere === "into" ? target.y : list.dropWhere === "above" ? target.y - 2 : target.y + target.height
        height: list.dropWhere === "into" ? (target ? target.height : 0) : 2
        radius: list.dropWhere === "into" ? Theme.radiusCtl : 1
        color: list.dropWhere === "into" ? "transparent" : Theme.accent
        border.color: Theme.accent; border.width: list.dropWhere === "into" ? 2 : 0
    }

    // box-pick keys (INTERACTION 1.3: a box picks what it touches): drawn from an empty part of a track (LayerTrack.qml);
    // on release every key whose diamond lies inside it, on every row it crosses, is picked (Ctrl / Shift: added)
    property rect box: Qt.rect(0, 0, 0, 0)
    property bool boxing: false
    property point boxFrom
    function boxStart(p) { boxFrom = p; box = Qt.rect(p.x, p.y, 0, 0); boxing = true }
    function boxTo(p) { box = Qt.rect(Math.min(p.x, boxFrom.x), Math.min(p.y, boxFrom.y), Math.abs(p.x - boxFrom.x), Math.abs(p.y - boxFrom.y)) }
    function boxEnd(how) {
        boxing = false
        if (how === "cancel") return
        const groups = [], rows = backend.layers
        for (let i = 0; i < rows.length; i++) {
            const item = itemAtIndex(i)
            if (!item) continue
            const y = item.y                        // the box is in the list's content px, as the rows
            if (y + item.height < box.y || y > box.y + box.height) continue
            for (const k of rows[i].keys) {
                const x = ruler.x + ruler.xOf(k.t)
                if (x >= box.x - 4 && x <= box.x + box.width + 4) groups.push(k.ids || [k.id])
            }
        }
        backend.keys.box(groups, how)
    }
    Rectangle {
        visible: list.boxing; z: 6
        x: list.box.x; y: list.box.y; width: list.box.width; height: list.box.height
        color: Qt.rgba(Theme.accent.r, Theme.accent.g, Theme.accent.b, 0.12); border.color: Theme.accent; border.width: 1
    }

    footer: SoundRow {   // the project's sound, the last row (only when there is sound; kept in compact)
        width: ListView.view.width; ruler: list.ruler; labelWidth: list.labelWidth
        y: list.spacing
    }

    delegate: Item {
        id: row
        required property var modelData
        width: ListView.view.width
        height: modelData.row === "layer" ? Theme.row : Theme.rowDense - 2
        opacity: list.dragId === modelData.id ? 0.45 : 1
        LayerName {
            x: Theme.gap; width: list.labelWidth - Theme.gap; height: parent.height
            rowData: row.modelData; rows: list
        }
        Repeater {   // an agent just changed this row's item: the 1-second outline
            model: backend.agent.flash.indexOf(row.modelData.id) >= 0 ? 1 : 0
            ChangeOutline { x: Theme.gap; width: list.labelWidth - Theme.gap; height: row.height }
        }
        LayerTrack {
            x: list.ruler.x - 8; width: list.ruler.width + 16; height: parent.height
            rowData: row.modelData; ruler: list.ruler; rows: list
        }
    }
}
