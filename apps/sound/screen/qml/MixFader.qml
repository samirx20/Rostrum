import QtQuick
import RostrumKit
import "MixFormat.js" as F

// A vertical level fader (gain, taper in MixFormat.js). Press jumps there, dragging follows; press to release is
// one gesture: scrubStarted, scrubbed(gain)…, scrubEnded (the app records it as ONE change).
Item {
    id: f
    property real gain: 1
    readonly property real pos: F.posOf(gain)
    signal scrubStarted()
    signal scrubbed(real gain)
    signal scrubEnded()
    implicitWidth: 28

    readonly property real travel: height - knob.height
    Rectangle {  // the 0 dB tick
        x: 0; width: 6; height: 1; color: Theme.fg3
        y: knob.height / 2 + f.travel * (1 - F.posOfDb(0))
    }
    Rectangle {  // track
        id: track
        anchors.horizontalCenter: parent.horizontalCenter
        y: knob.height / 2; height: f.travel; width: 4; radius: 2
        color: hover.hovered ? Theme.lineHover : Theme.active
        Rectangle { anchors.bottom: parent.bottom; width: parent.width; radius: 2; color: Theme.accent
                    height: parent.height * f.pos }
    }
    Rectangle {  // knob
        id: knob
        anchors.horizontalCenter: parent.horizontalCenter
        y: f.travel * (1 - f.pos)
        width: 22; height: 14; radius: 3; color: "white"
        border.width: drag.pressed ? 2 : 0; border.color: Theme.accent
        Rectangle { anchors.centerIn: parent; width: parent.width - 8; height: 2; color: Theme.fg4 }
    }
    HoverHandler { id: hover }
    MouseArea {
        id: drag
        anchors.fill: parent
        preventStealing: true
        cursorShape: Qt.PointingHandCursor
        function at(y) { return F.gainOf(1 - Math.max(0, Math.min(1, (y - knob.height / 2) / f.travel))) }
        onPressed: (m) => { f.scrubStarted(); f.scrubbed(at(m.y)) }
        onPositionChanged: (m) => f.scrubbed(at(m.y))
        onReleased: f.scrubEnded()
        onCanceled: f.scrubEnded()
    }
}
