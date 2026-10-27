import QtQuick
import RostrumKit
import "Blocks.js" as Blocks
import "Slide.js" as Slide
import "Marks.js" as Marks
import RostrumCursors 1.0
import "Picks.js" as Picks

// The velocity strip under the Editor's roll (DESIGN.md §3.3d): one bar per note (or drum hit) at its start, as high
// as it is loud. Drag a bar: that note (a selected bar takes every selected note with it by the same proportion;
// Alt = all to the same height). Drag across empty space: a line, and each note under it (the selected ones, when
// some are; the words beside the line say which: "every note", "3 selected notes") takes the line's height. One drag is one undo step (backend.beginVelocity … endVelocity); the number
// beside the pointer is the height being set (the kit's value chip, "Velocity 70 %"; a line adds what it sets). Esc
// during a drag puts every bar back, no undo step (dragEsc). The pointer (the kit's CanvasCursor): a bar's top
// `resize` up-down, empty space `make` (draw a line); kept while a drag runs. The fold arrow at the bottom left folds
// it to one thin row (the person's own screen state: backend.velocityFolded); the arrow stays under the pointer (the
// strip opens upward from it) and the roll takes the room. The value of the stem under the pointer, else of the
// selected one (several: their range), is written beside it ("70 %"). Its top edge drags it taller (52 … 240 px, never
// leaving the roll under `roomMax`; the roll gives the room): a crescendo over 8 bars needs the height to aim. The
// height is the person's screen state too (backend.velocityHeight), kept with the song like the fold.
Item {
    id: s
    property var roll
    property var blocks: []
    property var ruler
    property int keysWidth: 52
    readonly property bool folded: backend.velocityFolded
    property real roomMax: 240                 // the most the strip may take here (the host keeps the roll usable)
    readonly property real edgeIn: 12          // how far the top edge's grip reaches into the strip (a press there resizes)
    property real dragH: -1                    // the height while its top edge is dragged, else -1 (the kept one)
    readonly property real fullHeight: Math.max(52, Math.min(dragH >= 0 ? dragH : backend.velocityHeight, roomMax))
    readonly property real foldedHeight: 18
    readonly property real padTop: 6
    readonly property real plotH: height - padTop - 4
    readonly property var picked: Picks.all(backend, backend.pickStamp)     // one shared object a selection
    property string mode: ""                    // "" | "press" | "bar" | "line"
    property string hit: ""
    property real x0: 0
    property real y0: 0
    property real v: 0
    property real px: 0
    property real py: 0
    height: folded ? foldedHeight : fullHeight
    property string hoverId: ""
    readonly property var shown: {   // {x, y, text} of the value readout, or null
        // the hovered stem's, else the selected ones' (backend.rollPicked: their few numbers, velocity.readout)
        if (mode === "bar" || mode === "line") return null
        var one = hoverId, r = backend.rollPicked
        if (one !== "") {
            var b = s.blocks
            r = null
            for (var i = 0; i < b.length; i++)
                if (b[i].id === one && (b[i].type === "note" || b[i].type === "hit")) { r = { lo: b[i].vel, hi: b[i].vel, t: b[i].t, v: b[i].vel }; break }
        }
        if (!r || r.t === undefined) return null
        var lo = Math.round(100 * r.lo), hi = Math.round(100 * r.hi)
        return { x: ruler.xOf(r.t), v: r.v, text: lo === hi ? lo + " %" : lo + "–" + hi + " %" }
    }
    // What a line drawn now changes, said beside it while it is drawn: the selected notes (hits) of this track when
    // there are some, else every one (backend.beginVelocity: the same rule, every time).
    readonly property string lineScope: {
        var kind = roll.kind === "drums" ? "hit" : "note", n = backend.rollPicked[kind] || 0
        var word = kind === "hit" ? "hit" : "note"
        return n === 0 ? "every " + word : n === 1 ? "the selected " + word : n + " selected " + word + "s"
    }
    function vAt(y) { return Math.max(0, Math.min(1, 1 - (y - padTop) / plotH)) }
    function nearest(x) {                       // the bar under x (within 5 px), "" for none
        var b = s.blocks, best = "", d = 6
        for (var i = 0; i < b.length; i++) {
            if (b[i].type !== "note" && b[i].type !== "hit") continue
            var e = Math.abs(ruler.xOf(b[i].t) - x)
            if (e < d) { d = e; best = b[i].id }
        }
        return best
    }
    Item {   // the fold arrow and the label, at the bottom: click either to fold or open the strip (it stays where it is)
        x: 0; y: s.height - s.foldedHeight; width: s.keysWidth; height: s.foldedHeight
        Canvas {
            id: arrow
            x: Theme.gap; anchors.verticalCenter: parent.verticalCenter; width: 10; height: 10
            property color ink: vh.containsMouse ? Theme.fg : Theme.fg3
            property bool folded: s.folded
            onInkChanged: requestPaint()
            onFoldedChanged: requestPaint()
            onPaint: { var c = getContext("2d"); c.reset(); c.fillStyle = ink; c.beginPath()
                       if (folded) { c.moveTo(2, 0); c.lineTo(9, 5); c.lineTo(2, 10) } else { c.moveTo(0, 2); c.lineTo(10, 2); c.lineTo(5, 9) }
                       c.closePath(); c.fill() }
        }
        Text { x: Theme.gap + 14; anchors.verticalCenter: parent.verticalCenter
               text: "Velocity"; color: Theme.fg4; font.family: uiFont; font.pixelSize: Theme.label }
        MouseArea { id: vh; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                    onClicked: backend.toggleVelocityFold() }
        HoverTip { text: s.folded ? (backend.rollPlayed ? "Show the velocity strip and the playing lane" : "Show the velocity strip") : "Velocity: how hard each note plays. Drag a bar, or draw a line across: it sets the selected notes, or every note when none is. Drag its top edge to make it taller. Click to fold it away" + (backend.rollPlayed ? " (with the playing lane under it)" : "")
                   hovered: vh.containsMouse; pressed: vh.pressed }
    }
    Rectangle { visible: !s.folded; x: s.keysWidth; width: s.width - x; height: s.height; radius: Theme.radiusCtl; color: Theme.sunken
                border.color: Theme.border; border.width: 1 }
    Item {   // the bars' plot, right of the keys
    visible: !s.folded
    x: s.keysWidth; width: s.width - x; height: s.height; clip: true
    ViewCanvas {
        id: c
        height: parent.height
        ruler: s.ruler; slot: 1
        // painted whole on a new zoom, scroll or track (a resize: stretched, then whole: ViewCanvas), else only where an edit or a selection changed (Blocks.js)
        onWholeWanted: again()
        onHeightChanged: again()
        Connections { target: s; function onRollChanged() { c.again() } function onBlocksChanged() { c.requestPaint() }
                      function onPickedChanged() { if (Blocks.touches(c.kept, s.picked)) c.requestPaint() } }   // a selection elsewhere: as it is
        property bool stale: false              // asked while hidden (the Mixer shows): painted when shown again
        onVisibleChanged: if (visible && stale) { stale = false; requestPaint() }
        function view() {                       // what every bar of one paint shares, read once per paint (Marks.js)
            return { x0: s.ruler.xOf(0), perSec: s.ruler.perSec, H: height, W: width, top: s.padTop + s.plotH, plotH: s.plotH,
                     hue: s.roll.hue, accent: Theme.accent }
        }
        onPaint: {
            if (!visible) { stale = true; return }
            if (waiting) return                                  // the stretched picture stands until its turn
            if (height <= 0) { whole = true; return }            // the Editor still opening: painted once it has a size
            var ctx = getContext("2d"), v = view(), at = Marks.velAt(v)
            var slid = whole ? null : Slide.slide(kept, ctx, s.blocks, s.picked, v.x0, v.perSec, width, height)
            for (var j = 0; slid !== null && j < slid.length; j++) {    // every bar moved as one: the picture moved
                Blocks.clear(ctx, slid[j][0]); paintIn(ctx, slid[j][1], v, slid[j][0]); ctx.restore()
            }
            if (slid !== null) return
            var dirty = whole ? null : Blocks.update(kept, s.blocks, s.picked, at)
            whole = false
            if (dirty === null) { markPainted(); ctx.reset(); paintIn(ctx, Blocks.rebuild(kept, s.blocks, s.picked, at, width), v, null); return }
            for (var i = 0; i < dirty.length; i++) {            // only the changed places, each cleared and painted again
                Blocks.clear(ctx, dirty[i]); paintIn(ctx, Blocks.over(kept, dirty[i]), v, dirty[i]); ctx.restore()
            }
        }
        function paintIn(ctx, entries, v, d) {                  // the half-way guide and these bars ([block, selected]; over `d`, when one)
            ctx.fillStyle = Theme.border; ctx.fillRect(0, s.padTop + s.plotH / 2, width, 1)
            Marks.velPaint(ctx, entries, v, d)
        }
    }
    }
    Canvas {   // the line, as drawn
        id: ln
        anchors.fill: parent; visible: s.mode === "line" && !s.folded
        onVisibleChanged: requestPaint()
        onPaint: {
            var ctx = getContext("2d"); ctx.reset()
            if (s.mode !== "line") return
            ctx.strokeStyle = Theme.accent; ctx.lineWidth = 1.5
            ctx.beginPath(); ctx.moveTo(s.keysWidth + s.x0, s.y0); ctx.lineTo(s.keysWidth + s.px, s.py); ctx.stroke()
        }
    }
    DragLabel {   // the height being set, by the pointer (the kit's value chip)
        objectName: "velocityChip"
        text: s.mode === "bar" || s.mode === "line" ? "Velocity " + Math.round(100 * s.v) + " %" : ""
        hint: s.mode === "line" ? s.lineScope : s.mode === "bar" && m.altAll ? "all the same" : ""
        at: Qt.point(s.keysWidth + s.px, s.py)
    }
    Rectangle {   // the hovered or selected stem's value
        readonly property var r: s.shown
        visible: !s.folded && r !== null && s.ruler.visibleX(r.x)
        x: r ? Math.max(s.keysWidth, Math.min(s.width - width - 2, s.keysWidth + r.x + 6)) : 0
        y: r ? Math.max(1, Math.min(s.height - height - 1, s.padTop + s.plotH * (1 - r.v) - height / 2)) : 0
        width: rt.implicitWidth + 2 * Theme.grid; height: rt.implicitHeight + 2; radius: 3; color: Theme.raised; border.color: Theme.popupEdge
        Text { id: rt; anchors.centerIn: parent; text: parent.r ? parent.r.text : ""; color: Theme.fg; font.family: uiFont
               font.pixelSize: Theme.label; font.features: { "tnum": 1 } }
    }
    MouseArea {
        id: m
        enabled: !s.folded
        onExited: s.hoverId = ""
        x: s.keysWidth; width: s.width - x; y: s.folded ? 0 : s.edgeIn; height: s.height - y   // (under the top edge's grip)
        // a bar's top: `level` (drag it); empty: `draw` (a line across). The stem under the pointer is set as it moves (an
        // edit never re-reads every stem); during a drag, what the press began
        preventStealing: true; hoverEnabled: true
        property bool altAll: false             // Alt during a bar drag: every one to the same height
        CanvasCursor {
            objectName: "velocityCursor"; anchors.fill: parent
            readonly property bool bar: s.mode === "bar" || (s.mode !== "line" && s.hoverId !== "")
            kind: bar ? "resize" : "make"; angle: bar ? 90 : 0
        }
        Connections {   // Esc during a drag: every bar back, no undo step
            target: dragEsc
            function onCancelled() { if (s.mode === "bar" || s.mode === "line") { backend.cancelDrag(); s.mode = "" } }
        }
        onWheel: (w) => backend.viewWheel(w.angleDelta.x, w.angleDelta.y, (w.modifiers & Qt.ControlModifier) !== 0,
                                         (w.modifiers & Qt.ShiftModifier) !== 0, w.x / width, true)
        onPressed: (e) => { backend.focusArea("roll"); s.hit = s.nearest(e.x); s.mode = "press"; s.x0 = s.px = e.x; s.y0 = s.py = (e.y + m.y) }
        onPositionChanged: (e) => {
            if (!pressed) { s.hoverId = s.nearest(e.x); return }
            s.px = e.x; s.py = (e.y + m.y); s.v = s.vAt((e.y + m.y))
            if (s.mode === "press" && (Math.abs(e.x - s.x0) >= 4 || Math.abs((e.y + m.y) - s.y0) >= 4))
            { s.mode = backend.beginVelocity(s.hit) ? (s.hit !== "" ? "bar" : "line") : ""; if (s.mode !== "") dragEsc.holdEsc() }
            altAll = (e.modifiers & Qt.AltModifier) !== 0
            if (s.mode === "bar") backend.velocityBar(s.v, altAll)
            else if (s.mode === "line") {
                backend.velocityLine(s.ruler.tOf(s.x0), s.vAt(s.y0), s.ruler.tOf(e.x), s.v, 4 / s.ruler.perSec); ln.requestPaint()
            }
        }
        onReleased: { if (s.mode === "bar" || s.mode === "line") { dragEsc.letEsc(); backend.endVelocity() } s.mode = "" }
        onCanceled: { if (s.mode === "bar" || s.mode === "line") { dragEsc.letEsc(); backend.cancelDrag() } s.mode = "" }
    }
    MouseArea {   // the top edge: drag up for a taller strip (down to make it short again); the roll gives the room
        id: edge
        objectName: "velocityEdge"
        visible: !s.folded
        x: s.keysWidth; width: s.width - x; y: s.edgeIn - 16; height: 16; z: 2     // the gap above and the strip's top 12 px
        hoverEnabled: true; preventStealing: true; cursorShape: Qt.SizeVerCursor
        property real y0: 0
        property real h0: 0
        onPressed: (e) => { y0 = mapToItem(null, e.x, e.y).y; h0 = s.fullHeight; s.dragH = h0 }
        onPositionChanged: (e) => { if (pressed) s.dragH = Math.max(52, Math.min(s.roomMax, h0 - (mapToItem(null, e.x, e.y).y - y0))) }
        onReleased: { backend.setVelocityHeight(s.dragH); s.dragH = -1 }
        onCanceled: s.dragH = -1
        Rectangle { anchors.horizontalCenter: parent.horizontalCenter; anchors.verticalCenter: parent.verticalCenter
                    visible: edge.containsMouse || edge.pressed; width: 32; height: 3; radius: 1.5; color: Theme.fg3 }
    }
}
