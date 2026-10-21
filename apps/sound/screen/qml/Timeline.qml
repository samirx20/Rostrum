import QtQuick
import RostrumKit

// Bottom, full width: the arrangement. Markers and a bars/beats ruler on top; one row per track: its header
// (name, mute, solo) and its notes, hits and clips; the playhead and marker lines across every row.
// Click a block: select it (the inspector shows it); drag: move it in time (one gesture = one undo step;
// a quarter beat grid, Shift = free). Click empty lane: select the track and put the playhead there.
// Tall on the Timeline page, `slim` on the others (the same rows, shorter).
Rectangle {
    id: tl
    property bool slim: false
    readonly property int headerWidth: 200
    readonly property var rows: backend.tracks
    readonly property real rowGap: 2
    readonly property real rowH: rows.length === 0 ? 24
        : Math.max(slim ? 18 : 24, Math.min(slim ? 26 : 52, (list.height - rowGap * (rows.length - 1)) / rows.length))
    color: Theme.panel; radius: Theme.radiusPanel; clip: true

    Text {   // the song's grid, where the headers are
        x: Theme.pad; y: bars.y + (bars.height - height) / 2
        text: Math.round(backend.song.tempo) + " bpm  ·  " + backend.song.beatsPerBar + "/4"
        color: Theme.fg3; font.family: uiFont; font.pixelSize: Theme.label; font.features: { "tnum": 1 }
    }
    MarkerBand {
        id: band
        x: bars.x; width: bars.width; y: Theme.gap; height: 18; ruler: bars
    }
    BarRuler {
        id: bars
        x: tl.headerWidth + Theme.gap * 2; width: tl.width - x - Theme.pad; y: band.y + band.height + 2; height: 22
    }
    Flickable {
        id: list
        anchors { left: parent.left; right: parent.right; top: bars.bottom; bottom: parent.bottom
                  leftMargin: Theme.gap; rightMargin: Theme.pad; topMargin: Theme.grid; bottomMargin: Theme.gap }
        contentHeight: column.height; clip: true; boundsBehavior: Flickable.StopAtBounds; interactive: false
        Column {
            id: column
            width: list.width; spacing: tl.rowGap
            Repeater {
                model: tl.rows
                delegate: Item {
                    required property var modelData
                    width: column.width; height: tl.rowH
                    TrackHeader { width: tl.headerWidth; height: parent.height; track: parent.modelData }
                    Rectangle {
                        x: bars.x - list.x; width: bars.width; height: parent.height
                        radius: Theme.radiusCtl - 2; color: Theme.sunken
                        BeatGrid { anchors.fill: parent; ruler: bars }
                        LaneBlocks { anchors.fill: parent; track: parent.parent.modelData; ruler: bars }
                    }
                }
            }
        }
        MouseArea {   // every click and drag on the lanes, in one place
            id: lanes
            x: bars.x - list.x; width: bars.width; height: column.height
            preventStealing: true
            property real x0: 0
            property string mode: ""            // "drag" | "seek"
            onWheel: (w) => { list.contentY = Math.max(0, Math.min(list.contentHeight - list.height,
                                                                   list.contentY - w.angleDelta.y / 2)) }
            onPressed: (m) => {
                var i = Math.floor(m.y / (tl.rowH + tl.rowGap))
                if (i < 0 || i >= tl.rows.length) return
                var inRow = m.y - i * (tl.rowH + tl.rowGap), t = bars.tOf(m.x)
                var lane = Math.max(0, Math.min(1, (inRow - 3) / Math.max(1, tl.rowH - 8)))
                var id = backend.blockAt(tl.rows[i].id, t, lane, 6 / bars.perSec)
                x0 = m.x
                if (id !== "" && backend.beginDrag(id)) { mode = "drag"; return }
                mode = "seek"
                backend.select(tl.rows[i].id)
                backend.setTime(t)
            }
            onPositionChanged: (m) => {
                if (mode === "drag") backend.dragBy((m.x - x0) / bars.perSec, 0, (m.modifiers & Qt.ShiftModifier) !== 0)
                else if (mode === "seek") backend.setTime(bars.tOf(m.x))
            }
            onReleased: { if (mode === "drag") backend.endDrag(); mode = "" }
            onCanceled: { if (mode === "drag") backend.cancelDrag(); mode = "" }
        }
    }
    Repeater {   // marker lines through the rows
        model: backend.markers
        delegate: Rectangle {
            required property var modelData
            x: bars.x + Math.round(bars.xOf(modelData.t)); y: bars.y + bars.height
            width: 1; height: list.y + list.height - y; color: Theme.fg4; opacity: 0.6
        }
    }
    Rectangle {  // the playhead, across every row
        x: bars.x + Math.round(bars.xOf(backend.time)); y: bars.y + bars.height
        width: 1; height: list.y + list.height - y; color: Theme.accent; opacity: 0.9
    }
}
