import QtQuick
import RostrumKit

// The arrangement's tracks (Arrangement.qml puts it in the middle, under its header strip). Markers, the song's sections (when it has any) and a bars/beats ruler on top; one row per track: its header
// (name, mute, solo) and its notes, hits and clips; the playhead and marker lines across every row.
// Select first, then act (LaneInput: click, Ctrl+click, Shift+click, box; drag moves every selected item, one undo
// step, Ctrl = no snapping, Shift = only in time, Alt = a copy). A drag on the ruler is a time range (shaded over
// every lane). Right-click opens the kit's one short menu (backend.actions); the rest is in the settings panel's actions.
// Zoom and scroll: Ctrl + wheel (or a pinch) zooms around the pointer, Shift + wheel or a sideways swipe scrolls,
// Ctrl + / Ctrl - / Ctrl 0 (fit) from the keyboard, a slim scrollbar while zoomed in; playing keeps the playhead
// on screen. The view is backend.viewStart / viewSpan, shared by the ruler, markers, rows and the piano roll.
// A track's "Auto" chip opens its automation lane under the row (AutomationLane): click adds a point, drag moves
// it, Delete removes it; each is one `automation.set`. `slim`: no lanes (unused now).
// Under the tracks: "+ Track" (addTrack: the Sounds panel), then compact rows for the groups (buses) and the master,
// the Master last; they carry their lanes. A ducked track's row shows where its ducks pull it down (DuckDips).
Rectangle {
    id: tl
    property bool slim: false
    readonly property real rowsBottom: list.y + Math.min(list.height, column.height - list.contentY)   // where the rows end (PictureCorner sits under them)
    property real slack: 0                  // height the rows leave free for a folded dock (Arrangement.dockSlack)
    property int headerWidth: 224
    signal addTrack()
    readonly property real addH: slim ? 0 : 28          // the "+ Track" row, between the tracks and the group / master rows
    readonly property var rows: backend.tracks   // in the order of backend.trackRows (the Repeater); buses + master: lanes only
    readonly property real mixH: 20          // a bus's or the master's compact row
    readonly property real groupH: 24        // a group's header row
    readonly property int mixRows: rows.filter(r => r.mix && !r.group).length
    readonly property int groupRows: rows.filter(r => r.group).length
    readonly property real rowGap: 2
    readonly property real laneH: 76         // an open automation lane
    readonly property real laneGap: 2
    readonly property real rulerBottom: bars.y + bars.height   // where the bands and the ruler end
    readonly property int openLanes: slim ? 0 : rows.filter(r => r.auto).length
    // The rows share the room (24-52 px); an automation lane opening or closing never takes it from them: the lane
    // opens under its row and the rows below move down (scrolling when they run out), so the A just clicked, and every
    // row above it, stays under the pointer (INTERACTION.md 1.21; the stability pass checks it).
    readonly property real rowH: rows.length === mixRows + groupRows ? 24
        : Math.max(slim ? 18 : 24, Math.min(slim ? 26 : 52,
              (list.height - slack - addH - mixRows * mixH - groupRows * groupH - rowGap * (rows.length - 1)) / (rows.length - mixRows - groupRows)))
    // A track just added (Library Add or double-click, + Track, an undo bringing one back): its row flashes once and
    // the rows scroll just enough to show it (PLAN S3). Seen as one new track while every track before stays, so
    // opening another song never flashes.
    property var knownIds: null              // the tracks shown before this change (null: none read yet)
    property string arrived: ""              // the row flashing now
    onRowsChanged: {
        var ids = rows.filter(r => !r.mix).map(r => r.id), was = knownIds
        knownIds = ids.reduce((o, i) => { o[i] = true; return o }, {})
        if (was === null) return
        var fresh = ids.filter(i => !was[i]), kept = Object.keys(was).every(i => knownIds[i])
        if (fresh.length === 1 && kept) { arrived = fresh[0]; Qt.callLater(reveal, fresh[0]) }
    }
    function reveal(id) {   // scroll the rows just enough that this one is wholly in view (nothing moves when it is)
        var s = rowSpan(id)
        if (!s) return
        var top = list.y, bottom = list.y + list.height, most = Math.max(0, list.contentHeight - list.height)
        if (s.bottom > bottom) list.contentY = Math.min(most, list.contentY + s.bottom - bottom + Theme.grid)
        else if (s.top < top) list.contentY = Math.max(0, list.contentY - (top - s.top) - Theme.grid)
    }
    // Dragging a track header: where it would land is asked of the backend (group_drag.py), the one rule.
    property string dragId: ""
    property string dropOver: ""            // the row under the pointer
    property string dropWhat: ""            // "join" | "leave" | "" (nothing there)
    property string dropBus: ""
    property bool dropBelow: false          // the pointer is in the lower half of the row: the track goes under it
    property real dragX: 0
    property real dragY: 0
    function dragTo(id, p) {
        dragId = id; dragY = p.y - list.contentY + list.y
        var s = slot(p.y), i = s.i
        dropOver = i >= 0 ? rows[i].id : ""
        dropBelow = i >= 0 && p.y - s.top > hOf(rows[i]) / 2
        var t = dropOver === "" ? "" : backend.dropTarget(dropOver, id)
        dropWhat = t.split(":")[0]; dropBus = t.indexOf(":") >= 0 ? t.split(":")[1] : ""
    }
    function dropAt(id, dropped) {
        if (dropped && dropWhat !== "" && dropOver !== id) backend.dropTracks([id], dropOver, dropBelow)
        dragId = ""; dropOver = ""; dropWhat = ""; dropBus = ""; dropBelow = false
    }
    function autoOf(r) { return slim ? null : r.auto }
    function hOf(r) { return r.group ? groupH : r.mix ? mixH : rowH }
    function bottomMix(r) { return !!r.mix && !r.group }                    // a bus or the master in the compact rows, not a group header
    function addAbove(i) { return i >= 0 && i < rows.length && bottomMix(rows[i]) && (i === 0 || !bottomMix(rows[i - 1])) ? addH : 0 }   // + Track sits above the first mix row (a row going away has index -1)
    function slot(y) {   // which row is at height y of the list: its index, whether y is in its automation lane, where that starts
        var top = 0
        for (var i = 0; i < rows.length; i++) {
            top += addAbove(i)
            if (y < top) return { i: -1, top: 0, lane: false, laneTop: 0 }
            var lane = autoOf(rows[i]) ? laneGap + laneH : 0
            var h = hOf(rows[i])
            if (y < top + h + lane + rowGap / 2)
                return { i: i, top: top, lane: lane > 0 && y >= top + h + laneGap, laneTop: top + h + laneGap }
            top += h + lane + rowGap
        }
        return { i: -1, top: 0, lane: false, laneTop: 0 }
    }
    color: Theme.panel; radius: Theme.radiusPanel; clip: true

    MarkerBand {
        id: band
        x: bars.x; width: bars.width; y: Theme.gap; height: 18; ruler: bars
    }
    SectionBand {
        id: sectionBand
        x: bars.x; width: bars.width; y: band.y + band.height + 2; height: visible ? 18 : 0; ruler: bars
    }
    SongBand {   // tempo and key changes (when the song has any); a clear gap under the sections, so a range drawn
        id: songBand  // on the ruler a little too high never catches a section (each band its own pointer target)
        x: bars.x; width: bars.width; y: sectionBand.y + sectionBand.height + (sectionBand.visible ? 6 : 0)
        height: visible ? 16 : 0; ruler: bars
    }
    BarRuler {
        id: bars
        x: tl.headerWidth + Theme.gap * 2; width: tl.width - x - Theme.pad
        y: songBand.y + songBand.height + (songBand.visible ? 2 : 0); height: implicitHeight
    }
    Flickable {
        id: list
        anchors { left: parent.left; right: parent.right; top: bars.bottom; bottom: parent.bottom
                  leftMargin: Theme.gap; rightMargin: Theme.pad; topMargin: Theme.grid
                  bottomMargin: Theme.gap + scrollbar.height + Theme.grid }   // room kept: rows never move when it shows
        contentHeight: column.height; clip: true; boundsBehavior: Flickable.StopAtBounds; interactive: false
        Column {
            id: column
            z: 1      // above the lanes' mouse area: the chips and headers take their own clicks, the rest falls through
            width: list.width; spacing: tl.rowGap
            Repeater {   // keyed by track id (backend.trackRows): a change redraws a row in place, never makes every row again
                id: rowItems
                model: backend.trackRows
                delegate: Item {
                    id: row
                    readonly property alias lane: laneBlocks
                    required property var track
                    required property var blocks
                    required property int index
                    readonly property var modelData: track
                    readonly property var auto: tl.autoOf(modelData)
                    readonly property real h: tl.hOf(modelData)
                    readonly property real top0: tl.addAbove(index)
                    width: column.width; height: top0 + h + (auto ? tl.laneGap + tl.laneH : 0)
                    Loader {   // just added: the row (header and lane) flashes once in the accent and fades over a second
                        active: tl.arrived !== "" && tl.arrived === row.modelData.id
                        y: row.top0; width: parent.width; height: row.h; z: 2
                        sourceComponent: Rectangle {
                            objectName: "arrivedFlash"
                            color: Qt.rgba(Theme.accent.r, Theme.accent.g, Theme.accent.b, 0.18); radius: Theme.radiusCtl
                            border.width: 2; border.color: Theme.accent
                            enabled: false
                            NumberAnimation on opacity { from: 1; to: 0; duration: 1000; easing.type: Easing.InQuad
                                                         onFinished: if (tl.arrived === row.modelData.id) tl.arrived = "" }
                        }
                    }
                    Loader {   // + Track: made only in the rows that show it
                        active: row.top0 > 0 && backend.tracks.some(r => !r.mix)
                        x: Theme.grid; y: item ? (row.top0 - item.height) / 2 - tl.rowGap / 2 : 0
                        sourceComponent: Button { text: "+ Track"; kind: "ghost"; height: Theme.field; onClicked: tl.addTrack() }
                    }
                    TrackHeader { visible: !row.modelData.mix; x: (row.modelData.depth || 0) * 14; y: row.top0
                                  width: tl.headerWidth - x; height: row.h; track: row.modelData; showAuto: !tl.slim
                                  dragging: tl.dragId === row.modelData.id
                                  onMenuWanted: (px, py) => tl.openMenu(backend.itemMenu(row.modelData.id), mapToItem(tl, px, py))
                                  onDragMoved: (px, py) => tl.dragTo(row.modelData.id, mapToItem(column, px, py))
                                  onDragEnded: (px, py, dropped) => tl.dropAt(row.modelData.id, dropped) }
                    Rectangle {   // a drag over this group: its rows are tinted (the group the track will join)
                        visible: tl.dropWhat === "join" && (row.modelData.id === tl.dropBus || row.modelData.bus === tl.dropBus)
                        y: row.top0; width: tl.headerWidth; height: row.h; radius: Theme.radiusCtl
                        color: Theme.accentSoft; border.width: 1; border.color: Theme.accent }
                    Rectangle {   // a drag over a track that is in no group: the track will leave its group
                        visible: tl.dropWhat === "leave" && row.modelData.id === tl.dropOver
                        y: row.top0; width: tl.headerWidth; height: row.h; radius: Theme.radiusCtl
                        color: "transparent"; border.width: 1; border.color: Theme.fg3 }
                    Rectangle {   // between two rows: where the track will sit (a line above the row, or under it)
                        objectName: "dropLine"
                        visible: tl.dropWhat !== "" && !row.modelData.group && row.modelData.id === tl.dropOver
                        x: 0; y: row.top0 + (tl.dropBelow ? row.h + 1 : -2); width: tl.headerWidth; height: 2; radius: 1; color: Theme.accent }
                    Loader {   // group and bottom-mix headers: made only for the rows that are one
                        active: !!row.modelData.group
                        y: row.top0; width: tl.headerWidth; height: row.h
                        sourceComponent: GroupHeader { track: row.modelData; showAuto: !tl.slim
                                       onMenuWanted: (px, py) => tl.openMenu(backend.itemMenu(row.modelData.id), mapToItem(tl, px, py)) }
                    }
                    Loader {
                        active: tl.bottomMix(row.modelData)
                        y: row.top0; width: tl.headerWidth; height: row.h
                        sourceComponent: MixRowHeader { track: row.modelData; showAuto: !tl.slim }
                    }
                    Rectangle {
                        x: bars.x - list.x; y: row.top0; width: bars.width; height: row.h
                        radius: Theme.radiusCtl - 2; color: Theme.sunken; clip: true
                        BeatGrid { anchors.fill: parent; ruler: bars; slot: row.index }
                        LaneBlocks { id: laneBlocks; anchors.fill: parent; track: row.modelData; blocks: row.blocks; ruler: bars; slot: row.index }
                        Loader {   // a section being dragged (SectionBand.shift): its stretch of this lane, taken once at the press,
                            // rides the pointer; the place it leaves is dimmed. Pictures only: the notes are written on release
                            id: slice
                            readonly property var sh: sectionBand.shift
                            active: !!sh && !row.modelData.mix
                            anchors.fill: parent
                            sourceComponent: Item {
                                readonly property real x0: slice.sh ? Math.max(0, slice.sh.x0) : 0
                                readonly property real w: Math.max(1, Math.min(width, slice.sh ? slice.sh.x1 : 0) - x0)
                                Rectangle { x: parent.x0; width: parent.w; height: parent.height; color: Theme.sunken; opacity: 0.7 }
                                ShaderEffectSource {
                                    sourceItem: laneBlocks; live: false; hideSource: false
                                    sourceRect: Qt.rect(parent.x0, 0, parent.w, parent.height)
                                    x: parent.x0 + sectionBand.dx; width: parent.w; height: parent.height
                                }
                            }
                        }
                        DuckDips { anchors.fill: parent; trackId: row.modelData.id; ruler: bars }
                        Loader {   // the take growing while this track records (made only on the armed row)
                            anchors.fill: parent; active: recorder.take.track === row.modelData.id
                            sourceComponent: LiveTake { take: recorder.take; ruler: bars; hue: row.modelData.hue }
                        }
                        Rectangle {   // the time range, shaded on each track lane only (never the empty space below them); a loop that is on is shaded more and edged, as on the ruler
                            readonly property var r: backend.timeRange
                            visible: r.length === 2 && !row.modelData.mix
                            x: visible ? Math.max(0, bars.xOf(r[0])) : 0; height: parent.height
                            width: visible ? Math.max(1, Math.min(bars.width, bars.xOf(r[1])) - x) : 0
                            color: Qt.rgba(Theme.accent.r, Theme.accent.g, Theme.accent.b, backend.looping ? 0.13 : 0.07)
                            Rectangle { visible: backend.looping; width: 1; height: parent.height; color: Theme.accent }
                            Rectangle { visible: backend.looping; x: parent.width - 1; width: 1; height: parent.height; color: Theme.accent }
                        }
                    }
                    Loader {   // the automation lane: made when a lane is open on this row
                        id: laneLoader
                        readonly property var laneRow: row.modelData      // (inside the lane, a bare `row` is the lane's own property: it read itself, undefined)
                        active: !!row.auto
                        y: row.top0 + row.h + tl.laneGap; width: parent.width; height: tl.laneH
                        sourceComponent: AutomationLane { row: laneLoader.laneRow; ruler: bars; plotX: bars.x - list.x }
                    }
                }
            }
        }
        LaneInput {   // every click, drag, box and right-click on the lanes (select first, then act)
            id: lanes
            x: bars.x - list.x; width: bars.width; height: Math.max(column.height, list.height)   // the space below Master too: a click there clears
            tl: tl; bars: bars; flick: list
            onMenuAt: (entries, px, py) => tl.openMenu(entries, lanes.mapToItem(tl, px, py))
        }
    }
    readonly property var marks: backend.markers   // one read per change (each read copies the list)
    Repeater {   // marker lines through the rows; by count: a tempo drag moves them without making them again
        model: tl.marks.length
        delegate: Rectangle {
            required property int index
            readonly property var modelData: tl.marks[index]
            x: bars.x + Math.round(bars.xOf(modelData.t)); y: bars.y + bars.height
            visible: bars.visibleX(x - bars.x)
            width: 1; height: list.y + list.height - y; color: Theme.fg4; opacity: 0.6
        }
    }
    PunchBand { ruler: bars; y: bars.y + bars.height; height: list.y + list.height - y }   // the take's punch range
    PlayTime { id: playTime }
    Rectangle {  // the playhead, across every row (moved every frame while playing: PlayTime)
        visible: bars.visibleX(x - bars.x)
        x: bars.x + Math.round(bars.xOf(playTime.value)); y: bars.y + bars.height
        width: 1; height: list.y + list.height - y; color: Theme.accent; opacity: 0.9
    }
    Rectangle {   // the header being dragged: its name rides the pointer
        visible: tl.dragId !== ""
        x: Theme.gap * 2; y: tl.dragY - height / 2; width: tl.headerWidth - Theme.gap * 2; height: 22; radius: Theme.radiusCtl
        color: Theme.raised; border.color: Theme.accent; opacity: 0.92
        Text { anchors { left: parent.left; leftMargin: Theme.gap; right: parent.right; verticalCenter: parent.verticalCenter }
               text: { var r = tl.rows.find(x => x.id === tl.dragId); return r ? r.name : "" }
               elide: Text.ElideRight; color: Theme.fg; font.family: uiFont; font.pixelSize: Theme.label }
    }
    HScroll { id: scrollbar; view: backend.timeView; x: bars.x; width: bars.width; y: tl.height - height - Theme.grid }

    // ---- the selection's marks: the time range, the snap line, the context bar, the right-click menu ---------
    function rowSpan(id) {   // {top, bottom} of a track's row in the Timeline's px (scrolled), or null
        var top = 0
        for (var i = 0; i < rows.length; i++) {
            top += addAbove(i)
            var h = hOf(rows[i]), lane = autoOf(rows[i]) ? laneGap + laneH : 0
            if (rows[i].id === id) return { top: list.y + top - list.contentY, bottom: list.y + top + h - list.contentY }
            top += h + lane + rowGap
        }
        return null
    }
    function blockOf(trackId, id) {   // a block as its lane draws it now (a handle drag's chip reads what is shown)
        for (var i = 0; i < rowItems.count; i++) {
            var r = rowItems.itemAt(i)
            if (r && r.track.id === trackId) return r.lane.shown.find(b => b.id === id) || null
        }
        return null
    }
    function openMenu(entries, p) { var w = tl.mapToItem(null, p.x, p.y); menu.entries = entries; menu.openAt(w.x, w.y) }
    function menuFor(id) {   // the right-click menu on an item, opened beside it (a scripted step: steps_select.py)
        var entries = backend.itemMenu(id), e = backend.selectionExtent()
        var sp = e.tracks && e.tracks.length ? rowSpan(e.tracks[0]) : null
        openMenu(entries, Qt.point(bars.x + Math.max(0, bars.xOf(e.t0 || 0)) + 12, sp ? sp.bottom : bars.y + bars.height))
    }
    Connections { target: bars; function onMenuAt(t, px, py) { tl.openMenu(backend.atMenu("", t, 1 / bars.perSec), bars.mapToItem(tl, px, py)) } }
    Item {   // what a drag snapped to: the kit's snap line (a marker's or the playhead's name in its chip)
        x: bars.x; y: bars.y; width: bars.width; height: list.y + list.height - y
        readonly property var s: backend.snapLine
        SnapLine { visible: !!parent.s.name && (lanes.busy || bars.snapping || band.dragging) && bars.visibleX(bars.xOf(parent.s.t))
                   at: bars.xOf(parent.s.t || 0); name: parent.s.name || "" }
    }
    ActionMenu { id: menu; onPicked: (v) => backend.menuPick(v) }          // the kit's: keys on rows, dividers
    LaneLineBox { tl: tl; bars: bars }   // typing a voice line right on its lane
}
