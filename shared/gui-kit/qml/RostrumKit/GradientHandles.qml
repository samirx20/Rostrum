import QtQuick
import QtQuick.Shapes
import "."

// On-canvas handles of a gradient fill (SPEC 6.3, mockup 3): a line from start to end with a ringed dot at each end and
// one per middle stop (linear); a centre dot and ellipse (radial); a centre dot and an angle arm (angular). Dots are
// filled with their stop's colour; the selected stop's ring is the accent. Place the item exactly over the layer's box
// (its 0,0 = the box's top-left on screen, width/height = the box size on screen; the app sizes and rotates it) and set
// `paint` ({type, stops:[{at, color, opacity}], angle, cx, cy}) and `selected` (stop index). The geometry is the
// renderer's CSS one (linear-gradient(<a>deg), radial-gradient(closest-side at cx cy), conic-gradient(from <a>deg at
// cx cy)). Dragging emits a whole new paint through edited(paint) (the input is never changed): began() before the
// first change and ended() after the last make one undo step; stopPicked(index) on a click. Dots keep their screen size.
// With `points` (the layer takes "From point to point": shapes and paths) a linear's two ends and a radial's two radius
// dots set length as well as direction: the paint's span becomes "points" with x1, y1, x2, y2 (linear) or rx, ry
// (radial), fractions of the box; a box-span paint is converted on its first such drag. Dots are named grad_start,
// grad_end, grad_stop<i>, grad_centre, grad_arm, grad_rx, grad_ry (scripted drags: click_steps.py dragobj).
// Every dot stays where it can be grabbed (hand maker rows 22-23: on a wide sky at Fit the ends lay past the canvas, and
// one lay under the open picker): with `reach` (the item the canvas shows in) a dot outside it is drawn just inside its
// edge, and one under `avoid` (a rect in reach's coordinates: the open picker) just beside it, each with a small arrow
// towards where it really is (`pinned`). A drag from there works as from the dot: the end goes where the pointer goes.
// `placed`: anything the host changes that moves the box on screen (a pan, a zoom), so the dots are placed again.
Item {
    id: root
    property var paint: ({type: "linear", stops: [], angle: 90, cx: 0.5, cy: 0.5})
    property int selected: -1
    property bool points: true                 // the layer takes point-to-point spans (not a text's letters)
    property Item reach: null
    property rect avoid: Qt.rect(0, 0, 0, 0)
    property var placed: 0
    readonly property real edge: 12             // a pinned dot's centre this far inside the reach / beside `avoid`
    function shown(d) {                         // the dot's centre as drawn (box px), whether it is pinned, the arrow's angle
        if (!reach || !visible) return {x: d.x, y: d.y, pinned: false, angle: 0}
        const q = root.mapToItem(reach, d.x, d.y), m = edge, A = avoid
        const inside = (x, y) => x >= m && x <= reach.width - m && y >= m && y <= reach.height - m
        let x = clamp(q.x, m, reach.width - m), y = clamp(q.y, m, reach.height - m)
        if (A.width > 0 && x > A.x - m && x < A.x + A.width + m && y > A.y - m && y < A.y + A.height + m) {
            const ways = [[A.x - m, y], [A.x + A.width + m, y], [x, A.y - m], [x, A.y + A.height + m]].filter(p => inside(p[0], p[1]))
            ways.sort((a, b) => Math.hypot(a[0] - x, a[1] - y) - Math.hypot(b[0] - x, b[1] - y))
            if (ways.length) { x = ways[0][0]; y = ways[0][1] }
        }
        if (Math.abs(x - q.x) < 0.5 && Math.abs(y - q.y) < 0.5) return {x: d.x, y: d.y, pinned: false, angle: 0}
        const b = root.mapFromItem(reach, x, y)
        return {x: b.x, y: b.y, pinned: true, angle: Math.atan2(d.y - b.y, d.x - b.x) * 180 / Math.PI}
    }
    signal edited(var paint)
    signal began()
    signal ended()
    signal stopPicked(int index)

    readonly property var stops: paint && paint.stops ? paint.stops : []
    readonly property string kind: paint && paint.type ? paint.type : "linear"
    readonly property real ang: paint && paint.angle !== undefined ? paint.angle : 0
    readonly property real ccx: (paint && paint.cx !== undefined ? paint.cx : 0.5) * width
    readonly property real ccy: (paint && paint.cy !== undefined ? paint.cy : 0.5) * height
    readonly property bool spanned: points && !!paint && paint.span === "points" && (kind === "linear" || kind === "radial")
    function num(k, d) { return paint && paint[k] !== undefined ? paint[k] : d }
    readonly property real rx: spanned ? Math.abs(num("rx", 0.5)) * width : Math.max(0, Math.min(ccx, width - ccx))
    readonly property real ry: spanned ? Math.abs(num("ry", 0.5)) * height : Math.max(0, Math.min(ccy, height - ccy))
    readonly property real arm: 0.35 * Math.min(width, height)
    // linear: the unit direction and the line's two ends
    readonly property real dx: Math.sin(ang * Math.PI / 180)
    readonly property real dy: -Math.cos(ang * Math.PI / 180)
    readonly property real half: (width * Math.abs(dx) + height * Math.abs(dy)) / 2
    readonly property point p0: spanned ? Qt.point(num("x1", 0) * width, num("y1", 0.5) * height)
                                        : Qt.point(width / 2 - dx * half, height / 2 - dy * half)
    readonly property point p1: spanned ? Qt.point(num("x2", 1) * width, num("y2", 0.5) * height)
                                        : Qt.point(width / 2 + dx * half, height / 2 + dy * half)

    // every dot: role (start / end / stop / centre / arm), stop index, centre in box px
    readonly property var dots: {
        const n = stops.length, out = [], col = i => (i >= 0 && i < n ? stops[i].color : "#ffffff")
        if (kind === "linear") {
            out.push({role: "start", index: 0, x: p0.x, y: p0.y, color: col(0)})
            for (let i = 1; i < n - 1; i++)
                out.push({role: "stop", index: i, x: p0.x + (p1.x - p0.x) * stops[i].at, y: p0.y + (p1.y - p0.y) * stops[i].at, color: col(i)})
            out.push({role: "end", index: n - 1, x: p1.x, y: p1.y, color: col(n - 1)})
        } else {
            if (kind === "radial") {
                for (let i = 1; i < n; i++) out.push({role: "stop", index: i, x: ccx + rx * stops[i].at, y: ccy, color: col(i)})
                if (points) {                          // the two radii: left and below the centre
                    out.push({role: "rx", index: -1, x: ccx - rx, y: ccy, color: "#ffffff"})
                    out.push({role: "ry", index: -1, x: ccx, y: ccy + ry, color: "#ffffff"})
                }
            }
            else out.push({role: "arm", index: n - 1, x: ccx + arm * dx, y: ccy + arm * dy, color: col(n - 1)})
            out.push({role: "centre", index: 0, x: ccx, y: ccy, color: col(0)})
        }
        return out
    }

    function clone() { return JSON.parse(JSON.stringify(paint)) }
    function angleOf(vx, vy, snap) {
        let a = Math.round(Math.atan2(vx, -vy) * 1800 / Math.PI) / 10
        if (snap) a = Math.round(a / 15) * 15
        return a > 180 ? a - 360 : a
    }
    function clamp(v, lo, hi) { return Math.max(lo, Math.min(hi, v)) }
    function toPoints(p) {                       // a box-span paint as the same look, point to point
        if (p.span === "points") return
        p.span = "points"
        if (kind === "linear") { p.x1 = p0.x / width; p.y1 = p0.y / height; p.x2 = p1.x / width; p.y2 = p1.y / height }
        else { p.rx = rx / width; p.ry = ry / height }
    }
    function drag(dot, px, py, shift) {          // pointer in box px -> the new paint
        const p = clone()
        if (points && kind === "linear" && (dot.role === "start" || dot.role === "end")) {
            toPoints(p)
            const o = dot.role === "end" ? p0 : p1          // the other end stays; Shift: 15° steps, same length
            if (shift) {
                const a = angleOf(px - o.x, py - o.y, true) * Math.PI / 180, len = Math.hypot(px - o.x, py - o.y)
                px = o.x + Math.sin(a) * len; py = o.y - Math.cos(a) * len
            }
            const k = dot.role === "end" ? "2" : "1"
            p["x" + k] = clamp(px / width, -5, 6); p["y" + k] = clamp(py / height, -5, 6)
        } else if (dot.role === "rx" || dot.role === "ry") {
            toPoints(p)
            const r = dot.role === "rx" ? Math.abs(px - ccx) : Math.abs(py - ccy)    // Shift: a circle on screen
            if (dot.role === "rx" || shift) p.rx = clamp(r / width, 0.001, 6)
            if (dot.role === "ry" || shift) p.ry = clamp(r / height, 0.001, 6)
        } else if (dot.role === "start" || dot.role === "end") {
            const s = dot.role === "end" ? 1 : -1
            p.angle = angleOf(s * (px - width / 2), s * (py - height / 2), shift)
        } else if (dot.role === "arm") {
            p.angle = angleOf(px - ccx, py - ccy, shift)
        } else if (dot.role === "centre") {
            p.cx = clamp(px / width, -0.5, 1.5); p.cy = clamp(py / height, -0.5, 1.5)
        } else if (kind === "linear") {
            const ux = p1.x - p0.x, uy = p1.y - p0.y
            p.stops[dot.index].at = clamp(((px - p0.x) * ux + (py - p0.y) * uy) / (ux * ux + uy * uy), 0, 1)
        } else {
            p.stops[dot.index].at = clamp(rx > 0 ? (px - ccx) / rx : 0, 0, 1)
        }
        return p
    }

    // the lines: a soft dark outline under a 1.5 px white one
    Repeater {
        model: [{w: 3.5, c: Qt.rgba(0, 0, 0, 0.45), dash: false}, {w: 1.5, c: "white", dash: true}]
        Shape {
            anchors.fill: root
            preferredRendererType: Shape.CurveRenderer
            ShapePath {
                strokeWidth: modelData.w; strokeColor: modelData.c; fillColor: "transparent"; capStyle: ShapePath.RoundCap
                PathMultiline {
                    paths: root.kind === "linear" ? [[root.p0, root.p1]]
                         : root.kind === "angular" ? [[Qt.point(root.ccx, root.ccy), Qt.point(root.ccx + root.arm * root.dx, root.ccy + root.arm * root.dy)]]
                         : []
                }
            }
            ShapePath {                                    // radial: the closest-side ellipse, thin and dashed
                strokeWidth: root.kind === "radial" ? modelData.w * 0.6 : 0
                strokeColor: modelData.c; fillColor: "transparent"
                strokeStyle: modelData.dash ? ShapePath.DashLine : ShapePath.SolidLine; dashPattern: [4, 3]
                startX: root.ccx + root.rx; startY: root.ccy
                PathArc { x: root.ccx - root.rx; y: root.ccy; radiusX: root.rx; radiusY: root.ry; useLargeArc: false; direction: PathArc.Counterclockwise }
                PathArc { x: root.ccx + root.rx; y: root.ccy; radiusX: root.rx; radiusY: root.ry; useLargeArc: false; direction: PathArc.Counterclockwise }
            }
        }
    }

    Repeater {
        model: root.dots.length
        Item {
            id: dot
            readonly property var d: root.dots[index] || ({x: 0, y: 0, color: 'white', index: -1, role: ''})
            objectName: "grad_" + dot.d.role + (dot.d.role === "stop" ? dot.d.index : "")
            readonly property var s: (root.placed, root.avoid, root.width, root.height, root.reach ? root.reach.width + root.reach.height : 0, root.shown(dot.d))
            readonly property bool pinned: dot.s.pinned
            x: dot.s.x - 10; y: dot.s.y - 10; width: 20; height: 20
            property bool moved: false
            Item {                                         // pinned: a small arrow towards where the dot really is
                visible: dot.pinned; anchors.fill: parent; rotation: dot.s.angle
                Shape {
                    x: 17; y: 5; width: 8; height: 10
                    preferredRendererType: Shape.CurveRenderer
                    ShapePath {
                        strokeWidth: 1; strokeColor: Qt.rgba(0, 0, 0, 0.45); fillColor: "white"
                        startX: 0; startY: 0
                        PathLine { x: 7; y: 5 }
                        PathLine { x: 0; y: 10 }
                        PathLine { x: 0; y: 0 }
                    }
                }
            }
            Rectangle {                                    // dark halo, white ring, the stop's colour: every dot alike
                anchors.centerIn: parent; width: 18; height: 18; radius: 9; color: Qt.rgba(0, 0, 0, 0.35)
                Rectangle {
                    anchors.centerIn: parent; width: 14; height: 14; radius: 7
                    color: dot.d.color
                    border.width: 2
                    border.color: dot.d.index >= 0 && root.selected === dot.d.index && dot.d.role !== "arm" ? Theme.accent : "white"
                }
            }
            MouseArea {
                anchors.fill: parent
                cursorShape: Qt.SizeAllCursor
                preventStealing: true
                onPressed: if (dot.d.index >= 0) root.stopPicked(dot.d.index)
                onPositionChanged: mouse => {
                    if (!pressed) return
                    if (!dot.moved) { dot.moved = true; root.began() }
                    const q = mapToItem(root, mouse.x, mouse.y)
                    root.edited(root.drag(dot.d, q.x, q.y, mouse.modifiers & Qt.ShiftModifier))
                }
                onReleased: { if (dot.moved) { dot.moved = false; root.ended() } }
            }
        }
    }
}

