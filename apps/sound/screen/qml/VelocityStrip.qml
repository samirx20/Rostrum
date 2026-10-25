import QtQuick
import RostrumKit
import "Blocks.js" as Blocks
import "Marks.js" as Marks

// The velocity strip under the Editor's roll (DESIGN.md §3.3d): one bar per note (or drum hit) at its start, as high
// as it is loud. Drag a bar: that note (a selected bar takes every selected note with it by the same proportion;
// Alt = all to the same height). Drag across empty space: a line, and each note under it (the selected ones, when
// some are) takes the line's height. One drag is one undo step (backend.beginVelocity … endVelocity); the number
// beside the pointer is the height being set. The fold arrow at the left folds it to one thin row (the person's own
// screen state: backend.velocityFolded); the roll takes the room. The value of the stem under the pointer, else of the
// selected one (several: their range), is written beside it ("70 %").
Item {
    id: s
    property var roll
    property var blocks: []
    property var ruler
    property int keysWidth: 52
    readonly property bool folded: backend.velocityFolded
    readonly property real fullHeight: 52
    readonly property real foldedHeight: 18
    readonly property real padTop: 6
    readonly property real plotH: height - padTop - 4
    readonly property var picked: backend.picked
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
        // the hovered stem's, else the selected ones' (backend.rollPicked: only those, never a pass over every block)
        var one = hoverId, b = one !== "" ? s.blocks : backend.rollPicked, vs = [], x = 1e9, top = 0
        for (var i = 0; i < b.length; i++) {
            if ((b[i].type !== "note" && b[i].type !== "hit") || (one !== "" && b[i].id !== one)) continue
            vs.push(b[i].vel)
            var bx = ruler.xOf(b[i].t)
            if (bx < x) { x = bx; top = b[i].vel }
        }
        if (!vs.length || mode === "bar" || mode === "line") return null
        var lo = Math.round(100 * Math.min.apply(null, vs)), hi = Math.round(100 * Math.max.apply(null, vs))
        return { x: x, v: top, text: lo === hi ? lo + " %" : lo + "–" + hi + " %" }
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
    Item {   // the fold arrow and the label: click either to fold or open the strip
        x: 0; width: s.keysWidth; height: s.foldedHeight
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
        HoverTip { text: s.folded ? (s.roll.played ? "Show the velocity strip and the playing lane" : "Show the velocity strip") : "Velocity: how hard each note plays. Drag a bar, or draw a line across. Click to fold it away" + (s.roll.played ? " (with the playing lane under it)" : "")
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
    Rectangle {   // the height being set, beside the pointer
        visible: s.mode === "bar" || s.mode === "line"
        x: Math.min(s.width - width - 2, s.keysWidth + s.px + 10); y: Math.max(0, s.py - height - 4)
        width: tip.implicitWidth + 2 * Theme.grid; height: tip.implicitHeight + 4; radius: 3; color: Theme.raised; border.color: Theme.popupEdge
        Text { id: tip; anchors.centerIn: parent; text: Math.round(100 * s.v) + " %"; color: Theme.fg; font.family: uiFont; font.pixelSize: Theme.label
               font.features: { "tnum": 1 } }
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
        x: s.keysWidth; width: s.width - x; height: s.height
        preventStealing: true; cursorShape: s.hoverId !== "" ? Qt.SizeVerCursor : Qt.CrossCursor;   // the stem under the pointer (set as it moves: an edit never re-reads every stem)
                    hoverEnabled: true
        onWheel: (w) => backend.viewWheel(w.angleDelta.x, w.angleDelta.y, (w.modifiers & Qt.ControlModifier) !== 0,
                                         (w.modifiers & Qt.ShiftModifier) !== 0, w.x / width, true)
        onPressed: (e) => { backend.focusArea("roll"); s.hit = s.nearest(e.x); s.mode = "press"; s.x0 = s.px = e.x; s.y0 = s.py = e.y }
        onPositionChanged: (e) => {
            if (!pressed) { s.hoverId = s.nearest(e.x); return }
            s.px = e.x; s.py = e.y; s.v = s.vAt(e.y)
            if (s.mode === "press" && (Math.abs(e.x - s.x0) >= 4 || Math.abs(e.y - s.y0) >= 4))
                s.mode = backend.beginVelocity(s.hit) ? (s.hit !== "" ? "bar" : "line") : ""
            if (s.mode === "bar") backend.velocityBar(s.v, (e.modifiers & Qt.AltModifier) !== 0)
            else if (s.mode === "line") {
                backend.velocityLine(s.ruler.tOf(s.x0), s.vAt(s.y0), s.ruler.tOf(e.x), s.v); ln.requestPaint()
            }
        }
        onReleased: { if (s.mode === "bar" || s.mode === "line") backend.endVelocity(); s.mode = "" }
        onCanceled: { if (s.mode === "bar" || s.mode === "line") backend.cancelDrag(); s.mode = "" }
    }
}
