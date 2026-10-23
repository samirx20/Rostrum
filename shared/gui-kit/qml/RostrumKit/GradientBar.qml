import QtQuick
import "."
import "ColourMath.js" as M

// The gradient's strip with its stops as small handles. Click the strip: a stop is added there in the colour the
// gradient has at that place (until `maxStops`). Drag a stop: it moves. Drag it far off the strip (and let go) or press
// Delete: it goes (never below two). `edited(stops)` gives a new, sorted list; `selected` follows the stop you work on.
//   stops: [{at: 0..1, color: "#rrggbb", opacity: 0..1}]
Item {
    id: bar
    property var stops: []
    property int selected: 0
    property int maxStops: 8
    signal edited(var stops)

    readonly property int inset: 6
    readonly property real span: width - 2 * inset
    property int dragging: -1
    property bool away: false            // dragged off the strip: it goes when let go
    implicitWidth: 234; implicitHeight: 26
    activeFocusOnTab: true

    function xOf(at) { return inset + at * span }
    function copy() { return bar.stops.map(s => ({ at: s.at, color: s.color, opacity: s.opacity === undefined ? 1 : s.opacity })) }
    function remove(i) {
        if (bar.stops.length <= 2 || i < 0) return
        const arr = copy(); arr.splice(i, 1)
        selected = Math.min(i, arr.length - 1)
        edited(arr)
    }
    function put(arr, item) {            // sorted list out; `selected` follows `item`
        const out = M.sorted(arr)
        selected = out.indexOf(item)
        edited(out)
        return selected
    }
    onStopsChanged: { strip.requestPaint(); if (selected >= stops.length) selected = Math.max(0, stops.length - 1) }
    Keys.onDeletePressed: remove(selected)
    Keys.onBackPressed: remove(selected)

    Item {
        id: well
        x: bar.inset; y: 5; width: bar.span; height: 16
        Checker { anchors.fill: parent; radius: 4; cell: 5 }
        Canvas {
            id: strip
            anchors.fill: parent
            onWidthChanged: requestPaint()
            onPaint: {
                const g = getContext("2d")
                g.reset()
                g.roundedRect(0, 0, width, height, 4, 4); g.clip()
                const grad = g.createLinearGradient(0, 0, width, 0)
                M.addStops(grad, M.sorted(bar.stops))
                g.fillStyle = grad; g.fillRect(0, 0, width, height)
            }
        }
    }
    Repeater {
        model: bar.stops
        delegate: Rectangle {
            required property var modelData
            required property int index
            objectName: "stop:" + index
            readonly property bool on: index === bar.selected
            readonly property bool going: on && bar.away && bar.dragging === index
            x: bar.xOf(modelData.at) - width / 2; y: 1; width: 10; height: 24; radius: 4
            color: modelData.color; opacity: going ? 0.35 : 1
            border.width: on ? 2 : 1.5; border.color: on ? Theme.accent : "#ffffff"
            z: on ? 2 : 1
            Rectangle { anchors.fill: parent; anchors.margins: -1; radius: 5; z: -1
                        color: "transparent"; border.width: 1; border.color: Qt.rgba(0, 0, 0, 0.45) }
        }
    }

    MouseArea {
        objectName: "gradientBar"
        anchors.fill: parent
        cursorShape: Qt.PointingHandCursor
        function place(mx) { return M.clamp01((mx - bar.inset) / bar.span) }
        onPressed: (m) => {
            bar.forceActiveFocus()
            let hit = -1, best = 8
            for (let i = 0; i < bar.stops.length; i++) {
                const d = Math.abs(m.x - bar.xOf(bar.stops[i].at))
                if (d < best) { best = d; hit = i }
            }
            if (hit >= 0) { bar.selected = hit; bar.dragging = hit; return }
            if (bar.stops.length >= bar.maxStops) return
            const at = place(m.x), c = M.stopAt(M.sorted(bar.stops), at)
            const ns = { at: at, color: c.color, opacity: c.opacity }
            bar.dragging = bar.put(bar.copy().concat([ns]), ns)
        }
        onPositionChanged: (m) => {
            if (bar.dragging < 0) return
            bar.away = Math.abs(m.y - bar.height / 2) > 24 && bar.stops.length > 2
            const arr = bar.copy(), item = arr[bar.dragging]
            item.at = place(m.x)
            bar.dragging = bar.put(arr, item)
        }
        onReleased: {
            if (bar.away && bar.dragging >= 0) bar.remove(bar.dragging)
            bar.dragging = -1; bar.away = false
        }
    }
}
