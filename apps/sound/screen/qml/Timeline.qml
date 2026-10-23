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
// it, Delete removes it; each is one `automation.set`. `slim`: no lanes and no bus / master rows (unused now).
// Under the tracks: "+ Track" (addTrack: the Sounds panel), then compact rows for the groups (buses) and the master,
// the Master last; they carry their lanes. A ducked track's row shows where its ducks pull it down (DuckDips).
Rectangle {
    id: tl
    property bool slim: false
    property int headerWidth: 224
    signal addTrack()
    readonly property real addH: slim ? 0 : 28          // the "+ Track" row, between the tracks and the group / master rows
    readonly property var rows: slim ? backend.tracks.filter(r => !r.mix) : backend.tracks   // buses + master: lanes only
    readonly property real mixH: 20          // a bus's or the master's compact row
    readonly property real groupH: 24        // a group's header row
    readonly property int mixRows: rows.filter(r => r.mix && !r.group).length
    readonly property int groupRows: rows.filter(r => r.group).length
    readonly property real rowGap: 2
    readonly property real laneH: 76         // an open automation lane
    readonly property real laneGap: 2
    readonly property int openLanes: slim ? 0 : rows.filter(r => r.auto).length
    readonly property real rowH: rows.length === mixRows + groupRows ? 24
        : Math.max(slim ? 18 : 24, Math.min(slim ? 26 : 52,
              (list.height - addH - openLanes * (laneH + laneGap) - mixRows * mixH - groupRows * groupH - rowGap * (rows.length - 1)) / (rows.length - mixRows - groupRows)))
    // Dragging a track header: where it would land is asked of the backend (group_drag.py), the one rule.
    property string dragId: ""
    property string dropOver: ""            // the row under the pointer
    property string dropWhat: ""            // "join" | "leave" | "" (nothing there)
    property string dropBus: ""
    property real dragX: 0
    property real dragY: 0
    function dragTo(id, p) {
        dragId = id; dragY = p.y - list.contentY + list.y
        var i = slot(p.y).i
        dropOver = i >= 0 ? rows[i].id : ""
        var t = dropOver === "" ? "" : backend.dropTarget(dropOver)
        dropWhat = t.split(":")[0]; dropBus = t.indexOf(":") >= 0 ? t.split(":")[1] : ""
    }
    function dropAt(id, dropped) {
        if (dropped && dropWhat !== "" && dropOver !== id) backend.dropTracks([id], dropOver)
        dragId = ""; dropOver = ""; dropWhat = ""; dropBus = ""
    }
    function autoOf(r) { return slim ? null : r.auto }
    function hOf(r) { return r.group ? groupH : r.mix ? mixH : rowH }
    function bottomMix(r) { return !!r.mix && !r.group }                    // a bus or the master in the compact rows, not a group header
    function addAbove(i) { return bottomMix(rows[i]) && (i === 0 || !bottomMix(rows[i - 1])) ? addH : 0 }   // + Track sits above the first mix row
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
    SongBand {   // tempo and key changes (when the song has any)
        id: songBand
        x: bars.x; width: bars.width; y: sectionBand.y + sectionBand.height + (sectionBand.visible ? 2 : 0)
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
                  bottomMargin: Theme.gap + (scrollbar.visible ? scrollbar.height + Theme.grid : 0) }
        contentHeight: column.height; clip: true; boundsBehavior: Flickable.StopAtBounds; interactive: false
        Column {
            id: column
            z: 1      // above the lanes' mouse area: the chips and headers take their own clicks, the rest falls through
            width: list.width; spacing: tl.rowGap
            Repeater {
                model: tl.rows
                delegate: Item {
                    id: row
                    required property var modelData
                    required property int index
                    readonly property var auto: tl.autoOf(modelData)
                    readonly property real h: tl.hOf(modelData)
                    readonly property real top0: tl.addAbove(index)
                    width: column.width; height: top0 + h + (auto ? tl.laneGap + tl.laneH : 0)
                    Button {   // + Track: the Sounds panel (adding a track is choosing its sound)
                        visible: row.top0 > 0 && backend.tracks.some(r => !r.mix); text: "+ Track"; kind: "ghost"; height: Theme.field
                        x: Theme.grid; y: (row.top0 - height) / 2 - tl.rowGap / 2; onClicked: tl.addTrack()
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
                    GroupHeader { visible: !!row.modelData.group; y: row.top0; width: tl.headerWidth; height: row.h; track: row.modelData; showAuto: !tl.slim }
                    MixRowHeader { visible: tl.bottomMix(row.modelData); y: row.top0; width: tl.headerWidth; height: row.h; track: row.modelData; showAuto: !tl.slim }
                    Rectangle {
                        x: bars.x - list.x; y: row.top0; width: bars.width; height: row.h
                        radius: Theme.radiusCtl - 2; color: Theme.sunken; clip: true
                        BeatGrid { anchors.fill: parent; ruler: bars }
                        LaneBlocks { anchors.fill: parent; track: row.modelData; ruler: bars }
                        DuckDips { anchors.fill: parent; trackId: row.modelData.id; ruler: bars }
                    }
                    AutomationLane {
                        visible: !!row.auto
                        y: row.top0 + row.h + tl.laneGap; width: parent.width; height: tl.laneH
                        row: row.modelData; ruler: bars; plotX: bars.x - list.x
                    }
                }
            }
        }
        LaneInput {   // every click, drag, box and right-click on the lanes (select first, then act)
            id: lanes
            x: bars.x - list.x; width: bars.width; height: column.height
            tl: tl; bars: bars; flick: list
            onMenuAt: (entries, px, py) => tl.openMenu(entries, lanes.mapToItem(tl, px, py))
        }
    }
    Repeater {   // marker lines through the rows
        model: backend.markers
        delegate: Rectangle {
            required property var modelData
            x: bars.x + Math.round(bars.xOf(modelData.t)); y: bars.y + bars.height
            visible: bars.visibleX(x - bars.x)
            width: 1; height: list.y + list.height - y; color: Theme.fg4; opacity: 0.6
        }
    }
    PunchBand { ruler: bars; y: bars.y + bars.height; height: list.y + list.height - y }   // the take's punch range
    Rectangle {  // the playhead, across every row
        visible: bars.visibleX(x - bars.x)
        x: bars.x + Math.round(bars.xOf(backend.time)); y: bars.y + bars.height
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
    function openMenu(entries, p) { var w = tl.mapToItem(null, p.x, p.y); menu.entries = entries; menu.openAt(w.x, w.y) }
    function menuFor(id) {   // the right-click menu on an item, opened beside it (a scripted step: steps_select.py)
        var entries = backend.itemMenu(id), e = backend.selectionExtent()
        var sp = e.tracks && e.tracks.length ? rowSpan(e.tracks[0]) : null
        openMenu(entries, Qt.point(bars.x + Math.max(0, bars.xOf(e.t0 || 0)) + 12, sp ? sp.bottom : bars.y + bars.height))
    }
    Connections { target: bars; function onMenuAt(t, px, py) { tl.openMenu(backend.atMenu("", t), bars.mapToItem(tl, px, py)) } }
    Rectangle {   // the time range: a shaded band over the ruler and every lane
        readonly property var r: backend.timeRange
        visible: r.length === 2
        x: visible ? bars.x + Math.max(0, bars.xOf(r[0])) : 0; y: bars.y + bars.height
        width: visible ? Math.max(1, Math.min(bars.width, bars.xOf(r[1])) - Math.max(0, bars.xOf(r[0]))) : 0
        height: list.y + Math.min(list.height, column.height - list.contentY) - y      // down to the last row
        color: Qt.rgba(Theme.accent.r, Theme.accent.g, Theme.accent.b, 0.07)     // faint over the rows (the band shows it strongly)
    }
    Item {   // what a drag snapped to: the kit's snap line (a marker's or the playhead's name in its chip)
        x: bars.x; y: bars.y; width: bars.width; height: list.y + list.height - y
        readonly property var s: backend.snapLine
        SnapLine { visible: !!parent.s.name && lanes.busy && bars.visibleX(bars.xOf(parent.s.t))
                   at: bars.xOf(parent.s.t || 0); name: parent.s.name || "" }
    }
    ActionMenu { id: menu; onPicked: (v) => backend.menuPick(v) }          // the kit's: keys on rows, dividers
    LaneLineBox { tl: tl; bars: bars }   // typing a voice line right on its lane
}
