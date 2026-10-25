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
    readonly property var lit: backend.multi.lit     // how each row is lit: read once here per pick, not by every row
    property bool compact: false        // only the selected layer's row (or the first layer's, when none is selected)
    model: compact ? backend.rowsCompact : backend.rowsModel     // list models that change row by row (timeline_rows.py): a row and the key under the pointer live as long as their item
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
    // the list follows the pick: a layer picked anywhere (the canvas, Tab, Ctrl+K) brings its row into view, the last
    // picked one; a row already in view stays put (ListView.Contain), so a click in the list never scrolls it
    function follow() {
        const sel = backend.selection
        const i = sel.length ? backend.layers.findIndex(r => r.id === sel[sel.length - 1]) : -1
        if (i >= 0 && !list.compact && list.dragId === "") list.positionViewAtIndex(i, ListView.Contain)
    }
    Connections { target: backend; function onSelectedItemsChanged() { Qt.callLater(list.follow) } }
    function rowMid(id) {          // the middle of a row in the list's px (-1: not shown), for the drag label
        for (let i = 0; i < count; i++) {
            const item = itemAtIndex(i)
            if (item && item.modelData.id === id) return item.y - contentY + item.height / 2
        }
        return -1
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
        if (i < 0 || !item || rows[i].owned || rows[i].frame || rows[i].id === dragId) { dropRow = ""; return }
        const f = (y - item.y) / item.height
        const holds = rows[i].kind === "group" || rows[i].kind === "rig"
        dropRow = rows[i].id
        dropWhere = holds && f > 0.25 && f < 0.75 ? "into" : f < 0.5 ? "above" : "below"
    }
    function finishDrag() {
        if (dragId !== "" && dropRow !== "") backend.moveLayer(dragId, dropRow, dropWhere)
        dragId = ""; dropRow = ""
    }
    // press an eye or a lock and drag over more rows: the first row's new state shows on every row the pointer passed,
    // live (only here, in the list); ONE change on release (backend.setSwitches), so one Ctrl+Z puts them all back
    property string swipeField: ""      // "locked" | "hidden" while a swipe runs
    property bool swipeOn: false
    property var swipeIds: ({})
    property int swipeFrom: -1
    property int swipeLast: -1
    function swipeBegin(id, field, on) {
        swipeFrom = backend.layers.findIndex(r => r.id === id); swipeLast = swipeFrom
        swipeField = field; swipeOn = on; const m = {}; m[id] = true; swipeIds = m
    }
    function swipeTo(y) {              // y in the list's content px
        let i = indexAt(labelWidth / 2, y)
        if (i < 0) i = indexAt(labelWidth / 2, y - 3)
        if (i < 0) i = y < 0 ? 0 : count - 1
        if (i === swipeLast) return
        swipeLast = i
        const rows = backend.layers, m = {}
        for (let k = Math.min(i, swipeFrom); k <= Math.max(i, swipeFrom); k++)
            if (rows[k].row === "layer" && (swipeField === "locked" || !rows[k].frame)) m[rows[k].id] = true
        swipeIds = m
    }
    function swipeEnd() {
        if (swipeField !== "") backend.setSwitches(Object.keys(swipeIds), swipeField, swipeOn)
        swipeField = ""; swipeIds = ({}); swipeFrom = -1; swipeLast = -1
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

    // box-pick keys (the kit's KeyBox.qml): drawn from an empty part of a track (LayerTrack.qml)
    function boxStart(p) { keyBox.start(p) }
    function boxTo(p) { keyBox.to(p) }
    function boxEnd(how) { keyBox.end(how) }
    KeyBox { id: keyBox; objectName: "keyBox"; list: list; ruler: list.ruler }
    footer: SoundRow {   // the project's sound, the last row (only when there is sound; kept in compact)
        width: ListView.view.width; ruler: list.ruler; labelWidth: list.labelWidth
        y: list.spacing
    }

    delegate: Item {
        id: row
        required property var modelData
        width: ListView.view.width
        readonly property real own: modelData.row === "layer" || modelData.line ? Theme.row : Theme.rowDense - 2   // a layer's second line: as tall
        readonly property var sound: modelData.row === "layer" ? backend.soundtrack.videos.rows[modelData.id] : undefined
        height: own + (sound ? Theme.rowDense - 2 : 0)     // a video with sound: its sound's row under it (VideoSoundRow)
        opacity: list.dragId === modelData.id ? 0.45 : 1
        LayerName {
            x: Theme.gap; width: list.labelWidth - Theme.gap; height: row.own
            rowData: row.modelData; rows: list
        }
        Repeater {   // an agent just changed this row's item: the 1-second outline
            model: backend.agent.flash.indexOf(row.modelData.id) >= 0 ? 1 : 0
            ChangeOutline { x: Theme.gap; width: list.labelWidth - Theme.gap; height: row.own }
        }
        LayerTrack {
            x: list.ruler.x - 8; width: list.ruler.width + 16; height: row.own
            rowData: row.modelData; ruler: list.ruler; rows: list
            cells: Component { FrameMarks {   // a drawing's cells
                frames: row.modelData.frames || []; again: row.modelData.again || []; keys: row.modelData.keys || []
                drawing: row.modelData.row === "layer" && (row.modelData.kind === "drawing" || (row.modelData.frames || []).length > 0)
                trims: row.modelData.trim === true; layerStart: row.modelData.start || 0; layerEnd: row.modelData.end === undefined ? 1e9 : row.modelData.end
                timeRuler: list.ruler; owner: row.modelData.owner } }
        }
        Loader {   // the video's own sound, tied to the bar above (screen2d/video_sound.py)
            active: row.sound !== undefined
            y: row.own; width: parent.width; height: Theme.rowDense - 2
            sourceComponent: VideoSoundRow { rowData: row.modelData; info: row.sound; ruler: list.ruler; labelWidth: list.labelWidth }
        }
    }
}
