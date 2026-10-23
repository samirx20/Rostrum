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
Item {
    id: root
    property var paint: ({type: "linear", stops: [], angle: 90, cx: 0.5, cy: 0.5})
    property int selected: -1
    signal edited(var paint)
    signal began()
    signal ended()
    signal stopPicked(int index)

    readonly property var stops: paint && paint.stops ? paint.stops : []
    readonly property string kind: paint && paint.type ? paint.type : "linear"
    readonly property real ang: paint && paint.angle !== undefined ? paint.angle : 0
    readonly property real ccx: (paint && paint.cx !== undefined ? paint.cx : 0.5) * width
    readonly property real ccy: (paint && paint.cy !== undefined ? paint.cy : 0.5) * height
    readonly property real rx: Math.max(0, Math.min(ccx, width - ccx))
    readonly property real ry: Math.max(0, Math.min(ccy, height - ccy))
    readonly property real arm: 0.35 * Math.min(width, height)
    // linear: the unit direction and the line's two ends
    readonly property real dx: Math.sin(ang * Math.PI / 180)
    readonly property real dy: -Math.cos(ang * Math.PI / 180)
    readonly property real half: (width * Math.abs(dx) + height * Math.abs(dy)) / 2
    readonly property point p0: Qt.point(width / 2 - dx * half, height / 2 - dy * half)
    readonly property point p1: Qt.point(width / 2 + dx * half, height / 2 + dy * half)

    // every dot: role (start / end / stop / centre / arm), stop index, centre in box px
    readonly property var dots: {
        const n = stops.length, out = [], col = i => (i >= 0 && i < n ? stops[i].color : "#ffffff")
        if (kind === "linear") {
            out.push({role: "start", index: 0, x: p0.x, y: p0.y, color: col(0)})
            for (let i = 1; i < n - 1; i++)
                out.push({role: "stop", index: i, x: p0.x + (p1.x - p0.x) * stops[i].at, y: p0.y + (p1.y - p0.y) * stops[i].at, color: col(i)})
            out.push({role: "end", index: n - 1, x: p1.x, y: p1.y, color: col(n - 1)})
        } else {
            if (kind === "radial")
                for (let i = 1; i < n; i++) out.push({role: "stop", index: i, x: ccx + rx * stops[i].at, y: ccy, color: col(i)})
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
    function drag(dot, px, py, shift) {          // pointer in box px -> the new paint
        const p = clone()
        if (dot.role === "start" || dot.role === "end") {
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
            x: dot.d.x - 10; y: dot.d.y - 10; width: 20; height: 20
            property bool moved: false
            Rectangle {                                    // dark halo, white ring, the stop's colour
                anchors.centerIn: parent; width: 18; height: 18; radius: 9; color: Qt.rgba(0, 0, 0, 0.35)
                Rectangle {
                    anchors.centerIn: parent; width: 14; height: 14; radius: 7
                    color: dot.d.color
                    border.width: 2
                    border.color: root.selected === dot.d.index && dot.d.role !== "arm" ? Theme.accent : "white"
                }
            }
            MouseArea {
                anchors.fill: parent
                cursorShape: Qt.SizeAllCursor
                preventStealing: true
                onPressed: root.stopPicked(dot.d.index)
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

