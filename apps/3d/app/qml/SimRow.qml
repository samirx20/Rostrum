import QtQuick
import RostrumKit

// The Simulate row under the timeline's rows (SPEC §10, mockup 10; screen3d/sim_qt.py: backend.sim). There only while
// the shot's scene has bodies (Falls or Stays still). Left, in the names column: "Simulation" and Simulate (while
// there is something to compute). Right, under the ruler, over the shot's frames: a bar that is empty with
// "Not computed", fills left to right with the frames while the job runs (scrubbing works meanwhile), is solid once
// stored ("Stored · 120 frames") and striped once an input changed ("Out of date"; the viewport keeps the old result).
// A failure is the core's line in red (which body, which frame, what to do) until the next Simulate.
Item {
    id: row
    objectName: "simRow"
    property Item ruler
    property int labelWidth: 240
    readonly property var sim: backend.sim
    readonly property bool failed: sim.state === "failed"
    readonly property bool stale: sim.state === "out of date"
    readonly property var info: backend.shotInfo
    height: sim.shown ? Theme.button + 4 : 0
    visible: sim.shown
    Rectangle { anchors.fill: parent; color: Theme.panel }        // over the rows it is pinned on (SceneList.qml)
    Rectangle { width: parent.width; height: 1; color: Theme.line }

    Text {
        x: Theme.gap + 16; width: row.labelWidth - x - simulate.width - 2 * Theme.gap
        anchors.verticalCenter: parent.verticalCenter
        text: "Simulation"; elide: Text.ElideRight
        color: Theme.fg; font.family: uiFont; font.pixelSize: Theme.body
    }
    Button {
        id: simulate
        objectName: "simRun"
        visible: row.sim.canRun
        width: visible ? implicitWidth : 0
        x: row.labelWidth - width - Theme.gap; anchors.verticalCenter: parent.verticalCenter
        text: row.failed ? "Try again" : "Simulate"
        kind: "primary"         // the row's one action: the kit's filled button in every state it is offered
        help: "Computes how the bodies fall over the shot's frames and stores it; scrubbing and renders read it."
        onClicked: row.sim.simulate()
    }

    Item {      // the bar over the shot's frames, under the ruler (at ruler.x - 8 like the key tracks)
        id: track
        readonly property real x0: row.ruler ? row.ruler.x + row.ruler.xOfSec(row.info.start / row.info.fps) : 0
        readonly property real x1: row.ruler ? row.ruler.x + row.ruler.xOfSec((row.info.end + 1) / row.info.fps) : 0
        x: x0; width: Math.max(0, x1 - x0); height: Theme.rowDense - 4
        anchors.verticalCenter: parent.verticalCenter
        Rectangle {     // the outline: the whole shot
            id: frame
            objectName: "simBar"
            anchors.fill: parent; radius: Theme.radiusCtl; clip: true
            color: "transparent"; border.width: 1
            border.color: row.failed ? Theme.danger : row.sim.filled > 0 ? Theme.accent : Theme.lineHover
            Rectangle {     // the frames computed (running) or stored
                width: Math.round(parent.width * row.sim.filled); height: parent.height; radius: Theme.radiusCtl
                color: Theme.accentSoft
                visible: !row.stale && !row.failed
                Behavior on width { NumberAnimation { duration: 80 } }
            }
            Canvas {        // out of date: the stored bar, striped
                id: stripes
                objectName: "simStripes"
                anchors.fill: parent; anchors.margins: 1
                visible: row.stale
                onWidthChanged: requestPaint()
                onVisibleChanged: requestPaint()
                onPaint: {
                    const c = getContext("2d")
                    c.reset()
                    c.strokeStyle = Qt.rgba(76 / 255, 141 / 255, 1, 0.3); c.lineWidth = 3
                    for (let x = -height; x < width + height; x += 10) {
                        c.beginPath(); c.moveTo(x, height); c.lineTo(x + height, 0); c.stroke()
                    }
                }
            }
            Text {
                id: words
                objectName: "simLabel"
                anchors { left: parent.left; leftMargin: Theme.gap; right: parent.right; rightMargin: Theme.gap; verticalCenter: parent.verticalCenter }
                text: row.sim.label; elide: Text.ElideRight
                color: row.failed ? Theme.danger : Theme.fg; font.family: uiFont; font.pixelSize: Theme.label
                font.weight: row.failed ? Font.DemiBold : Font.Normal
                HoverHandler { id: wordsHover }
                HoverTip { text: words.truncated ? words.text : ""; hovered: wordsHover.hovered }
            }
        }
    }
}
