import QtQuick
import "."

// A slim scroll bar for a timeline's view (`view`: a rostrum_gui.timeview.TimeViewObject), there only while zoomed
// in: the thumb is the stretch on screen; drag it, or press the track to bring that spot into the middle. Drawn 8 px
// tall, its click area 16 px. Screen state, never an edit. (From Sound's HScroll, S35.)
Item {
    id: sb
    property var view
    readonly property real length: view ? Math.max(0.001, view.length) : 1
    visible: !!view && !view.fit
    implicitHeight: 16
    Rectangle { anchors.verticalCenter: parent.verticalCenter; width: parent.width; height: 8; radius: 4; color: Theme.sunken }
    Rectangle {
        id: thumb
        x: sb.view ? sb.view.start / sb.length * sb.width : 0
        width: sb.view ? Math.max(24, sb.view.span / sb.length * sb.width) : sb.width
        anchors.verticalCenter: parent.verticalCenter; height: 8; radius: 4
        color: area.pressed || area.containsMouse ? Theme.lineHover : Theme.line
    }
    MouseArea {
        id: area
        anchors.fill: parent; hoverEnabled: true
        property real grab: 0
        function move(x) { sb.view.setStart((x - grab) / sb.width * sb.length) }
        onPressed: (m) => { grab = m.x >= thumb.x && m.x <= thumb.x + thumb.width ? m.x - thumb.x : thumb.width / 2
                            move(m.x) }
        onPositionChanged: (m) => { if (pressed) move(m.x) }
    }
}
