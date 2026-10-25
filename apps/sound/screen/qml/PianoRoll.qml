import QtQuick
import RostrumKit
import "Blocks.js" as Blocks

// The Editor (bottom dock): the selection's track up close. Notes: bars on a keyboard (drag = time and pitch,
// double-click empty space = a new note, Delete removes). Drums: one row per drum. Recorded clips: their
// waveforms. Select first, then act (RollInput): click, Ctrl / Shift+click, a box; a drag moves every selected one
// (one undo step; Ctrl = no snapping, Shift = only in time, Alt = a copy). The keyboard at the left is a real one
// (RollGrid: a click plays the key). Its header (the track, Select / Draw, Note ▾) is on the dock's line (EditorHeader).
// It opens framed on the track's notes: the rows fit every note in view, centred on them.
Panel {
    id: p
    readonly property var roll: backend.roll                // its layout: kind, keys, drum rows, hue
    readonly property var marks: backend.markers            // one read per change (each read copies the list)
    readonly property var blocks: patched || Blocks.parse(backend.rollBlocks)    // its notes / hits / clips, sent alone (an edit on them)
    property var patched: null                              // a few of them changed since (backend.rollPatched)
    Connections {
        target: backend
        function onRollPatched(gone, put) { p.patched = Blocks.patch(p.blocks, gone, put) }
        function onRollBlocksChanged() { p.patched = null }
    }
    readonly property string kind: roll.kind
    readonly property int keysWidth: kind === "drums" ? 76 : 72     // drum names ("Open hat"); a keyboard wide enough to play
    // What shows, as conditions (never read from `visible`, which turns false while the dock shows the Mixer: the roll
    // then grew under a hidden strip and was laid out and painted whole on every E / X)
    readonly property bool shows: kind !== "none" && kind !== "empty"
    readonly property bool hasStrip: shows && (kind === "notes" || kind === "drums")
    readonly property bool laneShown: hasStrip && !!playedLane && !strip.folded && (lanesOpen || laneUsed)
    readonly property bool foldShown: hasStrip && !!playedLane && !strip.folded && !laneShown
    BarRuler {
        id: bars
        visible: p.shows
        x: p.keysWidth; width: parent.width - x; height: implicitHeight
    }
    Rectangle {
        id: well
        visible: p.shows
        anchors { left: parent.left; right: parent.right; top: bars.bottom; bottom: p.hasStrip ? strip.top : parent.bottom; topMargin: Theme.grid
                  bottomMargin: p.hasStrip ? Theme.grid : 0 }
        radius: Theme.radiusCtl; color: Theme.sunken; clip: true

        Flickable {
            id: view
            anchors.fill: parent
            contentHeight: grid.height; boundsBehavior: Flickable.StopAtBounds; interactive: false
            RollGrid { id: grid; onDrumMenuAt: (drum, px, py) => { drumMenu.drum = drum; drumMenu.entries = backend.drumRowMenu(drum, input.lastT); var q = grid.mapToItem(null, px, py); drumMenu.openAt(q.x, q.y) }
                      width: view.width; viewHeight: view.height; scrollY: view.contentY; roll: p.roll; blocks: p.blocks; ruler: bars; keysWidth: p.keysWidth }
            RollInput {   // every click, drag, box and right-click on the roll (select first, then act)
                id: input
                x: p.keysWidth; width: grid.width - x; height: grid.height
                grid: grid; bars: bars; flick: view; kind: p.kind; trackId: p.roll.id
                onMenuAt: (entries, px, py) => { rollMenu.entries = entries; var q = input.mapToItem(null, px, py); rollMenu.openAt(q.x, q.y) }
            }
            Component.onCompleted: centre()
            // The keys shown follow the notes (the top key = the highest note + 4), so an edit that moves that edge
            // would slide every row under the pointer. Only the person moves the view: the top key's shift is
            // taken out of the scroll, so every row stays where it was.
            property int seenHi: p.roll.hi
            property string seenShown: ""
            readonly property int topKey: p.roll.hi
            onTopKeyChanged: {
                if (shown === seenShown && grid.notes && !grid.shownKeys && topKey !== seenHi)
                    contentY = Math.max(0, Math.min((p.roll.hi - p.roll.lo + 1) * grid.rowH - height, contentY + (topKey - seenHi) * grid.rowH))
                seenHi = topKey
            }
            function centre() {   // framed on the notes: the rows fit them all (grid.frame), the view centred on them
                seenHi = p.roll.hi; seenShown = shown
                var ks = [], b = p.blocks
                for (var i = 0; i < b.length; i++) if (b[i].keys) ks = ks.concat(b[i].keys)
                if (!ks.length || p.kind !== "notes") {
                    grid.frame(0)   // an empty notes track opens on the middle of its range (its sound's best keys), else the top
                    contentY = p.kind === "notes" ? Math.max(0, Math.min(contentHeight - height, grid.count / 2 * grid.rowH - height / 2)) : 0
                    return
                }
                var lo = Math.min.apply(null, ks), hi = Math.max.apply(null, ks)
                grid.frame(grid.rowOf(lo) - grid.rowOf(hi) + 1)
                contentY = Math.max(0, Math.min(contentHeight - height, ((grid.rowOf(hi) + grid.rowOf(lo)) / 2 + 0.5) * grid.rowH - height / 2))
            }
            onHeightChanged: centre()
            readonly property string shown: p.roll.id + "/" + p.kind + (grid.shownKeys ? "/rows" : "")      // another track (or kind): framed again
            onShownChanged: centre()
        }
        Repeater {   // marker lines; by count: a tempo drag moves them without making them again
            model: p.marks.length
            delegate: Rectangle { required property int index; readonly property var modelData: p.marks[index]
                x: p.keysWidth + Math.round(bars.xOf(modelData.t)); width: 1; height: well.height
                visible: bars.visibleX(x - p.keysWidth); color: Theme.fg4; opacity: 0.6 }
        }
        Repeater {   // a voice line with several takes: ◂ ▸ on its block (TakeArrows.qml)
            model: p.kind === "audio" ? p.blocks.filter(b => b.canBack || b.canNext) : []   // only a voice track (audio) has takes
            TakeArrows { required property var modelData; block: modelData; ruler: bars; xOffset: p.keysWidth; inset: well.height * 0.2 + 5 }
        }
        PlayTime { id: playTime }
        Rectangle { x: p.keysWidth + Math.round(bars.xOf(playTime.value)); width: 1; height: well.height
                    visible: bars.visibleX(x - p.keysWidth); color: Theme.accent; opacity: 0.9 }
        Rectangle {   // the time range, shaded
            readonly property var r: backend.timeRange
            visible: r.length === 2
            x: visible ? p.keysWidth + Math.max(0, bars.xOf(r[0])) : 0; height: well.height
            width: visible ? Math.max(1, Math.min(bars.width, bars.xOf(r[1])) - Math.max(0, bars.xOf(r[0]))) : 0
            color: Theme.accentSoft
        }
        Item {   // what a drag snapped to: the kit's snap line over the roll
            x: p.keysWidth; width: bars.width; height: well.height
            readonly property var s: backend.snapLine
            SnapLine { visible: !!parent.s.name && (input.busy || bars.snapping) && bars.visibleX(bars.xOf(parent.s.t))
                       at: bars.xOf(parent.s.t || 0); name: parent.s.name || "" }
        }
    }
    VelocityStrip {   // one bar per note or hit; drag a bar, or draw a line across (DESIGN.md §3.3d)
        id: strip
        visible: p.hasStrip
        anchors { left: parent.left; right: parent.right; bottom: p.laneShown ? played.top : p.foldShown ? laneFold.top : parent.bottom
                  bottomMargin: p.laneShown || p.foldShown ? Theme.grid : 0 }
        roll: p.roll; blocks: p.blocks; ruler: bars; keysWidth: p.keysWidth
    }
    // The playing lane (sustain, expression, bend) stays folded while the track has none of them: a one-line "›" opens it.
    readonly property var playedLane: backend.rollPlayed        // its own property: a point added redraws only the lane
    readonly property bool laneUsed: !!p.playedLane && p.playedLane.choices.some(c => c.used)
    property bool lanesOpen: false
    readonly property string laneTrack: p.roll.id + "/" + p.kind
    onLaneTrackChanged: lanesOpen = false
    Item {
        id: laneFold
        visible: p.foldShown
        anchors { left: parent.left; right: parent.right; bottom: parent.bottom }
        height: 18
        Chevron { id: laneChev; x: 4; anchors.verticalCenter: parent.verticalCenter; rotation: -90
                  color: laneHover.hovered ? Theme.fg : Theme.fg3 }
        Text { anchors { left: laneChev.right; leftMargin: Theme.grid + 2; verticalCenter: parent.verticalCenter }
               text: "Sustain · Expression · Bend"; color: laneHover.hovered ? Theme.fg : Theme.fg3
               font.family: uiFont; font.pixelSize: Theme.label }
        HoverHandler { id: laneHover; cursorShape: Qt.PointingHandCursor }
        TapHandler { onTapped: p.lanesOpen = true }
    }
    AutomationLane {   // the playing lane under the velocity strip: sustain pedal, expression, pitch bend (folds with it)
        id: played
        visible: p.laneShown
        anchors { left: parent.left; right: parent.right; bottom: parent.bottom }
        height: 64; inEditor: true; plotX: p.keysWidth; ruler: bars
        row: ({ id: p.roll.id, hue: p.roll.hue, auto: p.playedLane })
    }
    ActionMenu { id: drumMenu; property string drum: ""; objectName: "drumRowMenu_" + drum; onPicked: (v) => backend.menuPick(v) }   // a drum row's name: Hear, Fill ▸, Clear …
    ActionMenu { id: rollMenu; objectName: "rollMenu"; onPicked: (v) => backend.menuPick(v) }      // the kit's
    Connections {   // right-click on the roll's ruler: what the arrangement's ruler offers (Add marker here, Make a section …)
        target: bars
        function onMenuAt(t, px, py) { rollMenu.entries = backend.atMenu("", t, 1 / bars.perSec); var q = bars.mapToItem(null, px, py); rollMenu.openAt(q.x, q.y) }
    }
    function drumMenuFor(drum, fillOpen) {   // a drum row's menu, open under its name, Fill ▸ open too (a scripted step: steps_select.py)
        drumMenu.drum = drum; drumMenu.entries = backend.drumRowMenu(drum, input.lastT)
        var q = grid.mapToItem(null, 30, (roll.drums.indexOf(drum) + 0.5) * grid.rowH)
        drumMenu.openAt(q.x, q.y)
        if (fillOpen) drumMenu.openSub(drumMenu.entries.findIndex(e => e.sub && e.sub.length && e.label === "Fill"))
    }
    function menuFor(id) {   // the right-click menu on an item (a scripted step: steps_select.py)
        rollMenu.entries = backend.itemMenu(id)
        var e = backend.selectionExtent()
        var q = well.mapToItem(null, p.keysWidth + Math.max(0, bars.xOf(e.t1 || 0)) + 8, well.height / 3)
        rollMenu.openAt(q.x, q.y)
    }
}
