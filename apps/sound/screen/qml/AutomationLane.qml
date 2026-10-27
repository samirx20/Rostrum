import QtQuick
import RostrumKit
import RostrumCursors 1.0
import "MixFormat.js" as F
import "Pointers.js" as Pointers
import "Tempo.js" as Tempo

// The automation lane under a track's row (volume, pan, a send's level …): at the left a picker naming what the lane draws
// ("Volume ▾": the lanes on offer for this track) and a close mark; across the time axis the points joined by
// straight lines, the track's own setting as a faint baseline, the selected point's value. Drawing only: presses and
// drags are the Timeline's (backend.laneBegin / laneDrag), so a drag keeps going while the lane is redrawn.
// `ruler` gives the time mapping; `plotX` is where the time axis starts in this row.
// `inEditor`: the Editor's playing lane under its velocity strip (sustain, expression, bend): the picker sits in a row
// above the plot, no close mark, and the lane takes its own presses (the same backend.laneBegin / laneDrag), with
// the same pointer as the Timeline's lanes (the kit's CanvasCursor: make on the line, pick+point over a point, kept
// while a drag runs), the kit's chip ("−6.0 dB at bar 2.3") and Esc putting the point back with no undo step.
Item {
    id: a
    property var row
    property var ruler
    property real plotX: 0
    property bool inEditor: false
    readonly property real chipsH: inEditor ? 20 : 0
    readonly property var none: ({ target: "", lane: "", lo: 0, hi: 1, points: [], choices: [], base: null })
    readonly property var rowv: row || ({ id: "", hue: "transparent", auto: null })   // (a row going away leaves the lane one last time)
    readonly property var auto: rowv.auto || none      // (built while the lane is closed too: nothing to read then)
    readonly property real pad: 8
    readonly property real plotH: height - chipsH - 2 * pad
    readonly property int sel: backend.point.track === rowv.id && backend.point.item === auto.target
                               && backend.point.lane === auto.lane ? backend.point.index : -1
    function yOf(v) { return pad + (1 - (v - auto.lo) / (auto.hi - auto.lo)) * plotH }
    // A volume or level lane is stored as gain and read in dB like the Mixer (F.faderText); other lanes keep their own units
    function show(v) { return auto.gain ? F.faderText(v) : (auto.lo < 0 && v > 0 ? "+" : "") + Number(v).toFixed(2) }
    function scaleLabel(v) { return auto.gain ? (v <= 0 ? "−∞ dB" : F.faderText(v)) : v }

    Rectangle {   // what the lane draws: "Volume ▾", the lanes this row can have
        id: pick
        x: a.inEditor ? plotX : Theme.gap + 11; y: 2; height: 18; radius: 4
        width: Math.min(pickText.implicitWidth + 28, a.inEditor ? ruler.width : plotX - x - 22 - Theme.gap)
        color: pickMenu.visible || pickArea.containsMouse ? Theme.hover : Theme.raised
        Text { id: pickText; x: 7; width: parent.width - 24; anchors.verticalCenter: parent.verticalCenter
               text: a.auto.label || ""; color: Theme.fg; elide: Text.ElideRight
               font.family: uiFont; font.pixelSize: Theme.label }
        Chevron { anchors { right: parent.right; rightMargin: 7; verticalCenter: parent.verticalCenter }
                  color: pickArea.containsMouse ? Theme.fg : Theme.fg3 }
        MouseArea { id: pickArea; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                    onClicked: { pickMenu.entries = a.auto.choices.map(c => ({ value: c.target + "|" + c.lane, label: c.label,
                                     checked: c.target === a.auto.target && c.lane === a.auto.lane }))
                                 const p = pick.mapToItem(null, 0, pick.height + 2); pickMenu.openAt(p.x, p.y) } }
        ActionMenu { id: pickMenu
                     onPicked: (v) => { const k = v.split("|")
                                        if (a.inEditor) backend.openPlayLane(k[1]); else backend.openLane(a.rowv.id, k[0], k[1]) } }
    }
    Text {   // close
        visible: !a.inEditor
        x: plotX - width - Theme.gap; y: 3; text: "×"; color: closeArea.containsMouse ? Theme.fg : Theme.fg3
        font.family: uiFont; font.pixelSize: Theme.title
        MouseArea { id: closeArea; anchors.fill: parent; anchors.margins: -4; hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor; onClicked: backend.openLane(a.rowv.id, "", "") }
    }

    Rectangle {
        id: plot
        x: plotX; y: a.chipsH; width: ruler.width; height: parent.height - a.chipsH; radius: Theme.radiusCtl - 2; color: Theme.sunken; clip: true
        BeatGrid { anchors.fill: parent; ruler: a.ruler }
        Repeater {   // the scale: top and bottom
            model: [a.auto.hi, a.auto.lo]
            delegate: Text { required property real modelData
                x: 4; y: modelData === a.auto.hi ? 2 : parent.height - height - 2
                text: a.scaleLabel(modelData); color: Theme.fg4; font.family: uiFont; font.pixelSize: Theme.label - 2
                font.features: { "tnum": 1 } }
        }
        Rectangle { visible: a.auto.base !== null && a.auto.points.length === 0   // the track's own setting
                    x: 0; width: parent.width; height: 1; y: a.yOf(a.auto.base); color: a.rowv.hue; opacity: 0.45 }
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
                x: x0; y: y0 - 1; width: Math.hypot(x1 - x0, y1 - y0); height: 2; color: a.rowv.hue
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
                color: on ? Theme.accent : a.rowv.hue; border.width: on ? 2 : 0; border.color: Theme.fg
                Text { visible: dot.on; x: 12; y: dot.y > 14 ? -16 : 12
                       text: a.show(dot.modelData.v); color: Theme.fg; font.family: uiFont; font.pixelSize: Theme.label
                       font.features: { "tnum": 1 } }
            }
        }
    }
    MouseArea {   // the Editor's lane takes its own presses (on the Timeline, LaneInput does)
        id: laneArea
        enabled: a.inEditor; visible: enabled
        x: plotX; y: a.chipsH; width: ruler.width; height: parent.height - a.chipsH
        preventStealing: true
        hoverEnabled: true
        acceptedButtons: Qt.LeftButton | Qt.RightButton
        property real x0: 0
        property real y0: 0
        property bool live: false            // a left press's gesture is open
        property bool holding: false         // it holds Esc (dragEsc) once it has moved 4 px
        property bool onPoint: false
        function yFrac(y) { return Math.max(0, Math.min(1, (y - a.pad) / a.plotH)) }
        function near(x, y) { return Pointers.pointNear(a.auto.points, a.ruler.xOf, a.yOf, x, y, 7) >= 0 }
        readonly property string pointer: live ? "point" : onPoint ? "point" : "draw"
        CanvasCursor { objectName: "playLaneCursor"; anchors.fill: parent
                       kind: Pointers.kind(laneArea.pointer); badge: Pointers.badge(laneArea.pointer) }
        function letGo() { if (holding) { holding = false; dragEsc.letEsc() } }
        Connections {   // Esc while a point is dragged: the lane as before, no undo step; the release then does nothing
            target: dragEsc
            function onCancelled() { if (laneArea.holding) { laneArea.holding = false; laneArea.live = false; backend.cancelDrag() } }
        }
        onPressed: (e) => { backend.focusArea("roll")
            if (e.button === Qt.RightButton) {       // a point's menu (Delete point); off every point, none
                pointMenu.entries = backend.pointMenu(a.rowv.id, a.auto.target, a.auto.lane, a.ruler.tOf(e.x), yFrac(e.y),
                                                      7 / a.ruler.perSec, 7 / a.plotH)
                if (pointMenu.entries.length) { var q = mapToItem(null, e.x, e.y); pointMenu.openAt(q.x, q.y) }
                return
            }
            x0 = e.x; y0 = e.y; live = true
            backend.laneBegin(a.rowv.id, a.auto.target, a.auto.lane, a.ruler.tOf(e.x), yFrac(e.y), 7 / a.ruler.perSec,
                              7 / a.plotH, (e.modifiers & Qt.ShiftModifier) !== 0, 1 / a.ruler.perSec) }
        onPositionChanged: (e) => {
            if (!pressed) { onPoint = near(e.x, e.y); return }
            if (!live || !(pressedButtons & Qt.LeftButton)) return
            if (!holding && (Math.abs(e.x - x0) >= 4 || Math.abs(e.y - y0) >= 4)) { holding = true; dragEsc.holdEsc() }
            backend.laneDrag(a.ruler.tOf(e.x), yFrac(e.y), (e.modifiers & Qt.ShiftModifier) !== 0) }
        onReleased: (e) => { if (e.button === Qt.LeftButton && live) backend.endDrag(); live = false; letGo() }
        onCanceled: { if (live) backend.cancelDrag(); live = false; letGo() }
    }
    DragLabel {   // the dragged point's value and place
        at: Qt.point(laneArea.x + laneArea.mouseX, laneArea.y + laneArea.mouseY)
        text: { if (!laneArea.holding || a.sel < 0) return ""
                var p = a.auto.points[a.sel]
                return p ? a.show(p.v) + " at " + Tempo.barName(a.ruler.song, p.t) : "" }
    }
    ActionMenu { id: pointMenu; objectName: "pointMenu"; onPicked: (v) => backend.menuPick(v) }
}
