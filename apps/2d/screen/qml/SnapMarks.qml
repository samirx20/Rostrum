import QtQuick
import RostrumKit

// What a canvas drag's snap lines say (2d-pro-workflows SPEC 3.3), over the canvas while the drag lasts: an equal-gap
// bracket's two short ends, and a gap's size ("48") in screen-sized words beside its line or bracket. The lines
// themselves are Stage.qml's (the kit's SnapLine); both read backend.snap.lines (snapper.py: `gap`, `gapAt` 0..1 along
// the line, `mark`) and place them through the stage's one composition mapping (compOrigin, compScale).
Item {
    id: marks
    required property Item stage
    readonly property var lines: backend.snap.lines
    readonly property rect well: stage.compView
    x: stage.x + well.x; y: stage.y + well.y; width: well.width; height: well.height
    clip: true
    KeptRepeater {   // kept: a drag's every move updates them in place, never remakes them
        id: kept
        needed: marks.lines.length
        delegate: Item {
            id: one
            required property int index
            readonly property var e: marks.lines[index] || ({ axis: "x", at: 0, from: 0, to: 0 })
            readonly property bool upright: e.axis === "x"                     // a vertical line or bracket
            readonly property real k: marks.stage.compScale
            readonly property point o: marks.stage.compOrigin
            visible: index < kept.needed && (!!e.mark || !!e.gap)
            x: o.x - marks.well.x + (upright ? Math.round(e.at * k) : e.from * k)
            y: o.y - marks.well.y + (upright ? e.from * k : Math.round(e.at * k))
            width: upright ? 1 : (e.to - e.from) * k
            height: upright ? (e.to - e.from) * k : 1
            Repeater {   // a bracket's two ends, across it
                model: one.e.mark ? 2 : 0
                delegate: Rectangle {
                    required property int index
                    color: Theme.snap
                    width: one.upright ? 7 : 1; height: one.upright ? 1 : 7
                    x: one.upright ? -3 : (index ? one.width - 1 : 0)
                    y: one.upright ? (index ? one.height - 1 : 0) : -3
                }
            }
            Rectangle {   // the gap's size
                visible: !!one.e.gap
                readonly property real along: one.e.gapAt === undefined ? 0.5 : one.e.gapAt
                width: words.implicitWidth + 8; height: words.implicitHeight + 2
                radius: 3
                color: Theme.snap
                x: one.upright ? 6 : one.width * along - width / 2
                y: one.upright ? one.height * along - height / 2 : -height - 5
                Text {
                    id: words
                    anchors.centerIn: parent
                    text: one.e.gap || ""
                    color: Theme.snapText; font.family: uiFont; font.pixelSize: Theme.label
                }
            }
        }
    }
}
