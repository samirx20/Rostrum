import QtQuick
import "."

// A curve of points "x,y x,y …": x from 0 to 1, y from 0 to `most`. With most = 1 it maps going in to coming out (a
// brightness curve; unchanged = the diagonal); with most above 1 it is a multiplier along x (a stroke's width profile;
// unchanged = flat at 1). `neutral` is the curve that changes nothing: drawn dashed, and shown for an empty value.
// Drawn as the smooth curve the engine uses (monotone cubic, never overshooting a point; flat beyond the ends). Drag a point to move it (it stays
// between its neighbours); press on an empty spot to add a point there and drag it; double-click a point to remove it
// (two always stay). Each press-drag-release is one `edited` = one change = one undo step; the readout shows the
// point while it moves.
Item {
    id: f
    property string value: ""
    property real most: 1     // the top of the out range
    property string neutral: most > 1 ? "0,1 1,1" : "0,0 1,1"
    signal edited(string value)
    implicitWidth: Theme.curveBox
    implicitHeight: Theme.curveBox       // fixed: the inspector row sizes itself from it

    property var pts: parse(value)
    onValueChanged: pts = parse(value)
    property int active: -1

    function parse(text) {
        var out = []
        var parts = (text || "").trim().split(/\s+/)
        for (var i = 0; i < parts.length; i++) {
            var xy = parts[i].split(",")
            if (xy.length === 2 && !isNaN(+xy[0]) && !isNaN(+xy[1])) out.push([+xy[0], +xy[1]])
        }
        return out.length >= 2 ? out : text === f.neutral ? [[0, 0], [1, 1]] : parse(f.neutral)
    }
    function fmt(v) { return (Math.round(v * 1000) / 1000).toString() }
    function text(p) { return p.map(function (q) { return fmt(q[0]) + "," + fmt(q[1]) }).join(" ") }
    // the engine's curve (render/src/scene/grade_curve.rs `through`): PCHIP tangents, Hermite segments
    function through(p, x) {
        var n = p.length
        if (x <= p[0][0]) return p[0][1]
        if (x >= p[n - 1][0]) return p[n - 1][1]
        function slope(i) { return (p[i + 1][1] - p[i][1]) / (p[i + 1][0] - p[i][0]) }
        function tangent(i) {
            if (i === 0 || i === n - 1) return slope(Math.min(i, n - 2))
            var d0 = slope(i - 1), d1 = slope(i)
            if (d0 * d1 <= 0) return 0
            var h0 = p[i][0] - p[i - 1][0], h1 = p[i + 1][0] - p[i][0]
            var w0 = 2 * h1 + h0, w1 = h1 + 2 * h0
            return (w0 + w1) / (w0 / d0 + w1 / d1)
        }
        var k = 0
        while (k < n - 2 && x > p[k + 1][0]) k++
        var h = p[k + 1][0] - p[k][0], t = (x - p[k][0]) / h, t2 = t * t, t3 = t2 * t
        var y = (2 * t3 - 3 * t2 + 1) * p[k][1] + (t3 - 2 * t2 + t) * h * tangent(k)
              + (-2 * t3 + 3 * t2) * p[k + 1][1] + (t3 - t2) * h * tangent(k + 1)
        return Math.max(0, Math.min(f.most, y))
    }

    Rectangle {
        id: graph
        width: Math.max(48, Math.min(f.width, f.implicitHeight)); height: width
        radius: Theme.radiusCtl; color: Theme.sunken; border.width: 1; border.color: Theme.popupEdge
        readonly property real pad: 6
        readonly property real side: width - 2 * pad
        function sx(x) { return pad + x * side }
        function sy(y) { return pad + (1 - y / f.most) * side }

        Canvas {
            id: canvas
            anchors.fill: parent
            property var pts: f.pts
            onPtsChanged: requestPaint()
            onPaint: {
                var g = getContext("2d"), p = f.pts, s = graph.side, o = graph.pad
                g.reset()
                g.strokeStyle = Theme.popupEdge; g.lineWidth = 1
                for (var i = 1; i < 4; i++) {                                    // quarter lines
                    g.beginPath(); g.moveTo(o + s * i / 4, o); g.lineTo(o + s * i / 4, o + s); g.stroke()
                    g.beginPath(); g.moveTo(o, o + s * i / 4); g.lineTo(o + s, o + s * i / 4); g.stroke()
                }
                var u = f.parse(f.neutral)                                         // unchanged
                g.strokeStyle = Theme.fg4; g.setLineDash([3, 3]); g.beginPath()
                for (var j = 0; j < u.length; j++)
                    if (j === 0) g.moveTo(graph.sx(u[j][0]), graph.sy(u[j][1])); else g.lineTo(graph.sx(u[j][0]), graph.sy(u[j][1]))
                g.stroke(); g.setLineDash([])
                g.strokeStyle = Theme.accent; g.lineWidth = 1.5
                g.beginPath()
                for (var k = 0; k <= 64; k++) {
                    var x = k / 64, y = f.through(p, x)
                    if (k === 0) g.moveTo(graph.sx(x), graph.sy(y)); else g.lineTo(graph.sx(x), graph.sy(y))
                }
                g.stroke()
            }
        }
        Repeater {
            model: f.pts.length
            delegate: Rectangle {
                required property int index
                width: 9; height: 9; radius: 4.5
                x: graph.sx(f.pts[index][0]) - 4.5; y: graph.sy(f.pts[index][1]) - 4.5
                color: index === f.active ? Theme.accent : "white"; border.width: 1; border.color: Theme.accent
            }
        }
        Text {  // the moving point's values
            visible: f.active >= 0
            anchors { left: parent.left; top: parent.top; margins: graph.pad + 2 }
            text: f.active < 0 ? "" : f.most > 1 ? "at " + f.fmt(f.pts[f.active][0]) + "  × " + f.fmt(f.pts[f.active][1])
                                                : "in " + f.fmt(f.pts[f.active][0]) + "  out " + f.fmt(f.pts[f.active][1])
            color: Theme.fg2; font.family: monoFont; font.pixelSize: Theme.label
        }
        MouseArea {
            anchors.fill: parent
            preventStealing: true
            function at(m) {
                return [Math.max(0, Math.min(1, (m.x - graph.pad) / graph.side)),
                        Math.max(0, Math.min(f.most, (1 - (m.y - graph.pad) / graph.side) * f.most))]
            }
            function near(m) {
                for (var i = 0; i < f.pts.length; i++)
                    if (Math.abs(graph.sx(f.pts[i][0]) - m.x) < 8 && Math.abs(graph.sy(f.pts[i][1]) - m.y) < 8) return i
                return -1
            }
            onPressed: (m) => {
                var i = near(m)
                if (i < 0) {                                                    // a new point where pressed
                    var q = at(m), p = f.pts.slice()
                    i = 0
                    while (i < p.length && p[i][0] < q[0]) i++
                    if ((i > 0 && q[0] - p[i - 1][0] < 0.01) || (i < p.length && p[i][0] - q[0] < 0.01)) { f.active = -1; return }
                    p.splice(i, 0, q)
                    f.pts = p
                }
                f.active = i
            }
            onPositionChanged: (m) => {
                if (f.active < 0) return
                var q = at(m), p = f.pts.slice(), i = f.active
                var lo = i > 0 ? p[i - 1][0] + 0.01 : 0, hi = i < p.length - 1 ? p[i + 1][0] - 0.01 : 1
                p[i] = [Math.max(lo, Math.min(hi, q[0])), q[1]]
                f.pts = p
            }
            onReleased: { if (f.active >= 0) f.edited(f.text(f.pts)); f.active = -1 }
            onCanceled: { f.active = -1; f.pts = f.parse(f.value) }
            onDoubleClicked: (m) => {
                var i = near(m)
                if (i >= 0 && f.pts.length > 2) { var p = f.pts.slice(); p.splice(i, 1); f.edited(f.text(p)) }
            }
        }
    }
}
