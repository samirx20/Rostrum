import QtQuick
import RostrumKit

// The automation lane under a track's row (volume, pan, a send's level …): at the left the lanes on offer for this
// track (pick one; a dot marks lanes that hold points) and a close mark; across the time axis the points joined by
// straight lines, the track's own setting as a faint baseline, the selected point's value. Drawing only: presses and
// drags are the Timeline's (backend.laneBegin / laneDrag), so a drag keeps going while the lane is redrawn.
// `ruler` gives the time mapping; `plotX` is where the time axis starts in this row.
Item {
    id: a
    property var row
    property var ruler
    property real plotX: 0
    readonly property var none: ({ target: "", lane: "", lo: 0, hi: 1, points: [], choices: [], base: null })
    readonly property var auto: row.auto || none      // (built while the lane is closed too: nothing to read then)
    readonly property real pad: 8
    readonly property real plotH: height - 2 * pad
    readonly property int sel: backend.point.track === row.id && backend.point.item === auto.target
                               && backend.point.lane === auto.lane ? backend.point.index : -1
    function yOf(v) { return pad + (1 - (v - auto.lo) / (auto.hi - auto.lo)) * plotH }
    function show(v) { return (auto.lo < 0 && v > 0 ? "+" : "") + Number(v).toFixed(2) }

    Flow {   // which lane: one chip each
        x: Theme.gap + 11; y: 2; width: plotX - x - 22 - Theme.gap; spacing: 3
        Repeater {
            model: a.auto.choices
            delegate: Rectangle {
                required property var modelData
                readonly property bool on: modelData.target === a.auto.target && modelData.lane === a.auto.lane
                width: chipText.implicitWidth + (modelData.used ? 18 : 12); height: 16; radius: 4
                color: on ? Theme.accentSoft : chipArea.containsMouse ? Theme.hover : Theme.raised
                border.width: on ? 1 : 0; border.color: Theme.accent
                Row { anchors.centerIn: parent; spacing: 4
                      Rectangle { visible: modelData.used; width: 5; height: 5; radius: 2.5; color: a.row.hue
                                  anchors.verticalCenter: parent.verticalCenter }
                      Text { id: chipText; text: modelData.label; color: on ? Theme.fg : Theme.fg2
                             font.family: uiFont; font.pixelSize: Theme.label - 1 } }
                MouseArea { id: chipArea; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                            onClicked: backend.openLane(a.row.id, modelData.target, modelData.lane) }
            }
        }
    }
    Text {   // close
        x: plotX - width - Theme.gap; y: 3; text: "×"; color: closeArea.containsMouse ? Theme.fg : Theme.fg3
        font.family: uiFont; font.pixelSize: Theme.title
        MouseArea { id: closeArea; anchors.fill: parent; anchors.margins: -4; hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor; onClicked: backend.openLane(a.row.id, "", "") }
    }

    Rectangle {
        id: plot
        x: plotX; width: ruler.width; height: parent.height; radius: Theme.radiusCtl - 2; color: Theme.sunken; clip: true
        BeatGrid { anchors.fill: parent; ruler: a.ruler }
        Repeater {   // the scale: top and bottom
            model: [a.auto.hi, a.auto.lo]
            delegate: Text { required property real modelData
                x: 4; y: modelData === a.auto.hi ? 2 : parent.height - height - 2
                text: modelData; color: Theme.fg4; font.family: uiFont; font.pixelSize: Theme.label - 2
                font.features: { "tnum": 1 } }
        }
        Rectangle { visible: a.auto.base !== null && a.auto.points.length === 0   // the track's own setting
                    x: 0; width: parent.width; height: 1; y: a.yOf(a.auto.base); color: a.row.hue; opacity: 0.45 }
        Text { visible: a.auto.points.length === 0; anchors.centerIn: parent
               text: "Click to add a point  ·  the line is the track's own setting"; color: Theme.fg4
               font.family: uiFont; font.pixelSize: Theme.label }
        Repeater {   // straight lines: a hold before the first point and after the last, a segment between points
            model: a.auto.points.length === 0 ? 0 : a.auto.points.length + 1
            delegate: Rectangle {
                required property int index
                readonly property var p0: index === 0 ? null : a.auto.points[index - 1]
                readonly property var p1: index === a.auto.points.length ? null : a.auto.points[index]
                readonly property real x0: p0 ? a.ruler.xOf(p0.t) : 0
                readonly property real y0: p0 ? a.yOf(p0.v) : a.yOf(p1.v)
                readonly property real x1: p1 ? a.ruler.xOf(p1.t) : plot.width
                readonly property real y1: p1 ? a.yOf(p1.v) : y0
                x: x0; y: y0 - 1; width: Math.hypot(x1 - x0, y1 - y0); height: 2; color: a.row.hue
                opacity: p0 && p1 ? 1 : 0.5; antialiasing: true
                transformOrigin: Item.Left; rotation: Math.atan2(y1 - y0, x1 - x0) * 180 / Math.PI
            }
        }
        Repeater {
            model: a.auto.points
            delegate: Rectangle {
                id: dot
                required property var modelData
                required property int index
                readonly property bool on: index === a.sel
                x: a.ruler.xOf(modelData.t) - width / 2; y: a.yOf(modelData.v) - height / 2
                width: on ? 11 : 9; height: width; radius: width / 2
                color: on ? Theme.accent : a.row.hue; border.width: on ? 2 : 0; border.color: Theme.fg
                Text { visible: dot.on; x: 12; y: dot.y > 14 ? -16 : 12
                       text: a.show(dot.modelData.v); color: Theme.fg; font.family: uiFont; font.pixelSize: Theme.label
                       font.features: { "tnum": 1 } }
            }
        }
    }
}
