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
    cacheBuffer: 200                    // only the rows in view and a few past it are built: a change to every row (a Stagger of
                                        // 200 layers) updates those, not all 200 (~120 -> ~10 ms a step); a row scrolled into view
                                        // is a kept one given its data (reuseItems), so a pick that scrolls the list stays flat.
                                        // A key box passing rows that scroll away keeps them itself (KeyBox.qml).
    reuseItems: true                    // rows scrolled out are kept and given the next row's data, never made anew: a pick
                                        // far down the list made every row there (~3 ms each), more the further the list had
                                        // scrolled (a grab among 200 layers grew 70 -> 230 ms over 17 picks; now flat)
    boundsBehavior: Flickable.StopAtBounds

    // Right-click menu of a layer: what applies to the selection (backend.layerMenu: an unselected layer is selected
    // alone first), the same list as Ctrl+K and the context bar. (px, py) in the list's px; the kit menu opens in the window's.
    function openMenu(id, px, py) {
        const item = itemAtIndex(list.model.indexOf(id))
        const entries = backend.layerMenu(id)
        if (!entries.length) return
        const g = list.mapToItem(null, px === undefined ? Theme.gap * 4 : px,
                                 py === undefined ? (item ? item.y - contentY + item.height : 0) : py)
        menu.entries = entries
        menu.openAt(g.x, g.y)
    }
    ActionMenu { id: menu; onPicked: (key) => backend.run(key) }
    // the list follows the pick: a layer picked anywhere (the canvas, Tab, Ctrl+K) brings its row into view, the last
    // picked one; a row already in view stays put (ListView.Contain), so a click in the list never scrolls it. A pick
    // of several (Ctrl+A, a range, the rubber band) leaves the list where it is: every picked row is lit, and jumping to
    // the last one lost the person's place (and made the rows at the bottom: ~80 ms at 200 layers).
    // Rows are found through the model (indexOf, at: rostrum_gui/rows_model.py), never by reading backend.layers:
    // that made every row, keys and frames too, into script objects (~100 ms a pick at 200 layers).
    function follow() {
        if (list.compact || list.dragId !== "") return
        const sel = backend.selection
        const i = sel.length === 1 ? list.model.indexOf(sel[0]) : -1
        if (i >= 0) list.positionViewAtIndex(i, ListView.Contain)
    }
    // With the pick's panel, not the pick: a press that picks and drags a layer scrolls the list at the drop (or a
    // 0.1 s rest), never in the drag's first frames (panel_hold.py).
    Connections { target: backend; function onPanelShown() { Qt.callLater(list.follow) } }
    function rowMid(id) {          // the middle of a row in the list's px (-1: not shown), for the drag label
        for (let i = 0; i < count; i++) {
            const item = itemAtIndex(i)
            if (item && item.modelData.id === id) return item.y - contentY + item.height / 2
        }
        return -1
    }

    // drag-to-reorder: the dragged row, and where it would land (the row, above | below | into a group). One gesture from
    // the pull to the drop (backend.rowDrag, row_drag.py): one undo step; Esc while held puts it back.
    property string dragId: ""
    property string dropRow: ""
    property string dropWhere: ""
    property var dragRow: null          // the pulled row's data (its ghost shows its icon and name)
    property real grabDy: 0             // where in the row it was grabbed: the ghost keeps that point under the pointer
    property real dragY: 0              // the pointer, in the list's content px
    // The rows part where it would land (Figma's layer list): the pulled row's place closes and a row-high gap opens
    // before `gapAt` (the list index the row goes in front of), the rows sliding there (Theme.rowEase). The rows' own
    // places (y) never move, so where the pointer is points at the same row whatever has slid; at the drop the list
    // takes its new order with nothing sliding. "into" a group: no gap, the group's outline.
    readonly property int dragIndex: dragId === "" ? -1 : model.indexOf(dragId)
    readonly property int gapAt: dragId === "" || dropRow === "" || dropWhere === "into" ? -1
                                 : model.indexOf(dropRow) + (dropWhere === "below" ? 1 : 0)
    property real dragH: Theme.row      // the pulled row's height: the gap's
    function partBy(i, h) {          // how far row i slides while a row is pulled
        if (gapAt < 0 || i === dragIndex) return 0
        return (i > dragIndex ? -h : 0) + (i >= gapAt ? h : 0)
    }
    function beginDrag(r, pressY) {
        if (!backend.rowDrag.begin(r.id)) return
        const it = itemAtIndex(model.indexOf(r.id))
        dragH = it ? it.height : Theme.row
        dragRow = r; grabDy = pressY; dragId = r.id
    }
    function cancelDrag() { backend.rowDrag.cancelDrag(); dragId = ""; dropRow = ""; dragRow = null }
    Connections { target: backend.rowDrag; function onCancelled() { list.dragId = ""; list.dropRow = ""; list.dragRow = null } }
    function dropAt(y) {
        dragY = y
        let i = indexAt(labelWidth / 2, y)
        if (i < 0) i = indexAt(labelWidth / 2, y - 3)
        const item = i < 0 ? null : itemAtIndex(i)
        const r = item ? item.modelData : null
        if (!r || r.owned || r.frame || r.id === dragId) { dropRow = ""; return }
        const f = (y - item.y) / item.height
        const holds = r.kind === "group" || r.kind === "rig"
        dropRow = r.id
        dropWhere = holds && f > 0.25 && f < 0.75 ? "into" : f < 0.5 ? "above" : "below"
    }
    function finishDrag() {
        if (dragId !== "") backend.rowDrag.drop(dropRow, dropWhere)      // no row under it: nothing changes
        dragId = ""; dropRow = ""; dragRow = null
    }
    // press an eye or a lock and drag over more rows: the first row's new state shows on every row the pointer passed,
    // live (only here, in the list); ONE change on release (backend.setSwitches), so one Ctrl+Z puts them all back
    property string swipeField: ""      // "locked" | "hidden" while a swipe runs
    property bool swipeOn: false
    property var swipeIds: ({})
    property int swipeFrom: -1
    property int swipeLast: -1
    function swipeBegin(id, field, on) {
        swipeFrom = list.model.indexOf(id); swipeLast = swipeFrom
        swipeField = field; swipeOn = on; const m = {}; m[id] = true; swipeIds = m
    }
    function swipeTo(y) {              // y in the list's content px
        let i = indexAt(labelWidth / 2, y)
        if (i < 0) i = indexAt(labelWidth / 2, y - 3)
        if (i < 0) i = y < 0 ? 0 : count - 1
        if (i === swipeLast) return
        swipeLast = i
        const m = {}
        for (let k = Math.min(i, swipeFrom); k <= Math.max(i, swipeFrom); k++) {
            const r = list.model.at(k)
            if (r.row === "layer" && (swipeField === "locked" || !r.frame)) m[r.id] = true
        }
        swipeIds = m
    }
    function swipeEnd() {
        if (swipeField !== "") backend.setSwitches(Object.keys(swipeIds), swipeField, swipeOn)
        swipeField = ""; swipeIds = ({}); swipeFrom = -1; swipeLast = -1
    }
    Rectangle {  // the pulled row, under the pointer where it was grabbed (its place in the list stays, dimmed)
        objectName: "rowDragGhost"
        visible: list.dragRow !== null
        z: 6
        x: Theme.gap; width: list.labelWidth - Theme.gap; height: Theme.row
        y: list.dragY - list.grabDy          // (a list's own children lie in its content, as the drop line does)
        radius: Theme.radiusCtl; color: Theme.raised; border.width: 1; border.color: Theme.accent; opacity: 0.92
        LayerIcon { id: ghostIcon; x: Theme.gap + ((list.dragRow && list.dragRow.depth) || 0) * 16 + 16; anchors.verticalCenter: parent.verticalCenter
                    kind: (list.dragRow && list.dragRow.kind) || "shape"; shape: (list.dragRow && list.dragRow.shape) || "rect"; ink: Theme.fg2 }
        Text { x: ghostIcon.x + ghostIcon.width + Theme.gap; anchors.verticalCenter: parent.verticalCenter; width: parent.width - x - Theme.gap
               text: list.dragRow ? list.dragRow.label : ""; elide: Text.ElideRight; color: Theme.fg; font.family: uiFont; font.pixelSize: Theme.label }
    }
    Rectangle {  // the drop line (between rows), or an outline round a group the layer would go into. A local stand-in
        objectName: "rowInsertLine"    // for the kit's InsertLine (K5, not in main yet): swap it in here
        readonly property var target: list.dropRow === "" ? null : list.itemAtIndex(list.model.indexOf(list.dropRow))
        visible: target !== null && list.dropWhere === "into"      // between rows the opened gap shows the place
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
        required property int index
        width: ListView.view.width
        transform: Translate {
            y: list.partBy(row.index, list.dragH)
            Behavior on y { enabled: list.dragId !== ""; NumberAnimation { duration: Theme.rowEase; easing.type: Theme.revealEasing } }
        }
        readonly property real own: modelData.row === "layer" || modelData.line ? Theme.row : Theme.rowDense - 2   // a layer's second line: as tall
        readonly property var sound: modelData.row === "layer" ? backend.soundtrack.videos.rows[modelData.id] : undefined
        height: own + (sound ? Theme.rowDense - 2 : 0)     // a video with sound: its sound's row under it (VideoSoundRow)
        opacity: list.dragId !== modelData.id ? 1 : list.gapAt >= 0 ? 0 : 0.45     // gone from its place while a gap is open
        property bool parked: false        // kept out of view for the next row (reuseItems): hidden, so no check sees it
        visible: !parked
        ListView.onPooled: { parked = true; rowName.endRename(false); rowTrack.release() }     // nothing of the row it was stays
        ListView.onReused: parked = false
        LayerName {
            id: rowName
            x: Theme.gap; width: list.labelWidth - Theme.gap; height: row.own
            rowData: row.modelData; rows: list
        }
        Repeater {   // an agent just changed this row's item: the 1-second outline
            model: backend.agent.flash.indexOf(row.modelData.id) >= 0 ? 1 : 0
            ChangeOutline { x: Theme.gap; width: list.labelWidth - Theme.gap; height: row.own }
        }
        LayerTrack {
            id: rowTrack
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
