import QtQuick
import RostrumKit

// The velocity strip under the Editor's roll (DESIGN.md §3.3d): one bar per note (or drum hit) at its start, as high
// as it is loud. Drag a bar: that note (a selected bar takes every selected note with it by the same proportion;
// Alt = all to the same height). Drag across empty space: a line, and each note under it (the selected ones, when
// some are) takes the line's height. One drag is one undo step (backend.beginVelocity … endVelocity); the number
// beside the pointer is the height being set. The fold arrow at the left folds it to one thin row (the person's own
// screen state: backend.velocityFolded); the roll takes the room.
Item {
    id: s
    property var roll
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
    function vAt(y) { return Math.max(0, Math.min(1, 1 - (y - padTop) / plotH)) }
    function nearest(x) {                       // the bar under x (within 5 px), "" for none
        var b = roll.blocks || [], best = "", d = 6
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
               text: "Vel"; color: Theme.fg4; font.family: uiFont; font.pixelSize: Theme.label }
        MouseArea { id: vh; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                    onClicked: backend.toggleVelocityFold() }
        HoverTip { text: s.folded ? (s.roll.played ? "Show the velocity strip and the playing lane" : "Show the velocity strip") : "Velocity: how hard each note plays. Drag a bar, or draw a line across. Click to fold it away" + (s.roll.played ? " (with the playing lane under it)" : "")
                   hovered: vh.containsMouse; pressed: vh.pressed }
    }
    Rectangle { visible: !s.folded; x: s.keysWidth; width: s.width - x; height: s.height; radius: Theme.radiusCtl; color: Theme.sunken
                border.color: Theme.border; border.width: 1 }
    Canvas {
        id: c
        visible: !s.folded
        x: s.keysWidth; width: s.width - x; height: s.height; clip: true
        onWidthChanged: requestPaint()
        onHeightChanged: requestPaint()
        Connections { target: s; function onRollChanged() { c.requestPaint() } function onPickedChanged() { c.requestPaint() } }
        Connections { target: s.ruler; function onStartChanged() { c.requestPaint() } function onPerSecChanged() { c.requestPaint() } }
        onPaint: {
            var ctx = getContext("2d"); ctx.reset()
            ctx.fillStyle = Theme.border; ctx.fillRect(0, s.padTop + s.plotH / 2, width, 1)      // the half-way guide
            var b = s.roll.blocks || [], on = s.picked
            for (var pass = 0; pass < 2; pass++)           // selected bars last, on top
                for (var i = 0; i < b.length; i++) {
                    if (b[i].type !== "note" && b[i].type !== "hit") continue
                    if (!!on[b[i].id] !== (pass === 1)) continue
                    var x = Math.round(s.ruler.xOf(b[i].t))
                    if (x < -4 || x > width + 4) continue
                    var h = Math.max(2, b[i].vel * s.plotH)
                    ctx.fillStyle = pass === 1 ? Theme.accent : s.roll.hue
                    ctx.globalAlpha = pass === 1 ? 1 : 0.8
                    ctx.fillRect(x - 1, s.padTop + s.plotH - h, 3, h)
                    ctx.beginPath(); ctx.arc(x + 0.5, s.padTop + s.plotH - h, 3, 0, 2 * Math.PI); ctx.fill()   // the grip
                }
            ctx.globalAlpha = 1
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
        Text { id: tip; anchors.centerIn: parent; text: s.v.toFixed(2); color: Theme.fg; font.family: uiFont; font.pixelSize: Theme.label
               font.features: { "tnum": 1 } }
    }
    MouseArea {
        id: m
        enabled: !s.folded
        x: s.keysWidth; width: s.width - x; height: s.height
        preventStealing: true; cursorShape: s.nearest(mouseX) !== "" ? Qt.SizeVerCursor : Qt.CrossCursor; hoverEnabled: true
        onWheel: (w) => backend.viewWheel(w.angleDelta.x, w.angleDelta.y, (w.modifiers & Qt.ControlModifier) !== 0,
                                         (w.modifiers & Qt.ShiftModifier) !== 0, w.x / width, true)
        onPressed: (e) => { backend.focusArea("roll"); s.hit = s.nearest(e.x); s.mode = "press"; s.x0 = s.px = e.x; s.y0 = s.py = e.y }
        onPositionChanged: (e) => {
            if (!pressed) return
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
