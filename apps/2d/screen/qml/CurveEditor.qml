import QtQuick
import RostrumKit

// The timeline's Curves view: the value curves of the selected layer's animated fields over time, on the same time
// scale as the ruler (so the playhead and the full width stay). Left: a legend naming each curve in its colour (click =
// show / hide). Drag a key: time and value (key.set). Drag a round handle: the key's Bézier ease (key.handles; a named
// ease becomes custom). Handles show only for the selected key's stretches and only where the ease has them.
// One MouseArea does the hit-testing, so a drag survives the screen redrawing from its own changes.
Item {
    id: ed
    property Item ruler
    property int labelWidth: 236
    readonly property var fs: backend.curves.fields
    readonly property var shown: fs.filter(f => f.shown)
    readonly property real padY: 14
    readonly property real plotH: plot.height - 2 * padY
    function px(t) { return 8 + ruler.xOf(t) }
    function py(f, v) { return padY + (f.hi - v) / (f.hi - f.lo) * plotH }
    function tOf(x) { return ruler.tOf(x - 8) }
    function vOf(f, y) { return f.hi - (y - padY) / plotH * (f.hi - f.lo) }
    function near(x, y, t, v, f, r) { return Math.hypot(x - px(t), y - py(f, v)) <= r }
    function handlesOf(f) {
        const out = []
        for (const s of f.stretches) out.push({ h: s.h1 }, { h: s.h2 })
        return out
    }
    function hit(x, y) {                       // handles first, then keys; the first one within reach
        for (const f of shown)
            for (const s of f.stretches) {
                if (near(x, y, s.h1[0], s.h1[1], f, 9)) return { handle: true, key: s.key, which: 1, f: f }
                if (near(x, y, s.h2[0], s.h2[1], f, 9)) return { handle: true, key: s.key, which: 2, f: f }
            }
        for (const f of shown)
            for (const k of f.keys)
                if (near(x, y, k.t, k.v, f, 9)) return { handle: false, key: k.id, f: f }
        return null
    }

    Column {   // the legend: in the name column, on the layer rows' own grid (top, height, spacing, text x: LayerName)
        x: Theme.gap; y: 0; width: ed.labelWidth - Theme.gap; spacing: 2
        Repeater {
            model: ed.fs
            delegate: Item {
                id: entry
                required property var modelData
                width: parent.width; height: Theme.row
                opacity: modelData.shown ? 1 : 0.4
                Rectangle { x: Theme.gap + 3; anchors.verticalCenter: parent.verticalCenter; width: 12; height: 3; radius: 1.5
                            color: entry.modelData.color }
                Text {
                    x: Theme.gap + 24; width: parent.width - x - 72; anchors.verticalCenter: parent.verticalCenter
                    elide: Text.ElideRight; text: entry.modelData.label; font.family: uiFont; font.pixelSize: Theme.body
                    color: Theme.fg; font.weight: entry.modelData.selected ? Font.DemiBold : Font.Normal   // its curve is drawn thicker
                }
                Text {
                    anchors { right: parent.right; rightMargin: Theme.gap; verticalCenter: parent.verticalCenter }
                    text: entry.modelData.keys.length ? ed.range(entry.modelData) : ""
                    font.family: uiFont; font.pixelSize: Theme.label; color: Theme.fg2; font.features: { "tnum": 1 }
                }
                Rectangle { anchors { left: parent.left; right: parent.right; bottom: parent.bottom; bottomMargin: -1 }
                            height: 1; color: Theme.border }      // a line between the curves' rows
                MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor
                            onClicked: backend.curves.toggleField(entry.modelData.id) }
            }
        }
    }
    function range(f) {                        // the keys' own lowest and highest value, as words
        const vs = f.keys.map(k => k.v), g = v => Math.round(v * 100) / 100
        return g(Math.min(...vs)) + " – " + g(Math.max(...vs))
    }

    Rectangle {
        id: plot
        x: ruler.x - 8; width: ruler.width + 16; height: parent.height; radius: Theme.radiusCtl; color: Theme.sunken
        clip: true

        // a value label lies at the right edge; a key there (a curve that keys late) would sit on it: the label moves left of it
        function clearOfKeys(x, y, w, h) {
            for (const f of ed.shown) for (const k of f.keys) {
                const kx = ed.px(k.t), ky = ed.py(f, k.v)
                if (ky > y - 8 && ky < y + h + 8 && kx > x - 8 && kx < x + w + 8) x = Math.min(x, kx - w - 12)
            }
            return x
        }
        Repeater {   // faint guides at the top, middle and bottom of the value range
            model: 3
            delegate: Rectangle { required property int index
                                  x: 0; width: plot.width; y: ed.padY + index * ed.plotH / 2; height: 1; color: Theme.border }
        }
        Repeater {   // each curve's lowest and highest key value at the right edge, in the curve's own colour
            model: ed.shown.filter(f => f.keys.length)
            delegate: Item {
                id: axis
                required property var modelData
                required property int index       // each curve's labels stand one step further left: two curves' values at one height never overprint
                readonly property var vs: modelData.keys.map(k => k.v)
                Repeater {
                    model: [Math.max(...axis.vs), Math.min(...axis.vs)]
                    delegate: Text {
                        required property real modelData
                        y: ed.py(axis.modelData, modelData) - height - 3
                        x: plot.clearOfKeys(plot.width - width - 10 - axis.index * 36, y, width, height)   // at the right edge, never on a key
                        text: Math.round(modelData * 100) / 100; font.family: uiFont; font.pixelSize: Theme.label
                        color: axis.modelData.color; opacity: 0.8; font.features: { "tnum": 1 }
                    }
                }
            }
        }
        Text {
            anchors.centerIn: parent; visible: ed.fs.length === 0; color: Theme.fg4; font.family: uiFont; font.pixelSize: Theme.body
            text: "Select a layer with animated fields to see its curves"
        }
        Canvas {
            id: canvas
            anchors.fill: parent
            Connections { target: backend.curves; function onChanged() { canvas.requestPaint() } }
            onWidthChanged: requestPaint()
            onHeightChanged: requestPaint()
            onPaint: {
                const c = getContext("2d")
                c.reset()
                c.lineJoin = "round"
                for (const f of ed.shown) {
                    if (f.path.length === 0) continue
                    const first = f.path[0], last = f.path[f.path.length - 1]
                    c.strokeStyle = f.color
                    c.globalAlpha = 0.4; c.lineWidth = 1.5            // before the first key and after the last: it holds
                    c.beginPath(); c.moveTo(ed.px(0), ed.py(f, first[1])); c.lineTo(ed.px(first[0]), ed.py(f, first[1]))
                    c.moveTo(ed.px(last[0]), ed.py(f, last[1])); c.lineTo(ed.px(ed.ruler.duration), ed.py(f, last[1])); c.stroke()
                    c.globalAlpha = 1; c.lineWidth = f.selected ? 2.5 : 1.75
                    c.beginPath(); c.moveTo(ed.px(first[0]), ed.py(f, first[1]))
                    for (const p of f.path) c.lineTo(ed.px(p[0]), ed.py(f, p[1]))
                    c.stroke()
                    c.globalAlpha = 0.55; c.lineWidth = 1            // handle arms
                    c.beginPath()
                    for (const s of f.stretches) {
                        c.moveTo(ed.px(s.p0[0]), ed.py(f, s.p0[1])); c.lineTo(ed.px(s.h1[0]), ed.py(f, s.h1[1]))
                        c.moveTo(ed.px(s.p3[0]), ed.py(f, s.p3[1])); c.lineTo(ed.px(s.h2[0]), ed.py(f, s.h2[1]))
                    }
                    c.stroke()
                }
            }
        }
        Repeater {
            model: ed.shown
            delegate: Item {
                id: fld
                required property var modelData
                Repeater {   // the handles
                    model: ed.handlesOf(fld.modelData)
                    delegate: Rectangle {
                        required property var modelData
                        x: ed.px(modelData.h[0]) - 5; y: ed.py(fld.modelData, modelData.h[1]) - 5; width: 10; height: 10; radius: 5
                        color: Theme.sunken; border { width: 2; color: fld.modelData.color }
                    }
                }
                Repeater {   // the keys
                    model: fld.modelData.keys
                    delegate: Item {
                        required property var modelData
                        x: ed.px(modelData.t) - 5; y: ed.py(fld.modelData, modelData.v) - 5; width: 10; height: 10
                        Rectangle {
                            anchors.fill: parent; rotation: 45
                            radius: 2; color: modelData.sel ? Theme.fg : fld.modelData.color
                            border { width: 2; color: modelData.sel ? fld.modelData.color : Theme.sunken }
                        }
                        Text {   // a key on a shared marker says which (it moves with the marker)
                            visible: modelData.marker !== ""; text: modelData.marker
                            anchors { horizontalCenter: parent.horizontalCenter; bottom: parent.top; bottomMargin: 4 }
                            font.family: uiFont; font.pixelSize: Theme.label; color: Theme.fg2; font.features: { "tnum": 1 }
                        }
                    }
                }
            }
        }
        MouseArea {
            id: area
            property var grab: null
            anchors.fill: parent; hoverEnabled: true; preventStealing: true
            cursorShape: grab ? Qt.ClosedHandCursor : ed.hit(mouseX, mouseY) ? Qt.OpenHandCursor : Qt.ArrowCursor
            onPressed: (m) => {
                const h = ed.hit(m.x, m.y)
                if (!h) { grab = null; backend.setTime(ed.tOf(m.x)); return }
                if (h.handle ? backend.curves.beginHandleDrag(h.key, h.which) : backend.curves.beginKeyDrag(h.key)) grab = h
            }
            onPositionChanged: (m) => {
                if (!pressed) return
                if (!grab) { backend.setTime(ed.tOf(m.x)); return }
                if (grab.handle) backend.curves.handleTo(ed.tOf(m.x), ed.vOf(grab.f, m.y))
                else backend.curves.keyTo(ed.tOf(m.x), ed.vOf(grab.f, m.y),      // its time snaps within 6 px (time_snap.py; Ctrl: free)
                                          (m.modifiers & Qt.ControlModifier) ? 0 : ed.tOf(6) - ed.tOf(0))
            }
            onReleased: { grab = null; backend.curves.endDrag() }
            onCanceled: { grab = null; backend.curves.endDrag() }
        }
    }
}
