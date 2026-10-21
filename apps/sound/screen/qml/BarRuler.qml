import QtQuick
import RostrumKit

// Bars and beats along a width, from the song's tempo and beats per bar: a number at each labelled bar (its
// start in seconds after it, dimmer), beat ticks, the playhead's head. Press or drag sets the time.
// xOf(t) / tOf(x) are the one mapping the rows, markers and piano roll use too.
Item {
    id: r
    readonly property var song: backend.song
    readonly property real length: song.length
    readonly property real barSec: song.spb * song.beatsPerBar
    readonly property real perSec: width / Math.max(length, 0.001)
    readonly property real barPx: barSec * perSec
    readonly property int every: [1, 2, 4, 8, 16, 32].find(n => n * barPx >= 64) || 64   // bars per label
    readonly property bool showSeconds: every * barPx >= 92
    function xOf(t) { return t * perSec }
    function tOf(x) { return Math.max(0, Math.min(length, x / perSec)) }
    implicitHeight: 22

    Repeater {   // beat ticks (when they are far enough apart), bar ticks taller
        model: Math.floor(r.length / r.song.spb + 1e-6) + 1
        delegate: Rectangle {
            required property int index
            readonly property bool bar: index % r.song.beatsPerBar === 0
            visible: bar || r.song.spb * r.perSec >= 10
            x: Math.round(r.xOf(index * r.song.spb)); y: r.height - height
            width: 1; height: bar ? 8 : 4; color: bar ? Theme.lineHover : Theme.line
        }
    }
    Repeater {   // labels
        model: Math.floor(r.length / (r.barSec * r.every) + 1e-6) + 1
        delegate: Row {
            required property int index
            readonly property real t: index * r.every * r.barSec
            x: Math.round(r.xOf(t)) + 4; y: 3; spacing: 5
            visible: r.xOf(t) < r.width - 20
            Text { text: index * r.every + 1; color: Theme.fg2; font.family: uiFont; font.pixelSize: Theme.label
                   font.features: { "tnum": 1 } }
            Text { visible: r.showSeconds; text: (Math.round(parent.t * 10) / 10) + " s"; color: Theme.fg4
                   font.family: uiFont; font.pixelSize: Theme.label - 1; font.features: { "tnum": 1 }
                   anchors.baseline: parent.children[0].baseline }
        }
    }
    MouseArea {
        anchors.fill: parent
        preventStealing: true
        cursorShape: Qt.PointingHandCursor
        onPressed: (m) => backend.setTime(r.tOf(m.x))
        onPositionChanged: (m) => backend.setTime(r.tOf(m.x))
    }
    Rectangle {  // the playhead: a line through the ruler, its head at the top
        x: Math.round(r.xOf(backend.time)); width: 1; height: r.height; color: Theme.accent
        Rectangle { x: -4; y: 0; width: 9; height: 8; radius: 2; color: Theme.accent }
    }
}
