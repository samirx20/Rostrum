import QtQuick
import QtQuick.Shapes
import RostrumKit

// The pen tool and a path's points, over the canvas (screen2d/pen.py does the work; the tool strip turns the pen on).
// Pen on: click = corner point, press-drag = smooth point, click the first point = close, Enter / Escape = done.
// A selected path layer shows its points (square = corner, round = smooth); click a point to select it and its handles show; dragging one is one
// change (Alt: move one handle alone). `ox`, `oy`, `fit`: where the frame sits in this item and its scale.
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

    MouseArea {  // the pen's clicks (on top of the canvas's move-drag while the pen is on)
        anchors.fill: parent
        enabled: ov.pen.on
        cursorShape: Qt.CrossCursor
        preventStealing: true
        onPressed: (m) => ov.pen.press((m.x - ov.ox) / ov.fit, (m.y - ov.oy) / ov.fit)
        onPositionChanged: (m) => ov.pen.pull((m.x - ov.ox) / ov.fit, (m.y - ov.oy) / ov.fit)
        onReleased: ov.pen.release()
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
    Repeater {  // by count, so a point keeps its delegate (and its drag) while the path changes under it
        model: ov.pts.length
        delegate: Item {
            id: knobs
            required property int index
            readonly property var p: ov.pts[index] || ({})
            Knob { i: knobs.index; part: "in"; px: knobs.p.inX; py: knobs.p.inY; visible: knobs.index === ov.sel && knobs.p.smooth === true; round: true; small: true }
            Knob { i: knobs.index; part: "out"; px: knobs.p.outX; py: knobs.p.outY; visible: knobs.index === ov.sel && knobs.p.smooth === true; round: true; small: true }
            Knob { i: knobs.index; part: "point"; px: knobs.p.x; py: knobs.p.y; round: knobs.p.smooth === true }
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
            cursorShape: Qt.SizeAllCursor
            preventStealing: true
            property point start
            property bool dragging: false
            onPressed: (m) => { start = mapToItem(ov, m.x, m.y); if (k.part === "point") ov.pen.selectPoint(k.i); dragging = ov.pen.beginPointDrag(k.i, k.part) }
            onPositionChanged: (m) => {
                if (!dragging) return
                var q = mapToItem(ov, m.x, m.y)
                ov.pen.dragBy((q.x - start.x) / ov.fit, (q.y - start.y) / ov.fit, (m.modifiers & Qt.AltModifier) !== 0)
            }
            onReleased: { if (dragging) ov.pen.endPointDrag(); dragging = false }
            onCanceled: { if (dragging) ov.pen.endPointDrag(); dragging = false }
        }
    }

    Text {
        visible: ov.pen.on
        anchors { horizontalCenter: parent.horizontalCenter; bottom: parent.bottom; bottomMargin: Theme.pad }
        text: ov.pts.length === 0 ? "Click for a corner, drag for a curve"
            : "Click the first point to close  ·  Enter to finish"
        color: Theme.fg3; font.family: uiFont; font.pixelSize: Theme.body
    }
    Shortcut { sequences: ["Return", "Enter", "Escape"]; enabled: ov.pen.on; onActivated: { ov.pen.finish(); ov.pen.setOn(false) } }
}
