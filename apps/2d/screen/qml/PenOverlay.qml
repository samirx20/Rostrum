import QtQuick
import QtQuick.Shapes
import RostrumKit
import RostrumCursors 1.0

// The pen tool and a path's points, over the canvas (screen2d/pen.py does the work; the tool rail turns the pen on).
// Pen on: click = corner point, press-drag = smooth point, click the first point = close, Enter / Escape / another tool = made
// (open), then Move with the path selected; no Done (the Pen's hover help says how: Rail2D.qml).
// A path layer whose points are being edited (double-click it or Enter; Esc: its box again) shows its points (square = corner, round = smooth); click a point to select it and its handles show; dragging one is one
// change (Alt: move one handle alone). `ox`, `oy`, `fit`: where the frame sits in this item and its scale.
// Pointers (CURSORS.md, CANVAS 1.3 pen table): the pen with × before a path starts, plain while drawing, ○ over the
// first point (a click closes), ^ over the last (drag: its out handle alone; click: sharp again), − over another point
// (a click removes it), + over the line (a click adds a point, the curve kept); with no path being drawn, a picked
// path's points (−) and line (+) answer the same way. Editing points: a point `pick` + point (Alt: pen −, Alt+click
// removes it), a handle end `pick` + bend, the line pen + (a click adds a point).
Item {
    id: ov
    property real fit: 1
    property real ox: 0
    property real oy: 0
    readonly property var pen: backend.pen
    readonly property var pts: pen.on ? pen.draft : pen.points
    function sx(x) { return ox + x * fit }
    function sy(y) { return oy + y * fit }
    readonly property int sel: pen.selected      // the one point whose handles show
    function svgOf(p, handles) {
        var d = ""
        for (var i = 0; i < p.length; i++) {
            var a = p[i]
            if (handles) {
                if (i === sel && a.smooth) d += "M " + sx(a.inX) + " " + sy(a.inY) + " L " + sx(a.x) + " " + sy(a.y) + " L " + sx(a.outX) + " " + sy(a.outY) + " "
            } else if (i === 0) {
                d = "M " + sx(a.x) + " " + sy(a.y)
            } else {
                var b = p[i - 1]
                d += " C " + sx(b.outX) + " " + sy(b.outY) + " " + sx(a.inX) + " " + sy(a.inY) + " " + sx(a.x) + " " + sy(a.y)
            }
        }
        return d
    }

    readonly property real near: 8 / Math.max(fit, 0.0001)      // 8 screen px, in composition px (pen.CLOSE_PX at 100 %)
    MouseArea {  // the pen's clicks (on top of the canvas's move-drag while the pen is on)
        id: penArea
        anchors.fill: parent
        enabled: ov.pen.on
        visible: enabled        // off: out of the way (a disabled but shown full-canvas area wins the pointer over the canvas)
        hoverEnabled: true
        preventStealing: true
        // What a press here would do = the pen's badge (pen.zone): × no path yet, ○ first point, ^ last point, − another
        // point, + the line; re-read on every move and whenever the points change; kept while the button is down.
        property string zone: "x"
        function look() { if (!pressed && ov.pen.on) zone = ov.pen.zone((mouseX - ov.ox) / ov.fit, (mouseY - ov.oy) / ov.fit, ov.near) }
        Connections { target: ov.pen; function onChanged() { penArea.look() } }
        CanvasCursor { visible: parent.enabled; kind: "pen"; badge: penArea.zone }
        onPressed: (m) => ov.pen.press((m.x - ov.ox) / ov.fit, (m.y - ov.oy) / ov.fit, ov.near)
        onPositionChanged: (m) => { if (pressed) ov.pen.pull((m.x - ov.ox) / ov.fit, (m.y - ov.oy) / ov.fit); else look() }
        onReleased: { ov.pen.release(); look() }
    }
    MouseArea {  // editing a path's points (pen off): its line takes a click (a point there, the curve kept), pen +
        id: lineArea
        anchors.fill: parent
        enabled: ov.pen.editing && !ov.pen.on
        visible: enabled
        hoverEnabled: true
        containmentMask: QtObject {   // only the line itself: elsewhere the canvas under it keeps its own presses
            function contains(p: point) : bool { return lineArea.enabled && ov.pen.zone((p.x - ov.ox) / ov.fit, (p.y - ov.oy) / ov.fit, ov.near) === "copy" }
        }
        CanvasCursor { kind: "pen"; badge: "copy" }
        onPressed: (m) => ov.pen.addOnLine((m.x - ov.ox) / ov.fit, (m.y - ov.oy) / ov.fit, ov.near)
    }
    Shape {  // the path being drawn, and the handles of the points shown
        anchors.fill: parent
        ShapePath {
            strokeColor: Theme.accent; strokeWidth: 1.5; fillColor: "transparent"
            PathSvg { path: ov.pen.on ? ov.svgOf(ov.pts, false) : "" }
        }
        ShapePath {
            strokeColor: Theme.accent; strokeWidth: 1; fillColor: "transparent"
            PathSvg { path: ov.svgOf(ov.pts, true) }
        }
    }
    KeptRepeater {  // kept, so a point keeps its delegate (and its drag) while the path changes under it, and leaving
        needed: ov.pts.length   // the points (Esc) only hides them: a destroyed knob's pointer item went wrong (cursor_item._follow)
        delegate: Item {
            id: knobs
            required property int index
            visible: index < ov.pts.length
            readonly property var p: ov.pts[index] || ({})
            // a sharp point has no handles, a kept knob past the end no point: their place falls back (never undefined)
            readonly property real x0: knobs.p.x !== undefined ? knobs.p.x : 0
            readonly property real y0: knobs.p.y !== undefined ? knobs.p.y : 0
            Knob { i: knobs.index; part: "in"; px: knobs.p.inX !== undefined ? knobs.p.inX : knobs.x0; py: knobs.p.inY !== undefined ? knobs.p.inY : knobs.y0
                   visible: knobs.index === ov.sel && knobs.p.smooth === true; round: true; small: true }
            Knob { i: knobs.index; part: "out"; px: knobs.p.outX !== undefined ? knobs.p.outX : knobs.x0; py: knobs.p.outY !== undefined ? knobs.p.outY : knobs.y0
                   visible: knobs.index === ov.sel && knobs.p.smooth === true; round: true; small: true }
            Knob { i: knobs.index; part: "point"; px: knobs.x0; py: knobs.y0; round: knobs.p.smooth === true }
        }
    }

    component Knob: Rectangle {
        id: k
        property string part
        property real px
        property real py
        property bool round
        property bool small
        property int i
        width: small ? 7 : 9; height: width; radius: round ? width / 2 : 1
        x: ov.sx(px) - width / 2; y: ov.sy(py) - height / 2
        color: part === "point" ? "white" : Theme.accent
        border.width: 1; border.color: Theme.accent
        MouseArea {
            anchors.fill: parent; anchors.margins: -4
            enabled: !ov.pen.on
            visible: enabled        // the pen on: its own area shows the pen's badge here (a shown, disabled area wins the pointer)
            preventStealing: true
            CanvasCursor { kind: k.part === "point" && altHeld ? "pen" : "pick"; badge: k.part !== "point" ? "bend" : altHeld ? "remove" : "point" }
            property point start
            property bool dragging: false
            onPressed: (m) => {
                if (k.part === "point" && (m.modifiers & Qt.AltModifier)) { ov.pen.removePoint(k.i); return }   // Alt+click: pen −
                start = mapToItem(ov, m.x, m.y); if (k.part === "point") ov.pen.selectPoint(k.i); dragging = ov.pen.beginPointDrag(k.i, k.part) }
            onPositionChanged: (m) => {
                if (!dragging) return
                var q = mapToItem(ov, m.x, m.y)
                ov.pen.dragBy((q.x - start.x) / ov.fit, (q.y - start.y) / ov.fit, (m.modifiers & Qt.AltModifier) !== 0)
            }
            onReleased: { if (dragging) ov.pen.endPointDrag(); dragging = false }
            onCanceled: { if (dragging) ov.pen.endPointDrag(); dragging = false }
        }
    }

    KeyShortcut { sequences: ["Return", "Enter", "Escape"]; enabled: ov.pen.on && !OpenPopups.takes(["Enter", "Esc"]); onActivated: { ov.pen.finish(); ov.pen.setOn(false) } }
}
