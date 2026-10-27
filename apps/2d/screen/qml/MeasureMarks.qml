import QtQuick
import RostrumKit

// Alt measuring (CANVAS.md §2 row 23): with one layer picked, holding Alt shows red lines and their numbers from it to
// the layer under the pointer, or to the frame's edges over nothing (backend.measure: measure_view.py, measure.py).
// Over the canvas's well, it tells the pointer's place in composition px (read from the canvas's hover, Stage.qml: it never takes a press or a hover), and
// draws the lines through the view's mapping (fit, ox, oy); the numbers are screen-sized at any zoom. Nothing in the
// document changes. `busy`: a press is under way (an Alt-drag copies, an Alt+click picks behind): no lines then.
Item {
    id: marks
    objectName: "measureMarks"
    property real fit: 1
    property real ox: 0
    property real oy: 0
    property bool busy: false
    readonly property color red: "#e0381c"      // local until the kit has a measuring colour (white words on it: 4.3:1)
    readonly property var lines: busy ? [] : backend.measure.lines
    // The pointer, from the canvas's own hover reader (Stage.qml's hoverPick): a HoverHandler here, over the canvas, took
    // every hover from the canvas below (its hover outline and pointer badges went blind).
    property bool hovered: false
    property point at: Qt.point(0, 0)            // in this item's px
    onAtChanged: if (hovered && backend.measure.alt) marks.tell()          // no Python call per move without Alt
    onHoveredChanged: if (!hovered) backend.measure.leave()
    function tell() { backend.measure.hover((at.x - ox) / fit, (at.y - oy) / fit) }
    Connections {   // Alt pressed with the pointer resting: the lines come on the key, not on the next move
        target: backend.measure
        function onAltChanged() { if (backend.measure.alt && marks.hovered) marks.tell() }
    }
    KeptRepeater {   // kept: each move updates the lines in place, never remakes them
        id: kept
        needed: marks.lines.length
        delegate: Item {
            id: one
            required property int index
            readonly property var e: marks.lines[index] || ({ along: "x", at: 0, from: 0, to: 0 })
            readonly property bool across: e.along === "x"                     // a line running left to right
            visible: index < kept.needed
            x: marks.ox + (across ? e.from * marks.fit : Math.round(e.at * marks.fit))
            y: marks.oy + (across ? Math.round(e.at * marks.fit) : e.from * marks.fit)
            width: across ? (e.to - e.from) * marks.fit : 1
            height: across ? 1 : (e.to - e.from) * marks.fit
            Rectangle {   // the line: solid when it measures, a faint thin guide when it only leads to the other box
                anchors.fill: parent
                color: marks.red; opacity: one.e.guide ? 0.5 : 1
            }
            Repeater {    // a measuring line's two end ticks, across it
                model: one.e.guide ? 0 : 2
                delegate: Rectangle {
                    required property int index
                    color: marks.red
                    width: one.across ? 1 : 7; height: one.across ? 7 : 1
                    x: one.across ? (index ? one.width - 1 : 0) : -3
                    y: one.across ? -3 : (index ? one.height - 1 : 0)
                }
            }
            Rectangle {   // the number, in the middle of the line (beside an upright one, above a level one)
                visible: !one.e.guide
                width: words.implicitWidth + 8; height: words.implicitHeight + 2
                radius: 3
                color: marks.red
                x: one.across ? (one.width - width) / 2 : 6
                y: one.across ? -height - 5 : (one.height - height) / 2
                Text {
                    id: words
                    anchors.centerIn: parent
                    text: one.e.gap || ""
                    color: "white"; font.family: uiFont; font.pixelSize: Theme.label
                }
            }
        }
    }
}
