import QtQuick
import RostrumKit

// The shot's frames along a width, from its first frame to where it ends (one past its last frame): ticks, frame
// numbers and the playhead's head. Press or drag scrubs (screen state). xOf(f) / fOf(x) are the one mapping the
// timeline rows use too.
Item {
    id: r
    property int first: 0
    property int last: 47
    property int frame: 0
    readonly property real span: Math.max(1, last + 1 - first)
    readonly property real perFrame: width / span
    // a number every `major` frames (at least ~70 px apart), small ticks every `minor`
    readonly property int major: [1, 2, 5, 10, 20, 50, 100, 200, 500, 1000, 5000].find(n => n * perFrame >= 70) || 10000
    readonly property int minor: major >= 10 ? major / (major % 4 === 0 ? 4 : 5) : 1
    function xOf(f) { return (f - first) * perFrame }
    function fOf(x) { return first + x / perFrame }
    implicitHeight: 22

    Repeater {
        model: Math.floor(r.span / r.minor) + 1
        delegate: Rectangle {
            required property int index
            readonly property int f: r.first + index * r.minor
            readonly property bool big: (f - r.first) % r.major === 0
            x: Math.round(r.xOf(f)); y: r.height - height
            width: 1; height: big ? 7 : 3; color: big ? Theme.lineHover : Theme.line
            Text { visible: parent.big && r.xOf(f) < r.width - 24; x: 4; y: -r.height + 5 + parent.height
                   text: f; color: Theme.fg3; font.family: uiFont; font.pixelSize: Theme.label
                   font.features: { "tnum": 1 } }
        }
    }
    Rectangle {  // the playhead: a line through the ruler, its head at the top
        x: Math.round(r.xOf(r.frame)); width: 1; height: r.height; color: Theme.accent
        Rectangle { x: -4; y: 0; width: 9; height: 8; radius: 2; color: Theme.accent }
    }
    MouseArea {
        anchors.fill: parent
        preventStealing: true
        cursorShape: Qt.PointingHandCursor
        onPressed: (m) => backend.setFrame(Math.round(r.fOf(m.x)))
        onPositionChanged: (m) => backend.setFrame(Math.round(r.fOf(m.x)))
    }
}
