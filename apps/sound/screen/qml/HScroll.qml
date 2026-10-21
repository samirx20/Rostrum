import QtQuick
import RostrumKit

// A slim scrollbar for the timeline's view, there only while zoomed in: the thumb is the stretch of the song on
// screen; drag it, or press the track to bring that spot into the middle.
Item {
    id: sb
    readonly property real length: Math.max(0.001, backend.song.length)
    visible: !backend.viewFit
    height: 8
    Rectangle { anchors.fill: parent; radius: 4; color: Theme.sunken }
    Rectangle {
        id: thumb
        x: backend.viewStart / sb.length * sb.width; width: Math.max(24, backend.viewSpan / sb.length * sb.width)
        height: parent.height; radius: 4
        color: area.pressed || area.containsMouse ? Theme.lineHover : Theme.line
    }
    MouseArea {
        id: area
        anchors.fill: parent; hoverEnabled: true
        property real grab: 0
        function move(x) { backend.setViewStart((x - grab) / sb.width * sb.length) }
        onPressed: (m) => { grab = m.x >= thumb.x && m.x <= thumb.x + thumb.width ? m.x - thumb.x : thumb.width / 2
                            move(m.x) }
        onPositionChanged: (m) => move(m.x)
    }
}
