import QtQuick
import RostrumKit

// Bottom, full width: the arrangement. Markers, the song's sections (when it has any) and a bars/beats ruler on top; one row per track: its header
// (name, mute, solo) and its notes, hits and clips; the playhead and marker lines across every row.
// Click a block: select it (the inspector shows it); drag: move it in time (one gesture = one undo step;
// a quarter beat grid, Shift = free). Click empty lane: select the track and put the playhead there.
// Zoom and scroll: Ctrl + wheel (or a pinch) zooms around the pointer, Shift + wheel or a sideways swipe scrolls,
// Ctrl + / Ctrl - / Ctrl 0 (fit) from the keyboard, a slim scrollbar while zoomed in; playing keeps the playhead
// on screen. The view is backend.viewStart / viewSpan, shared by the ruler, markers, rows and the piano roll.
// A track's "Auto" chip opens its automation lane under the row (AutomationLane): click adds a point, drag moves
// it, Delete removes it; each is one `automation.set`. Tall on the Timeline page, `slim` on the others.
Rectangle {
    id: tl
    property bool slim: false
    readonly property int headerWidth: 200
    readonly property var rows: backend.tracks
    readonly property real rowGap: 2
    readonly property real laneH: 76         // an open automation lane
    readonly property real laneGap: 2
    readonly property int openLanes: slim ? 0 : rows.filter(r => r.auto).length
    readonly property real rowH: rows.length === 0 ? 24
        : Math.max(slim ? 18 : 24, Math.min(slim ? 26 : 52,
              (list.height - openLanes * (laneH + laneGap) - rowGap * (rows.length - 1)) / rows.length))
    function autoOf(r) { return slim ? null : r.auto }
    function slot(y) {   // which row is at height y of the list: its index, whether y is in its automation lane, where that starts
        var top = 0
        for (var i = 0; i < rows.length; i++) {
            var lane = autoOf(rows[i]) ? laneGap + laneH : 0
            if (y < top + rowH + lane + rowGap / 2)
                return { i: i, top: top, lane: lane > 0 && y >= top + rowH + laneGap, laneTop: top + rowH + laneGap }
            top += rowH + lane + rowGap
        }
        return { i: -1, top: 0, lane: false, laneTop: 0 }
    }
    color: Theme.panel; radius: Theme.radiusPanel; clip: true

    Text {   // the song's grid, where the headers are
        x: Theme.pad; y: bars.y + (bars.height - height) / 2
        text: Math.round(backend.song.tempo) + " bpm  ·  " + backend.song.beatsPerBar + "/4"
              + (backend.song.key ? "  ·  " + backend.song.key : "")
        color: Theme.fg3; font.family: uiFont; font.pixelSize: Theme.label; font.features: { "tnum": 1 }
    }
    Text {   // while zoomed in: how far, and the way back
        visible: !backend.viewFit
        x: Theme.pad; y: band.y + (band.height - height) / 2
        text: "Zoom " + (Math.round(backend.song.length / backend.viewSpan * 10) / 10) + "×  ·  Ctrl 0 shows all"
        color: zoomArea.containsMouse ? Theme.fg : Theme.fg3; font.family: uiFont; font.pixelSize: Theme.label
        MouseArea { id: zoomArea; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                    onClicked: backend.fitView() }
    }
    MarkerBand {
        id: band
        x: bars.x; width: bars.width; y: Theme.gap; height: 18; ruler: bars
    }
    SectionBand {
        id: sectionBand
        x: bars.x; width: bars.width; y: band.y + band.height + 2; height: visible ? 18 : 0; ruler: bars
    }
    BarRuler {
        id: bars
        x: tl.headerWidth + Theme.gap * 2; width: tl.width - x - Theme.pad
        y: sectionBand.y + sectionBand.height + (sectionBand.visible ? 2 : 0); height: 22
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
                    readonly property var auto: tl.autoOf(modelData)
                    width: column.width; height: tl.rowH + (auto ? tl.laneGap + tl.laneH : 0)
                    TrackHeader { width: tl.headerWidth; height: tl.rowH; track: row.modelData }
                    Rectangle {
                        x: bars.x - list.x; width: bars.width; height: tl.rowH
                        radius: Theme.radiusCtl - 2; color: Theme.sunken; clip: true
                        BeatGrid { anchors.fill: parent; ruler: bars }
                        LaneBlocks { anchors.fill: parent; track: row.modelData; ruler: bars }
                        LaneToggle { visible: !tl.slim; track: row.modelData
                                     anchors { right: parent.right; rightMargin: 4; verticalCenter: parent.verticalCenter } }
                    }
                    AutomationLane {
                        visible: !!row.auto
                        y: tl.rowH + tl.laneGap; width: parent.width; height: tl.laneH
                        row: row.modelData; ruler: bars; plotX: bars.x - list.x
                    }
                }
            }
        }
        MouseArea {   // every click and drag on the lanes, in one place
            id: lanes
            x: bars.x - list.x; width: bars.width; height: column.height
            preventStealing: true
            property real x0: 0
            property real laneTop: 0
            property string mode: ""            // "drag" | "seek" | "point"
            function yFrac(y) { return Math.max(0, Math.min(1, (y - laneTop - 8) / (tl.laneH - 16))) }
            onWheel: (w) => {
                if (!backend.viewWheel(w.angleDelta.x, w.angleDelta.y, (w.modifiers & Qt.ControlModifier) !== 0,
                                       (w.modifiers & Qt.ShiftModifier) !== 0, w.x / width, list.contentHeight > list.height + 1))
                    list.contentY = Math.max(0, Math.min(list.contentHeight - list.height, list.contentY - w.angleDelta.y / 2))
            }
            PinchGrow {}
            onPressed: (m) => {
                var s = tl.slot(m.y)
                if (s.i < 0) return
                var r = tl.rows[s.i], t = bars.tOf(m.x), a = tl.autoOf(r)
                x0 = m.x
                if (s.lane && a) {
                    laneTop = s.laneTop; mode = "point"
                    backend.laneBegin(r.id, a.target, a.lane, t, yFrac(m.y), 7 / bars.perSec, 7 / (tl.laneH - 16),
                                      (m.modifiers & Qt.ShiftModifier) !== 0)
                    return
                }
                var lane = Math.max(0, Math.min(1, (m.y - s.top - 3) / Math.max(1, tl.rowH - 8)))
                var id = backend.blockAt(r.id, t, lane, 6 / bars.perSec)
                if (id !== "" && backend.beginDrag(id)) { mode = "drag"; return }
                mode = "seek"
                backend.select(r.id)
                backend.clearPoint()
                backend.setTime(t)
            }
            onPositionChanged: (m) => {
                if (mode === "drag") backend.dragBy((m.x - x0) / bars.perSec, 0, (m.modifiers & Qt.ShiftModifier) !== 0)
                else if (mode === "point") backend.laneDrag(bars.tOf(m.x), yFrac(m.y), (m.modifiers & Qt.ShiftModifier) !== 0)
                else if (mode === "seek") backend.setTime(bars.tOf(m.x))
            }
            onReleased: { if (mode === "drag" || mode === "point") backend.endDrag(); mode = "" }
            onCanceled: { if (mode === "drag" || mode === "point") backend.cancelDrag(); mode = "" }
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
    Rectangle {  // the playhead, across every row
        visible: bars.visibleX(x - bars.x)
        x: bars.x + Math.round(bars.xOf(backend.time)); y: bars.y + bars.height
        width: 1; height: list.y + list.height - y; color: Theme.accent; opacity: 0.9
    }
    HScroll { id: scrollbar; x: bars.x; width: bars.width; y: tl.height - height - Theme.grid }
}
