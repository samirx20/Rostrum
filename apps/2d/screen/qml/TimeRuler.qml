import QtQuick
import RostrumKit

// Seconds along a width: ticks, labels and the playhead's head. Press or drag sets the time (screen state).
// xOf(t) / tOf(x) are the one mapping the timeline rows use too. The project's shared markers show as flags.
Item {
    id: r
    property real duration: 1
    property real fps: 30
    property real time: 0
    readonly property real perSec: width / Math.max(duration, 0.001)
    // label every `major` seconds (at least ~90 px apart), small ticks every `minor`
    readonly property real major: [0.1, 0.25, 0.5, 1, 2, 5, 10, 30, 60, 300].find(s => s * perSec >= 90) || 600
    readonly property real minor: major / (major === 1 || major === 2 ? 4 : 5)
    function xOf(t) { return t * perSec }
    function tOf(x) { return Math.max(0, Math.min(duration, x / perSec)) }
    function label(t) { return t >= 60 ? Math.floor(t / 60) + ":" + ("0" + Math.round(t % 60)).slice(-2)
                                        : (Math.round(t * 100) / 100) + "s" }
    implicitHeight: 22

    Repeater {
        model: Math.floor(r.duration / r.minor + 1e-6) + 1
        delegate: Rectangle {
            required property int index
            readonly property bool big: Math.abs((index * r.minor / r.major) - Math.round(index * r.minor / r.major)) < 1e-6
            x: Math.round(r.xOf(index * r.minor)); y: r.height - height
            width: 1; height: big ? 7 : 3; color: big ? Theme.lineHover : Theme.line
            Text { visible: parent.big && r.xOf(index * r.minor) < r.width - 24; x: 4; y: -r.height + 5 + parent.height
                   text: r.label(index * r.minor); color: Theme.fg3; font.family: uiFont; font.pixelSize: Theme.label
                   font.features: { "tnum": 1 } }
        }
    }
    Repeater {   // the project's shared markers (rostrum_core.markers): a flag with its name
        model: backend.markers
        delegate: Item {
            required property var modelData
            x: Math.round(r.xOf(modelData.at)); width: 1; height: r.height
            Rectangle { width: 1; height: parent.height; color: Theme.warn }
            Rectangle {
                id: flag
                x: 1; y: 0; height: 16; radius: 2; color: Theme.panel; border.color: Theme.warn
                width: Math.min(name.implicitWidth + 8, Math.max(r.width - parent.x - 1, 14))
                clip: true
                Text { id: name; x: 4; anchors.verticalCenter: parent.verticalCenter; text: modelData.name
                       color: Theme.warn; font.family: uiFont; font.pixelSize: Theme.label - 1 }
            }
        }
    }
    Rectangle {  // the playhead: a line through the ruler, its head at the top
        x: Math.round(r.xOf(r.time)); width: 1; height: r.height; color: Theme.accent
        Rectangle { x: -4; y: 0; width: 9; height: 8; radius: 2; color: Theme.accent }
    }
    MouseArea {
        anchors.fill: parent
        preventStealing: true
        cursorShape: Qt.PointingHandCursor
        onPressed: (m) => backend.setTime(r.tOf(m.x))
        onPositionChanged: (m) => backend.setTime(r.tOf(m.x))
    }
}
